from pathlib import Path
import osmnx as ox
import pandas as pd

GRAPH_PATH = Path(__file__).parent / Path("boston_walk.graphml")


def download_boston_walk_graph():
    ox.settings.use_cache = True
    ox.settings.timeout = 180
    G = ox.graph_from_place("Boston, MA", network_type="walk")
    G_proj = ox.project_graph(G)
    ox.save_graphml(G_proj, filepath=GRAPH_PATH)


def create_graph(crime_data: pd.DataFrame):
    if not GRAPH_PATH.exists():
        download_boston_walk_graph()
    G_proj = ox.load_graphml(GRAPH_PATH)
    breakpoint()
