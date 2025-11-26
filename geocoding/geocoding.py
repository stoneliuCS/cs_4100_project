import pandas as pd

from pathlib import Path
import osmnx as os


GEOCODED_AGGREGATED_CRIMES = Path(__file__).parent / "geocoded_aggregated_crimes.csv"


def geocode_row(address: str):
    """
    Geocodes the following row
    """

    print(f"Geocoding {address}")
    try:
        coords = os.geocode(address)
        print(f"Successfully geocoded {address} to {coords}")
        return coords
    except Exception as e:
        print(f"Failed to geocode {e}")
        return "N/A"


def format_aggregated_crimes_for_geocoding(
    aggregated_crimes: pd.DataFrame,
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

    all_crimes["Block Address"] = all_crimes["Block Address"].str.replace(
        r"^.*BLOCK\s+", "", case=False, regex=True
    )
    # Now create a unique identifier for all crime addresses
    all_crimes["Address"] = (
        all_crimes["Block Address"]
        + ", "
        + all_crimes["Neighborhood"]
        + ", "
        + "MA"
        + ", "
        + all_crimes["Zip Code"].astype(str).str.zfill(5)
    )
    return all_crimes


def geocode_aggregated_crimes(aggregated_crimes: pd.DataFrame) -> pd.DataFrame:
    if GEOCODED_AGGREGATED_CRIMES.exists():
        return pd.read_csv(GEOCODED_AGGREGATED_CRIMES)
    sampled_aggregated_crimes = format_aggregated_crimes_for_geocoding(
        aggregated_crimes
    )
    addresses_to_geocode = (
        sampled_aggregated_crimes["Address"].drop_duplicates().to_frame()
    )
    addresses_to_geocode["Coordinates"] = addresses_to_geocode["Address"].apply(
        geocode_row
    )
    sampled_aggregated_crimes = sampled_aggregated_crimes.merge(
        addresses_to_geocode[["Address", "Coordinates"]], on="Address", how="left"
    )
    sampled_aggregated_crimes.to_csv(GEOCODED_AGGREGATED_CRIMES)
    return aggregated_crimes
