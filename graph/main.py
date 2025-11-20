import pandas as pd

from geocoding.geocoding import geocode_aggregated_crimes
from graph.create_graph import create_graph
from data.crime_data import AGGREGATED_CRIMES_PATH


if __name__ == "__main__":
    if not AGGREGATED_CRIMES_PATH.exists():
        raise FileNotFoundError(
            f"{AGGREGATED_CRIMES_PATH} not found, please run the data pipeline to create it."
        )
    aggregated_crimes = pd.read_csv(AGGREGATED_CRIMES_PATH)
    crime_data = geocode_aggregated_crimes(aggregated_crimes)
    time_of_day = 12
    create_graph(crime_data, time_of_day)
