import pandas as pd

from geocoding.geocoding import geocode_aggregated_crimes
from graph.create_graph import create_graph
from data.crime_data import AGGREGATED_CRIMES_PATH, run_crime_dataset_creation


if __name__ == "__main__":
    if not AGGREGATED_CRIMES_PATH.exists():
        run_crime_dataset_creation()
    aggregated_crimes = pd.read_csv(AGGREGATED_CRIMES_PATH)
    time_of_day = 12
    bbox_buffer_size = 10
    crime_data = geocode_aggregated_crimes(aggregated_crimes)
    G = create_graph(crime_data, time_of_day, bbox_buffer_size)
