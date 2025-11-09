from data.crime_data import AGGREGATED_CRIMES_PATH
import pandas as pd

from graph.create_graph import create_graph


if __name__ == "__main__":
    if not AGGREGATED_CRIMES_PATH.exists():
        raise FileNotFoundError(
            f"{AGGREGATED_CRIMES_PATH} not found, please run the data pipeline to create it."
        )
    crime_data = pd.read_csv(AGGREGATED_CRIMES_PATH)
    time_of_day = 12
    create_graph(crime_data, time_of_day)
