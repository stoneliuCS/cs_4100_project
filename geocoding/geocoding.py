import pandas as pd

from pathlib import Path
import osmnx as os
import re

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


def sample_street_addresses(address, step_size: int):
    def expand_block_address(address, step=10):
        match = re.search(r"(\d+)\s+BLOCK\s+", address)

        if match:
            start_num = int(match.group(1))
        else:
            start_num = 0

        numbers = list(range(start_num, start_num + 101, step))

        expanded = []
        for num in numbers:
            new_addr = re.sub(r"\d+\s+BLOCK\s+", f"{num} ", address)
            expanded.append(new_addr)

        return expanded

    return expand_block_address(address, step_size)


def format_aggregated_crimes_for_geocoding(
    aggregated_crimes: pd.DataFrame, step_size: int
) -> pd.DataFrame:
    """
    A transform on the aggregated crimes dataset intended to clean up and add an address column for geocoding.
    """
    multi_block_crimes: pd.DataFrame = aggregated_crimes[
        aggregated_crimes["Block Address"].str.contains("&")
    ]
    single_blocks = multi_block_crimes["Block Address"].str.split("&")
    exploded_crimes = multi_block_crimes.copy()
    exploded_crimes["Block Address"] = single_blocks
    exploded_crimes = exploded_crimes.explode("Block Address")
    exploded_crimes["Block Address"] = exploded_crimes["Block Address"].str.strip()
    single_block_crimes = aggregated_crimes[
        ~aggregated_crimes["Block Address"].str.contains("&")
    ]
    all_crimes = pd.concat([single_block_crimes, exploded_crimes], ignore_index=True)
    # Now create a unique identifier for all crime addresses
    all_crimes["Address"] = (
        all_crimes["Block Address"]
        + " "
        + all_crimes["Neighborhood"]
        + " "
        + "MA"
        + " "
        + all_crimes["Zip Code"].astype(str).str.zfill(5)
    )
    all_crimes_exploded = all_crimes.copy()
    all_crimes_exploded["Address"] = all_crimes_exploded["Address"].apply(
        lambda address: sample_street_addresses(address, step_size)
    )
    all_crimes_exploded = all_crimes_exploded.explode("Address").reset_index(drop=True)
    original_addresses = set(all_crimes["Address"])

    # Now we filter to only the sampled addresses
    sampled_only = all_crimes_exploded[
        ~all_crimes_exploded["Address"].isin(original_addresses)
    ]
    return sampled_only


def geocode_aggregated_crimes(aggregated_crimes: pd.DataFrame) -> pd.DataFrame:
    # First create a unique address as precise as possible
    sampled_aggregated_crimes = format_aggregated_crimes_for_geocoding(
        aggregated_crimes, 20
    )
    if GEOCODED_AGGREGATED_CRIMES.exists():
        return pd.read_csv(GEOCODED_AGGREGATED_CRIMES)
    sampled_aggregated_crimes["coordinates"] = sampled_aggregated_crimes.apply(
        geocode_row, axis=1
    )
    sampled_aggregated_crimes.to_csv(GEOCODED_AGGREGATED_CRIMES)
    return aggregated_crimes
