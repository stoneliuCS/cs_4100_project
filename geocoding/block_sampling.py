"""
block address sampling and geocoding module.
"""

import io
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

# census geocoding api endpoint
GEOCODING_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BATCH_SIZE = 9999  # census api limit


def parse_block_address(block_address: str) -> dict:
    """
    parse a block address string to extract block number, street name, direction, and suffix.
    
    ex:
        "800 BLOCK WASHINGTON ST" -> {"block_num": 800, "street_name": "WASHINGTON", "direction": "", "suffix": "ST"}
        "WASHINGTON ST & WILLIAMS ST" -> {"block_num": None, "street_name": "WASHINGTON", "direction": "", "suffix": "ST", "is_intersection": True}
    """
    block_address = block_address.strip().upper()
    
    #intersection check
    if "&" in block_address:
        first_street = block_address.split("&")[0].strip()
        parts = first_street.split()
        if len(parts) >= 2:
            suffix = parts[-1] if parts[-1] in ["ST", "AVE", "RD", "BLVD", "DR", "LN", "WAY", "PL"] else ""
            street_name = " ".join(parts[:-1]) if suffix else first_street
        else:
            street_name = first_street
            suffix = ""
        return {
            "block_num": None,
            "street_name": street_name,
            "direction": "",
            "suffix": suffix,
            "is_intersection": True,
        }
    
    # block keyword check
    if "BLOCK" not in block_address:
        # not a block address, try to parse as regular address
        parts = block_address.split()
        if len(parts) >= 2:
            suffix = parts[-1] if parts[-1] in ["ST", "AVE", "RD", "BLVD", "DR", "LN", "WAY", "PL"] else ""
            street_name = " ".join(parts[:-1]) if suffix else block_address
        else:
            street_name = block_address
            suffix = ""
        return {
            "block_num": None,
            "street_name": street_name,
            "direction": "",
            "suffix": suffix,
            "is_intersection": False,
        }
    
    # remove "BLOCK" and split
    parts = block_address.replace("BLOCK", "").split()
    
    if not parts:
        return {
            "block_num": None,
            "street_name": "",
            "direction": "",
            "suffix": "",
            "is_intersection": False,
        }
    
    # block number
    block_num_str = parts[0]
    try:
        block_num = int(block_num_str)
    except ValueError:
        block_num = None
    
    # direction check
    direction = ""
    street_start_idx = 1
    if len(parts) > 1 and parts[1] in ["N", "S", "E", "W", "NE", "NW", "SE", "SW"]:
        direction = parts[1]
        street_start_idx = 2
    
    # suffix check
    suffix = ""
    street_end_idx = len(parts)
    if len(parts) > street_start_idx:
        last_part = parts[-1]
        if last_part in ["ST", "AVE", "RD", "BLVD", "DR", "LN", "WAY", "PL", "CIR", "CT"]:
            suffix = last_part
            street_end_idx = len(parts) - 1
    
    # street name is everything in between
    street_name = " ".join(parts[street_start_idx:street_end_idx]) if street_end_idx > street_start_idx else ""
    
    return {
        "block_num": block_num,
        "street_name": street_name,
        "direction": direction,
        "suffix": suffix,
        "is_intersection": False,
    }


def generate_block_samples(
    block_num: int, street_name: str, direction: str = "", suffix: str = "", spacing: int = 20
) -> list[str]:
    """
    generate sample addresses for a block by sampling every N addresses.
    
    ex: "800 BLOCK", "WASHINGTON", "E", "ST", 20 -> ["800 E WASHINGTON ST", "820 E WASHINGTON ST", 
      "840 E WASHINGTON ST", "860 E WASHINGTON ST", "880 E WASHINGTON ST", "900 E WASHINGTON ST", 
      "920 E WASHINGTON ST", "940 E WASHINGTON ST", "960 E WASHINGTON ST", "980 E WASHINGTON ST", "1000 E WASHINGTON ST"]
    """
    if block_num is None or block_num == 0:
        return []
    
    # generate addresses in the block range
    block_start = block_num
    block_end = block_num + 99
    
    # generate sample addresses
    samples = []
    for addr_num in range(block_start, block_end + 1, spacing):
        addr_parts = [str(addr_num)]
        if direction:
            addr_parts.append(direction)
        addr_parts.append(street_name)
        if suffix:
            addr_parts.append(suffix)
        
        samples.append(" ".join(addr_parts))
    
    return samples


def format_address_for_geocoding(
    address: str, city: str, state: str = "MA", zip_code: Optional[str] = None
) -> str:
    """
    format an address string for geocoding api
    """
    parts = [address, city, state]
    if zip_code:
        parts.append(str(zip_code))
    return ", ".join(parts)


