from data.crime_data import AGGREGATED_CRIMES_PATH
import pandas as pd

from graph.create_graph import create_graph


if __name__ == "__main__":
    crime_data = pd.read_csv(AGGREGATED_CRIMES_PATH)
    create_graph(crime_data)

