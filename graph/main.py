import pandas as pd
from geocoding.geocoding import compute_geocoding_stats, geocode_aggregated_crimes
from graph.create_graph import (
    create_graph,
    add_risk_cost_weights,
    convert_starting_and_end_coords,
)
from graph.visualize_graph import show_path_and_kde_full_and_zoom
from data.crime_data import AGGREGATED_CRIMES_PATH, run_crime_dataset_creation
import networkx as nx
import osmnx as ox

STARTING_DEST = "177 Massachusetts Ave, Boston, MA 02115"
ENDING_DEST = "82 Hillside St, Boston, MA 02120"
TIME_OF_DAY = 16  # The time of day in hours (military time)


if __name__ == "__main__":
    if not AGGREGATED_CRIMES_PATH.exists():
        run_crime_dataset_creation()

    # Geocoding crime dataset
    aggregated_crimes = pd.read_csv(AGGREGATED_CRIMES_PATH)
    crime_data = geocode_aggregated_crimes(aggregated_crimes)

    # Helpful to show how well the geocoding performed
    compute_geocoding_stats(crime_data)

    # Finally use a KDE based approach for risk calculation
    G, kde_attr = create_graph(crime_data, TIME_OF_DAY)

    # Add the risk costs to each of the distances
    risk_attr = add_risk_cost_weights(G, kde_attr)

    # Find the closest nodes from the given starting and ending addresses
    orig_node, dest_node = convert_starting_and_end_coords(
        STARTING_DEST, ENDING_DEST, G
    )

    # Run astar_path to find the shortest path
    def heuristic(u, v):
        node_u = G.nodes[u]
        node_v = G.nodes[v]
        return ox.distance.euclidean(node_u["y"], node_u["x"], node_v["y"], node_v["x"])
    
    path_nodes = nx.astar_path(
        G, source=orig_node, target=dest_node, weight=risk_attr, heuristic=heuristic
    )

    # Finally plot the heatmap of our KDE, our a-star path together so we can see what our model predicts as the
    # safest root!
    show_path_and_kde_full_and_zoom(
        G, path_nodes, risk_attr, kde_attr, hour_label=f"{TIME_OF_DAY}"
    )
