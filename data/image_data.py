import mapillary.interface as mly
import mapillary.controller as controller
import pandas as pd
from datetime import datetime
from pathlib import Path
import os

def get_image_metadata(image_id : int, res=256):
    url = controller.image.get_image_thumbnail_controller(image_id=str(image_id), resolution=res)
    detections = mly.get_detections_with_image_id(image_id=image_id)
    return url, detections

def create_image_dataset(lat: float, lng: float, radius: float) -> pd.DataFrame:
    """Creates an image Dataset of the nearest images from the given latitude and longitude
    and radius in meters.
    """
    # Much larger area
    geo_jsons = mly.get_image_close_to(lat, lng, radius=radius, fields="all")
    data = geo_jsons.features
    schema = {
        "time_epoch": [],
        "datetime": [],
        "longitude": [],
        "latitude": [],
        "image_id": [],
        "sequence_id": [],
    }
    for image_data in data:
        image_id = image_data.properties.id
        epoch_time = image_data.properties.captured_at
        coordinates = image_data.geometry.coordinates
        sequence_id = image_data.properties.sequence_id
        url, objects = get_image_metadata(image_id)
        schema["time_epoch"].append(epoch_time)
        schema["datetime"].append(datetime.fromtimestamp(epoch_time / 1000))
        schema["longitude"].append(coordinates.longitude)
        schema["latitude"].append(coordinates.latitude)
        schema["image_id"].append(image_id)
        schema["sequence_id"].append(sequence_id)
    return pd.DataFrame(schema)


def main():
    NORTHEASTERN_UNI_LAT_LNG = [42.3398, -71.0892]
    RADIUS_METERS = 10000
    CSV_PATH = Path(__file__).parent / "./image_data.csv"
    image_dataset = create_image_dataset(
        NORTHEASTERN_UNI_LAT_LNG[0], NORTHEASTERN_UNI_LAT_LNG[1], RADIUS_METERS
    )
    image_dataset.to_csv(CSV_PATH)


if __name__ == "__main__":
    access_token = os.getenv("MAPILLARY_ACCESS_TOKEN")
    if access_token is None:
        raise RuntimeError("MAPILLARY_ACCESS_TOKEN is undefined")
    mly.set_access_token(access_token)
    main()
