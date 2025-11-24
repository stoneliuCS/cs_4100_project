from pathlib import Path
from networkx.classes.multidigraph import MultiDiGraph
import osmnx as ox
import pandas as pd
import pyproj
from shapely.geometry import LineString
import networkx as nx

GRAPH_PATH = Path(__file__).parent / Path("boston_walk.graphml")


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
        "coordinates"
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


def create_graph(crime_data: pd.DataFrame, time_of_day: int, bbox_buffer_size: int):
    """
    Creates a directed walkable graph network of the Boston area with edge weights that reflect risk.
    """
    if not GRAPH_PATH.exists():
        download_boston_walk_graph()
    G = ox.load_graphml(GRAPH_PATH)
    G = assign_crime_score_to_street_segment(
        crime_data, G, time_of_day, bbox_buffer_size
    )
