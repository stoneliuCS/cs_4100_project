import pandas as pd
from pathlib import Path
from graph.create_graph import (
    create_graph,
    add_risk_cost_weights,
    convert_starting_and_end_coords,
    coerce_kde_value
)
from graph.visualize_graph import show_path_and_kde_full_and_zoom
import networkx as nx
import math

STARTING_DEST = "24 Beacon St, Boston, MA 02133"
ENDING_DEST = "82 Hillside St, Boston, MA 02120"
TIME_OF_DAY = 14  # The time of day in hours (military time)

# Use the geocoded file directly
GEOCODED_CRIMES_PATH = Path(__file__).parent.parent / "geocoding" / "geocoded_aggregated_crimes.csv"


def euclidean_distance_heuristic(G, source, target):
    """
    Heuristic function for A*: straight-line distance between nodes.
    """

    def heuristic(u, v):
        x1, y1 = G.nodes[u]['x'], G.nodes[u]['y']
        x2, y2 = G.nodes[v]['x'], G.nodes[v]['y']
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    return heuristic


def calc_route_stats(path, G, kde_attr):
    """Calculate comprehensive statistics for a route."""
    total_dist = 0
    total_risk = 0
    max_risk = 0
    edge_count = 0

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edges = G.get_edge_data(u, v)
        if edges:
            edge = list(edges.values())[0]
            dist = edge.get('length', 0)
            risk_raw = edge.get(kde_attr, 0)

            # Use coerce_kde_value to properly convert risk
            risk = coerce_kde_value(risk_raw)

            total_dist += float(dist)
            total_risk += risk * dist  # Weight risk by distance
            max_risk = max(max_risk, risk)
            edge_count += 1

    avg_risk = total_risk / total_dist if total_dist > 0 else 0

    return {
        'distance_m': total_dist,
        'distance_km': total_dist / 1000,
        'avg_risk': avg_risk,
        'max_risk': max_risk,
        'total_risk_exposure': total_risk,
        'num_edges': edge_count,
        'time_min': (total_dist / 1000) / 5.0 * 60  # 5 km/h walking
    }


