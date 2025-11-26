import pandas as pd

from geocoding.geocoding import geocode_aggregated_crimes
from graph.create_graph import create_graph, plot_kde_graph
from data.crime_data import AGGREGATED_CRIMES_PATH, run_crime_dataset_creation


if __name__ == "__main__":
    if not AGGREGATED_CRIMES_PATH.exists():
        run_crime_dataset_creation()

    # Geocoding crime dataset
    aggregated_crimes = pd.read_csv(AGGREGATED_CRIMES_PATH)
    time_of_day = 12
    bbox_buffer_size = 10
    crime_data = geocode_aggregated_crimes(aggregated_crimes)

    # Print stats on geocoding
    num_failed = crime_data["Coordinates"].isna().sum()
    num_success = crime_data["Coordinates"].notna().sum()
    total = len(crime_data)
    failed_pct = num_failed / total * 100
    success_pct = num_success / total * 100
    print(f"Failed geocodes: {num_failed} ({failed_pct:.2f}%)")
    print(f"Successful geocodes: {num_success} ({success_pct:.2f}%)")

    # Finally use a KDE based approach for risk calculation
    G, attr_name = create_graph(crime_data, time_of_day)
    plot_kde_graph(G, attr_name)
