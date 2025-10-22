"""
Crime dataset creation
"""

from pathlib import Path
import pandas as pd

CSV_PATH = Path(__file__).parent / "crime.csv"

def main():
    if not CSV_PATH.exists():
        raise RuntimeError(
            f"{CSV_PATH} not found, please download it here: https://boston-pd-crime-hub-boston.hub.arcgis.com/datasets/d42bd4040bca419a824ae5062488aced/explore"
        )
    crime_dataframe = pd.read_csv(CSV_PATH)
    # Do something interesting with the data

if __name__ == "__main__":
    main()
