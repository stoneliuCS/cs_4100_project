from pathlib import Path
from geopandas import gpd
from networkx.classes.multidigraph import MultiDiGraph
import osmnx as ox
import pandas as pd
import pyproj
from shapely.geometry import LineString
import networkx as nx
from sklearn.neighbors import KernelDensity
import numpy as np
import logging
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

GRAPH_PATH = Path(__file__).parent / Path("boston_walk.graphml")
CRIME_GRAPH_PATH = Path(__file__).parent / Path("boston_walk_crime.graphml")


def download_boston_walk_graph():
    ox.settings.use_cache = True
    G = ox.graph_from_place("Boston, MA", network_type="walk")
    G_proj = ox.project_graph(G)
    ox.save_graphml(G_proj, filepath=GRAPH_PATH)


def lookup_street_and_assign(
    edge_data,
    crime_data: pd.DataFrame,
    G: MultiDiGraph,
    time_of_day: int,
    bbox_buffer_size: int,
) -> int | None:
    def lookup(coords, minx, miny, maxx, maxy):
        x = coords[0]
        y = coords[1]
        return minx <= x <= maxx and miny <= y <= maxy

    def time_in_interval(interval_str, hour):
        start, end = interval_str.split("-")
        start = int(start)
        end = int(end)
        return start <= hour <= end

    u_node = G.nodes[edge_data[0]]
    v_node = G.nodes[edge_data[1]]
    u_lat, u_lng = u_node["y"], u_node["x"]
    v_lat, v_lng = v_node["y"], v_node["x"]
    bbox = LineString([(u_lng, u_lat), (v_lng, v_lat)])
    bbox_with_buffer = bbox.buffer(bbox_buffer_size)  # Add a buffer of 100 meters
    minx, miny, maxx, maxy = bbox_with_buffer.bounds
    crimes_in_bbox = crime_data[
        crime_data["converted_coordinates"].apply(
            lambda coord: lookup(coord, minx, miny, maxx, maxy)
        )
    ]
    time_of_day_bucket = crimes_in_bbox["Interval of Day"]
    crimes_in_time_window = crimes_in_bbox[
        time_of_day_bucket.apply(
            lambda interval: time_in_interval(interval, time_of_day)
        )
    ]
    if len(crimes_in_time_window) == 0:
        return None
    else:
        mean_score = crimes_in_time_window["Crime Score"].mean()
        return mean_score


def assign_crime_score_to_street_segment(
    crime_data: pd.DataFrame, G: MultiDiGraph, time_of_day: int, bbox_buffer_size: int
):
    cleaned_crime_data = crime_data.dropna()
    # convert the latitude and longitude into x and y values
    graph_crs = G.graph["crs"]
    transformer = pyproj.Transformer.from_crs("EPSG:4326", graph_crs, always_xy=True)

    def coord_transformer(coord_str):
        coord_str = coord_str.strip("()")
        lat_str, lon_str = coord_str.split(",")
        lat = float(lat_str.strip())
        lon = float(lon_str.strip())
        x, y = transformer.transform(lon, lat)
        return x, y

    cleaned_crime_data["converted_coordinates"] = cleaned_crime_data[
        "Coordinates"
    ].apply(coord_transformer)

    total_edges = 0
    assigned_edges = 0

    for u, v, k, data in G.edges(keys=True, data=True):
        total_edges += 1
        score = lookup_street_and_assign(
            (u, v, k, data), cleaned_crime_data, G, time_of_day, bbox_buffer_size
        )
        G[u][v][k]["crime_score"] = score
        if score is not None:
            print(f"Successfully assigned crime score: {score}")
            assigned_edges += 1

    print(
        f"Successfully assigned crime scores to {assigned_edges} out of {total_edges} edges ({assigned_edges / total_edges * 100:.1f}%)"
    )
    return G


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


def plot_kde_graph(G: MultiDiGraph, attr_name: str):
    # Get the KDE values for edges, defaulting to 0 if missing
    kde_vals = np.array(
        [d.get(attr_name, 0.0) for _, _, _, d in G.edges(keys=True, data=True)]
    )

    vmax = kde_vals.max() if kde_vals.size > 0 else 0
    if vmax > 0:
        kde_norm = kde_vals / vmax
    else:
        kde_norm = kde_vals

    cmap = plt.cm.inferno
    edge_colors = [cmap(v) for v in kde_norm]

    fig, ax = ox.plot_graph(
        G,
        node_size=0,
        edge_color=edge_colors,
        edge_linewidth=1,
        bgcolor="white",
        show=False,
        close=False,
    )
    plt.show()


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
