from data.crime_data import AGGREGATED_CRIMES_PATH, run_crime_dataset_creation
from data.image_data import IMAGE_CSV_PATH, run_image_dataset_creation
import pandas as pd


def main():
    if not AGGREGATED_CRIMES_PATH.exists():
        run_crime_dataset_creation()
    if not IMAGE_CSV_PATH.exists():
        run_image_dataset_creation()
    geocoded_crime_df = pd.read_csv(AGGREGATED_CRIMES_PATH)
    image_df = pd.read_csv(IMAGE_CSV_PATH)


if __name__ == "__main__":
    main()
