"""
    This file generates routes for multiple pairs of (start, end) points and 
    compare the overall result of our model.
"""

from pathlib import Path
import pandas as pd
import networkx as nx

from graph.create_graph import (
    create_graph,
    add_risk_cost_weights,
    convert_starting_and_end_coords,
)
from graph.main import (
    euclidean_distance_heuristic,
    calc_route_stats
)

TIME_OF_DAY = 14 
ROUTE_PAIRS = [("24 Beacon St, Boston, MA 02133", "82 Hillside St, Boston, MA 02120"),
               ("82 Hillside St, Boston, MA 02120", "360 Huntington Ave, Boston, MA 02115"),
               ("744 Columbus Ave., Boston, MA 02120", "360 Huntington Ave, Boston, MA 02115"),
               ("175 Federal St, Boston, MA 02110", "70 Kneeland St, Boston, MA 02111"),
               ("175 Federal St, Boston, MA 02110", "50 Beach St, Boston, MA 02111"),
               ("88 Harrison Ave, Boston, MA 02111", "850 Harrison Ave, Boston, MA 02118"),
               ("170 Newbury St, Boston, MA 02116", "1490 Tremont St, Boston, MA 02120"),
               ("360 Huntington Ave, Boston, MA 02115", "95 Saint Stephen St, Boston, MA 02115"),
               ("77 Massachusetts Ave, Cambridge, MA 02139", "800 Boylston St, Boston, MA 02199"),
               ("296 Meridian St, East Boston, MA 02128", "1 India St, Boston, MA 02109")
               ]

GEOCODED_CRIMES_PATH = Path(__file__).parent.parent / "geocoding" / "geocoded_aggregated_crimes.csv"

def evaluate_route(start_addr, end_addr, G, kde_attr, risk_attr):
    """
    Find and evaluate route for a given pair of start and end address.
    """
    # Find the closest nodes from the given starting and ending addresses
    print("\nFinding route nodes...")
    orig_node, dest_node = convert_starting_and_end_coords(start_addr, end_addr, G)
    print(f"Origin node: {orig_node}")
    print(f"Destination node: {dest_node}")

    # Create heuristic function
    heuristic = euclidean_distance_heuristic(G, orig_node, dest_node)

    # find fastest and safest path
    print("\nRunning A* to find safest path (crime-aware)...")
    safest_path = nx.astar_path(
        G, source=orig_node, target=dest_node, weight=risk_attr, heuristic=heuristic
    )
    print(f"A* safest path found: {len(safest_path)} nodes")
    print("Running A* to find fastest path (distance only)...")
    fastest_path = nx.astar_path(
        G, source=orig_node, target=dest_node, weight='length', heuristic=heuristic
    )
    print(f"A* fastest path found: {len(fastest_path)} nodes")

    # get quantive results
    fast_stats = calc_route_stats(fastest_path, G, kde_attr)
    safe_stats = calc_route_stats(safest_path, G, kde_attr)

    extra_dist = safe_stats['distance_km'] - fast_stats['distance_km']
    extra_time = safe_stats['time_min'] - fast_stats['time_min']

    if fast_stats['avg_risk'] > 0:
        risk_reduction = (1 - safe_stats['avg_risk'] / fast_stats['avg_risk']) * 100
    else:
        risk_reduction = 0

    if fast_stats['total_risk_exposure'] > 0:
        exposure_reduction = (1 - safe_stats['total_risk_exposure'] / fast_stats['total_risk_exposure']) * 100
    else:
        exposure_reduction = 0

    return {
        "Start": start_addr,
        "End": end_addr,
        "Fast: Distance (km)": fast_stats['distance_km'],
        "Safe: Distance (km)": safe_stats['distance_km'],
        "Distance Increase (%)": extra_dist / fast_stats['distance_km'] * 100 if fast_stats['distance_km'] > 0 else 0,
        "Fast: Compute Time (min)": fast_stats['time_min'],
        "Safe: Compute Time (min)": safe_stats['time_min'],
        "Time Increase (%)": extra_time / fast_stats['time_min'] * 100 if fast_stats['time_min'] > 0 else 0,
        "Fast: Average Risk": fast_stats['avg_risk'],
        "Safe: Average Risk": safe_stats['avg_risk'],
        "Risk Reduction (%)": risk_reduction,
        "Fast: Total Risk Exposure": fast_stats['total_risk_exposure'],
        "Safe: Total Risk Exposure": safe_stats['total_risk_exposure'],
        "Exposure Reduction (%)": exposure_reduction,
    }

if __name__ == "__main__":
    print("This file evaluates the performance for multiple routes")
    # Load already-geocoded crime data
    print("Loading geocoded crime data...")
    crime_data = pd.read_csv(GEOCODED_CRIMES_PATH)
    print(f"Loaded {len(crime_data)} crime records")

    # Use KDE approach for risk calculation
    print(f"\nBuilding KDE graph for time {TIME_OF_DAY}:00...")
    print("(First run: 60-80 min, subsequent runs: instant with cache)")
    G, kde_attr = create_graph(crime_data, TIME_OF_DAY)
    print(f"Graph built with attribute: {kde_attr}")

    # Add the risk costs to each of the distances
    risk_attr = add_risk_cost_weights(G, kde_attr)

    # Start finding routes
    # Find route for multiple (start,end) pairs
    results = []
    for start, end in ROUTE_PAIRS:
        print(f"Evaluating: {start} -> {end}")

        res = evaluate_route(start, end, G, kde_attr, risk_attr)
        results.append(res)

    df_results = pd.DataFrame(results)
    print(df_results)

    df_results.to_csv("route_evaluation_results.csv", index=False)

    # print out important evaluations
    print("\nAverage distance increase (%):", df_results["Distance Increase (%)"].mean())
    print("Average risk reduction (%):", df_results["Risk Reduction (%)"].mean())
    print("Average exposure reduction (%):", df_results["Exposure Reduction (%)"].mean())
