import pandas as pd

from data.crime_data import AGGREGATED_CRIMES_PATH
import osmnx as os

from geocoding.block_sampling import generate_block_samples, parse_block_address


def geocode_row(row):
    """
    Assigns a crime score to the following row
    """

    def create_query(sample: str) -> str:
        query = f"{sample} {row['City']} {row['Zip Code'].str.zfill(5)}"
        breakpoint()
        return query

    block_address = row["Block Address"]
    vals = parse_block_address(block_address)
    queries = generate_block_samples(
        block_num=vals["block_num"], street_name=vals["street_name"], suffix="ST"
    )
    queries = list(map(create_query, queries))


def geocode_aggregated_crimes(aggregated_crimes: pd.DataFrame) -> pd.DataFrame:
    geocoded_data = aggregated_crimes.apply(geocode_row, axis=1)
    return geocoded_data