if __name__ == "__main__":
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

    # Find the closest nodes from the given starting and ending addresses
    print("\nFinding route nodes...")
    orig_node, dest_node = convert_starting_and_end_coords(
        STARTING_DEST, ENDING_DEST, G
    )
    print(f"Origin node: {orig_node}")
    print(f"Destination node: {dest_node}")

    # Create heuristic function
    heuristic = euclidean_distance_heuristic(G, orig_node, dest_node)

    # === FIND BOTH ROUTES ===

    # A* with risk-aware weights
    print("\nRunning A* to find safest path (crime-aware)...")
    astar_path = nx.astar_path(
        G, source=orig_node, target=dest_node, weight=risk_attr, heuristic=heuristic
    )
    print(f"A* safest path found: {len(astar_path)} nodes")

    # A* with distance only (fastest)
    print("Running A* to find fastest path (distance only)...")
    fastest_path = nx.astar_path(
        G, source=orig_node, target=dest_node, weight='length', heuristic=heuristic
    )
    print(f"A* fastest path found: {len(fastest_path)} nodes")

    # === CALCULATE STATISTICS ===

    astar_stats = calc_route_stats(astar_path, G, kde_attr)
    fastest_stats = calc_route_stats(fastest_path, G, kde_attr)

    # === PRINT COMPARISON ===

    print("\n" + "=" * 85)
    print("ROUTE COMPARISON: A* KDE RISK-AWARE vs A* FASTEST")
    print("=" * 85)
    print(f"\n{'Metric':<30} {'Fastest Route':<25} {'Risk-Aware Route':<25}")
    print("-" * 85)

    # Distance
    print(f"{'Distance':<30} {fastest_stats['distance_km']:>8.2f} km              "
          f"{astar_stats['distance_km']:>8.2f} km")

    # Time
    print(f"{'Walking Time (5 km/h)':<30} {fastest_stats['time_min']:>8.0f} min             "
          f"{astar_stats['time_min']:>8.0f} min")

    # Average Risk - Scientific notation
    print(f"{'Average Risk Score':<30} {fastest_stats['avg_risk']:>10.3e}            "
          f"{astar_stats['avg_risk']:>10.3e}")

    # Max Risk - Scientific notation
    print(f"{'Maximum Risk Encountered':<30} {fastest_stats['max_risk']:>10.3e}            "
          f"{astar_stats['max_risk']:>10.3e}")

    # Total Exposure - Scientific notation
    print(f"{'Total Risk Exposure':<30} {fastest_stats['total_risk_exposure']:>10.3e}            "
          f"{astar_stats['total_risk_exposure']:>10.3e}")

    print("=" * 85)

    # === ANALYSIS ===

    extra_dist = astar_stats['distance_km'] - fastest_stats['distance_km']
    extra_time = astar_stats['time_min'] - fastest_stats['time_min']

    if fastest_stats['avg_risk'] > 0:
        risk_reduction = (1 - astar_stats['avg_risk'] / fastest_stats['avg_risk']) * 100
    else:
        risk_reduction = 0

    if fastest_stats['max_risk'] > 0:
        max_risk_reduction = (1 - astar_stats['max_risk'] / fastest_stats['max_risk']) * 100
    else:
        max_risk_reduction = 0

    if fastest_stats['total_risk_exposure'] > 0:
        exposure_reduction = (1 - astar_stats['total_risk_exposure'] / fastest_stats['total_risk_exposure']) * 100
    else:
        exposure_reduction = 0

    print("\n📊 SAFETY ANALYSIS:")
    print("-" * 85)
    print(f"✓ Risk-aware route is {risk_reduction:.1f}% SAFER on average")
    print(f"✓ Maximum risk reduced by {max_risk_reduction:.1f}%")
    print(f"✓ Total risk exposure reduced by {exposure_reduction:.1f}%")

    print(f"\n💰 TRADE-OFF:")
    print(f"  • Extra distance: {extra_dist:.2f} km ({(extra_dist / fastest_stats['distance_km'] * 100):+.1f}%)")
    print(f"  • Extra time: {extra_time:.1f} minutes ({(extra_time / fastest_stats['time_min'] * 100):+.1f}%)")

    print(f"\n🎯 RECOMMENDATION:")
    if risk_reduction > 40:
        print(f"  ✓✓✓ STRONGLY RECOMMEND risk-aware route - MUCH SAFER ({risk_reduction:.0f}% less risky)")
        print(f"       Worth the {extra_time:.0f} extra minutes!")
    elif risk_reduction > 25:
        print(f"  ✓✓ RECOMMEND risk-aware route - SIGNIFICANTLY SAFER ({risk_reduction:.0f}% less risky)")
        print(f"      Only {extra_time:.0f} more minutes for much better safety")
    elif risk_reduction > 15:
        print(f"  ✓ Consider risk-aware route - MODERATELY SAFER ({risk_reduction:.0f}% less risky)")
        print(f"    Trade-off: {extra_time:.0f} extra minutes")
    elif risk_reduction > 5:
        print(f"  → Risk-aware route is SLIGHTLY SAFER ({risk_reduction:.0f}% less risky)")
        print(f"    Marginal benefit for {extra_time:.0f} extra minutes - your choice")
    else:
        print(f"  → Both routes have SIMILAR RISK ({risk_reduction:.0f}% difference)")
        print(f"    Take fastest route - no significant safety benefit")

    print("=" * 85 + "\n")

    # === VISUALIZE ===

    print("Generating visualization for risk-aware A* route...")
    show_path_and_kde_full_and_zoom(
        G, astar_path, risk_attr, kde_attr, hour_label=f"{TIME_OF_DAY}"
    )

    print("\n✓ Done!")
