from pathlib import Path
from networkx.classes.multidigraph import MultiDiGraph
import osmnx as ox
import pandas as pd

GRAPH_PATH = Path(__file__).parent / Path("boston_walk.graphml")


def download_boston_walk_graph():
    ox.settings.use_cache = True
    G = ox.graph_from_place("Boston, MA", network_type="walk")
    G_proj = ox.project_graph(G)
    ox.save_graphml(G_proj, filepath=GRAPH_PATH)


def lookup_street_and_assign(edge_data, crime_data: pd.DataFrame) -> int | None:
    def lookup(street_name):
        street_name_matches = crime_data[
            crime_data["Block Address"].str.contains(street_name)
        ]
        if len(street_name_matches) == 0:
            return None
        else:
            breakpoint()

    print(edge_data)
    street = edge_data["name"]
    scores: list[int | None] = []
    if type(street) == list:
        for s in street:
            scores.append(lookup(s))
    else:
        scores.append(lookup(street))


def assign_crime_score_to_street_segment(
    crime_data: pd.DataFrame, G: MultiDiGraph, time_of_day: int
):
    # Filter out all the addresses with blocks.
    crimes_with_block = crime_data[crime_data["Block Address"].str.contains("BLOCK")]
    crimes_with_no_block = crime_data[
        ~crime_data["Block Address"].str.contains("BLOCK")
    ]
    for u, v, k, data in G.edges(keys=True, data=True):
        lookup_street_and_assign(data, crime_data)


def create_graph(crime_data: pd.DataFrame, time_of_day: int):
    """
    Creates a directed walkable graph network of the Boston area with edge weights that reflect risk.
    """
    if not GRAPH_PATH.exists():
        download_boston_walk_graph()
    G = ox.load_graphml(GRAPH_PATH)
    assign_crime_score_to_street_segment(crime_data, G, time_of_day)
