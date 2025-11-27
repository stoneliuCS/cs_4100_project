from pathlib import Path
from geopandas import gpd
from networkx.classes.multidigraph import MultiDiGraph
import osmnx as ox
import pandas as pd
from shapely.geometry import LineString, Point
import networkx as nx
from sklearn.neighbors import KernelDensity
import numpy as np
import logging
from geocoding.geocoding import geocode_row

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

GRAPH_PATH = Path(__file__).parent / Path("boston_walk.graphml")
CRIME_GRAPH_PATH = Path(__file__).parent / Path("boston_walk_crimes")


def download_boston_walk_graph():
    ox.settings.use_cache = True
    G = ox.graph_from_place("Boston, MA", network_type="walk")
    G_proj = ox.project_graph(G)
    ox.save_graphml(G_proj, filepath=GRAPH_PATH)


def convert_starting_and_end_coords(
    starting_address, ending_address: str, G: MultiDiGraph
):
    """
    Giving a starting and ending address computes the nearest nodes in G
    """
    lat_start, lng_start = geocode_row(starting_address)
    lat_end, lng_end = geocode_row(ending_address)

    graph_crs = G.graph.get("crs", "EPSG:4326")

    pts = gpd.GeoDataFrame(
        geometry=[
            Point(lng_start, lat_start),
            Point(lng_end, lat_end),
        ],
        crs="EPSG:4326",
    ).to_crs(graph_crs)

    start_pt = pts.geometry.iloc[0]
    end_pt = pts.geometry.iloc[1]

    orig_node = ox.nearest_nodes(G, X=start_pt.x, Y=start_pt.y)
    dest_node = ox.nearest_nodes(G, X=end_pt.x, Y=end_pt.y)

    return orig_node, dest_node


def run_kde_on_graph(
    crime_data: pd.DataFrame,
    time_of_day: int,
    G: MultiDiGraph,
    bandwidth: float = 150.0,
    step: float = 25.0,
):
    crime_data = crime_data.dropna(subset=["Coordinates"]).copy()
    crime_data["latlon_clean"] = crime_data["Coordinates"].str.strip("()").str.strip()
    crime_data[["lat", "lon"]] = (
        crime_data["latlon_clean"].str.split(",", expand=True).astype(float)
    )
    crime_data = crime_data.drop("latlon_clean", axis=1)
    temp_df = crime_data.copy()
    crime_geo_data = gpd.GeoDataFrame(
        temp_df,
        geometry=gpd.points_from_xy(temp_df["lon"], temp_df["lat"]),
        crs="EPSG:4326",
    )
    interval_bounds = (
        crime_geo_data["Interval of Day"].str.strip().str.split("-", expand=True)
    )
    crime_geo_data["interval_start"] = interval_bounds[0].astype(int)
    crime_geo_data["interval_end"] = interval_bounds[1].astype(int)
    mask = (crime_geo_data["interval_start"] <= time_of_day) & (
        crime_geo_data["interval_end"] > time_of_day
    )
    bucket_gdf = crime_geo_data.loc[mask].copy()
    G_proj = ox.project_graph(G)
    _, edges_gdf = ox.graph_to_gdfs(G_proj)
    total_edges = len(edges_gdf)

    target_crs = edges_gdf.crs
    bucket_proj = bucket_gdf.to_crs(target_crs)
    bucket_proj = bucket_proj[bucket_proj.geometry.notna()]
    X = np.vstack([bucket_proj.geometry.x, bucket_proj.geometry.y]).T
    if "Crime Score" in bucket_proj.columns:
        weights = bucket_proj["Crime Score"].astype(float).values
        weights = np.nan_to_num(weights, nan=0.0)
        weights[weights < 0] = 0.0
    else:
        weights = None
    kde = KernelDensity(bandwidth=bandwidth, kernel="gaussian")
    kde.fit(X, sample_weight=weights)

    def sample_points_along_line(line: LineString, step: float):
        length = line.length
        if length == 0:
            return []
        distances = np.arange(0, length + step, step)
        return [line.interpolate(d) for d in distances]

    def edge_kde_score(line: LineString, step: float) -> float:
        pts = sample_points_along_line(line, step)
        if not pts:
            return 0.0
        coords = np.array([[p.x, p.y] for p in pts])
        log_dens = kde.score_samples(coords)
        dens = np.exp(log_dens)
        return float(dens.mean())

    kde_scores = {}
    for i, (idx, edge) in enumerate(edges_gdf.iterrows(), start=1):
        if i % 1000 == 0 or i == total_edges:
            logger.info("KDE running on edge %s (%d/%d)", idx, i, total_edges)
        geom = edge.geometry
        kde_scores[idx] = edge_kde_score(geom, step=step)

    nx.set_edge_attributes(G_proj, kde_scores, create_attr_name(time_of_day))
    return G_proj


def create_attr_name(time_of_day: int):
    bucket_start = (time_of_day // 4) * 4
    bucket_end = bucket_start + 4
    attr_name = f"kde_score_for_{bucket_start:02d}_{bucket_end:02d}"
    return attr_name


def coerce_kde_value(value):
    """GraphML stores edge attributes as strings; convert them to floats."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    try:
        value_str = str(value).strip()
        return float(value_str) if value_str else 0.0
    except (TypeError, ValueError):
        logger.debug("Unable to parse KDE value %r for %s", value, attr_name)
        return 0.0


def add_risk_cost_weights(G, risk_attr: str, alpha: float = 3.0):
    """
    Adds a risk cost associated with each edge and returns the weight attribute used for a_star

    The cost of an edge is dependent on its normalized risk and weights this is to prevent paths that
    are not very feasible.
    """
    risks = [
        coerce_kde_value(d.get(risk_attr, 0.0))
        for _, _, _, d in G.edges(keys=True, data=True)
    ]
    max_risk = max(risks) if risks else 0.0
    if max_risk == 0:
        max_risk = 1.0

    for _, _, _, data in G.edges(keys=True, data=True):
        length = data.get("length", 1.0)
        risk = coerce_kde_value(data.get(risk_attr, 0.0))
        norm_risk = risk / max_risk
        cost = length * (1.0 + alpha * norm_risk)
        data["risk_cost"] = cost

    return "risk_cost"


def create_graph(crime_data: pd.DataFrame, time_of_day: int):
    """
    Creates a directed walkable graph network of the Boston area with edge weights that reflect risk.
    """

    if not GRAPH_PATH.exists():
        download_boston_walk_graph()
    attr_name = create_attr_name(time_of_day)
    path = CRIME_GRAPH_PATH / f"{attr_name}.graphml"
    if path.exists():
        return ox.load_graphml(path), attr_name
    G = ox.load_graphml(GRAPH_PATH)
    G_proj = run_kde_on_graph(crime_data, time_of_day, G)
    ox.save_graphml(G_proj, path)
    return G_proj, attr_name
