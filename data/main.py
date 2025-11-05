from data.crime_data import GEOCODED_PATH, run_crime_dataset_creation
from data.image_data import IMAGE_CSV_PATH, run_image_dataset_creation
import pandas as pd


def main():
    if not GEOCODED_PATH.exists():
        run_crime_dataset_creation()
    if not IMAGE_CSV_PATH.exists():
        run_image_dataset_creation()
    geocoded_crime_df = pd.read_csv(GEOCODED_PATH)
    image_df = pd.read_csv(IMAGE_CSV_PATH)
    breakpoint()


if __name__ == "__main__":
    main()