def batch_geocode_addresses(addresses_df: pd.DataFrame) -> pd.DataFrame:
    """
    batch geocode addresses using census geocoding api
    """
    num_rows = len(addresses_df)
    all_results = []
    
    for i in range(0, num_rows, BATCH_SIZE):
        batch_df = addresses_df.iloc[i : i + BATCH_SIZE].copy()
        
        temp_csv = Path(__file__).parent / f"temp_geocoding_batch_{i // BATCH_SIZE + 1}.csv"
        batch_df.to_csv(temp_csv, index=False)
        
        try:
            with open(temp_csv, "rb") as f:
                files = {"addressFile": (temp_csv.name, f, "text/csv")}
                params = {"benchmark": "Public_AR_Current"}
                response = requests.post(GEOCODING_URL, files=files, params=params)
            
            if response.status_code == 200:
                column_names = [
                    "row_id",
                    "Input_Address",
                    "Match_Status",
                    "Match_Type",
                    "Matched_Address",
                    "Coordinates",
                    "TIGER_Line_ID",
                    "Side",
                ]
                batch_results = pd.read_csv(
                    io.StringIO(response.content.decode()), header=None, names=column_names
                )
                all_results.append(batch_results)
            else:
                raise RuntimeError(f"Geocoding API error: {response.status_code} - {response.text}")
        
        finally:
            if temp_csv.exists():
                temp_csv.unlink()
    
    if not all_results:
        return pd.DataFrame(
            columns=[
                "row_id",
                "Input_Address",
                "Match_Status",
                "Match_Type",
                "Matched_Address",
                "Coordinates",
                "TIGER_Line_ID",
                "Side",
            ]
        )
    
    return pd.concat(all_results, ignore_index=True)


def parse_coordinates(coordinates_str: str) -> tuple[Optional[float], Optional[float]]:
    """
    parse coordinates string from geocoding api response.
    
    format: "lon,lat" (e.g., "-71.05998397324,42.319283127")

    """
    if pd.isna(coordinates_str) or coordinates_str == "":
        return None, None
    
    try:
        parts = str(coordinates_str).split(",")
        if len(parts) == 2:
            lon = float(parts[0].strip())
            lat = float(parts[1].strip())
            return lon, lat
    except (ValueError, AttributeError):
        pass
    
    return None, None


def geocode_block_samples(
    block_address: str,
    city: str,
    zip_code: Optional[str] = None,
    spacing: int = 20,
    state: str = "MA",
) -> pd.DataFrame:
    """
    generate sample addresses for a block and geocode them
    """
    parsed = parse_block_address(block_address)
    
    if parsed["block_num"] is None or parsed["block_num"] == 0:
        return pd.DataFrame(
            columns=[
                "block_address",
                "sample_address",
                "formatted_address",
                "lat",
                "lon",
                "geocode_status",
                "matched_address",
            ]
        )
    
    sample_addresses = generate_block_samples(
        parsed["block_num"],
        parsed["street_name"],
        parsed["direction"],
        parsed["suffix"],
        spacing=spacing,
    )
    
    if not sample_addresses:
        return pd.DataFrame(
            columns=[
                "block_address",
                "sample_address",
                "formatted_address",
                "lat",
                "lon",
                "geocode_status",
                "matched_address",
            ]
        )
    
    formatted_addresses = [
        format_address_for_geocoding(addr, city, state, zip_code) for addr in sample_addresses
    ]
    
    geocoding_df = pd.DataFrame(
        {
            "id": range(1, len(sample_addresses) + 1),
            "address": sample_addresses,
            "city": [city] * len(sample_addresses),
            "state": [state] * len(sample_addresses),
            "zip": [zip_code] * len(sample_addresses) if zip_code else [""] * len(sample_addresses),
        }
    )
    
    geocoded_results = batch_geocode_addresses(geocoding_df)
    
    results = []
    for idx, row in geocoded_results.iterrows():
        lon, lat = parse_coordinates(row["Coordinates"])
        results.append(
            {
                "block_address": block_address,
                "sample_address": sample_addresses[idx] if idx < len(sample_addresses) else "",
                "formatted_address": formatted_addresses[idx] if idx < len(formatted_addresses) else "",
                "lat": lat,
                "lon": lon,
                "geocode_status": row["Match_Status"],
                "matched_address": row.get("Matched_Address", ""),
            }
        )
    
    return pd.DataFrame(results)


def process_all_block_addresses(
    aggregated_crimes: pd.DataFrame, spacing: int = 20
) -> pd.DataFrame:
    """
    process all unique block addresses from aggregated crimes dataframe.

    for each unique block address, generate samples, geocode them, and combine with crime scores.
    """
    unique_blocks = aggregated_crimes[
        ["Block Address", "City", "Zip Code", "Neighborhood", "Interval of Day", "Crime Score"]
    ].copy()
    
    block_groups = (
        unique_blocks.groupby(
            ["Block Address", "City", "Zip Code", "Neighborhood", "Interval of Day"],
            observed=True,
        )["Crime Score"]
        .sum()
        .reset_index()
    )
    
    all_results = []
    
    for _, row in block_groups.iterrows():
        block_address = row["Block Address"]
        city = row["City"]
        zip_code = row["Zip Code"]
        neighborhood = row["Neighborhood"]
        time_interval = row["Interval of Day"]
        crime_score = row["Crime Score"]
        
        geocoded_samples = geocode_block_samples(
            block_address, city, zip_code, spacing=spacing
        )
        
        if not geocoded_samples.empty:
            geocoded_samples["city"] = city
            geocoded_samples["zip_code"] = zip_code
            geocoded_samples["neighborhood"] = neighborhood
            geocoded_samples["time_interval"] = time_interval
            geocoded_samples["crime_score"] = crime_score
            all_results.append(geocoded_samples)
    
    if not all_results:
        return pd.DataFrame(
            columns=[
                "block_address",
                "sample_address",
                "formatted_address",
                "lat",
                "lon",
                "geocode_status",
                "matched_address",
                "city",
                "zip_code",
                "neighborhood",
                "time_interval",
                "crime_score",
            ]
        )
    
    result_df = pd.concat(all_results, ignore_index=True)
    
    result_df = result_df[
        result_df["geocode_status"].isin(["Match", "Tie"]) & result_df["lat"].notna() & result_df["lon"].notna()
    ]
    
    return result_df

