import pandas as pd

from pathlib import Path
import osmnx as os

from geocoding.block_sampling import generate_block_samples, parse_block_address

GEOCODED_AGGREGATED_CRIMES = Path(__file__).parent / "geocoded_aggregated_crimes.csv"


def geocode_row(row):
    """
    Geocodes the following row
    """

    def create_query(sample: str) -> str:
        query = f"{sample} {row['City']} {str(row['Zip Code']).zfill(5)}"
        return query

    block_address = row["Block Address"]
    vals = parse_block_address(block_address)
    queries = generate_block_samples(
        block_num=vals["block_num"], street_name=vals["street_name"], suffix="ST"
    )
    queries = list(map(create_query, queries))
    try:
        print(f"Geocoding {queries}")
        return os.geocode(queries)
    except Exception as e:
        print(f"Failed to geocode {e}")
        return "N/A"


def geocode_aggregated_crimes(aggregated_crimes: pd.DataFrame) -> pd.DataFrame:
    if GEOCODED_AGGREGATED_CRIMES.exists():
        return pd.read_csv(GEOCODED_AGGREGATED_CRIMES)
    aggregated_crimes["coordinates"] = aggregated_crimes.apply(geocode_row, axis=1)
    aggregated_crimes.to_csv(GEOCODED_AGGREGATED_CRIMES)
    return aggregated_crimes
