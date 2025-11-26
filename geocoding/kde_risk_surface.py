"""
kde risk surface module.
"""

from typing import Optional, Tuple

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.stats import gaussian_kde


def create_coordinate_transformer(
    source_crs: str = "EPSG:4326", target_crs: str = None
) -> Transformer:
    """
    create a coordinate transformer from source CRS to target CRS.

    args:
        source_crs: source coordinate reference system (default: WGS84)
        target_crs: target coordinate reference system (e.g., graph's projected CRS)

    returns:
        pyproj Transformer object
    """
    if target_crs is None:
        raise ValueError("target_crs must be provided")

    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return transformer


def transform_coordinates_to_crs(
    lons: np.ndarray,
    lats: np.ndarray,
    transformer: Transformer,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    transform coordinates from WGS84 to target CRS.

    args:
        lons: array of longitudes (WGS84)
        lats: array of latitudes (WGS84)
        transformer: pyproj Transformer object

    returns:
        tuple of (x_coords, y_coords) in target CRS
    """
    # (lon, lat) -> (x, y) in target CRS
    x_coords, y_coords = transformer.transform(lons, lats)
    return np.array(x_coords), np.array(y_coords)


def build_risk_kde(
    geocoded_crimes: pd.DataFrame,
    graph_crs: str,
    bandwidth: Optional[float] = None,
    weights: Optional[np.ndarray] = None,
) -> Tuple[gaussian_kde, Transformer]:
    """
    build a KDE from geocoded crime data with crime scores as weights.

    args:
        geocoded_crimes: dataframe with columns:
            - lat: latitude (WGS84)
            - lon: longitude (WGS84)
            - crime_score: crime score (used as weight)
        graph_crs: graph's coordinate reference system (e.g., "EPSG:32619" for UTM zone 19N)
        bandwidth: bandwidth for KDE (if None, uses scipy's default)
        weights: optional array of weights (if None, uses crime_score column)

    returns:
        tuple of (fitted KDE object, coordinate transformer)
    """
    # remove rows with missing coordinates
    valid_data = geocoded_crimes[
        geocoded_crimes["lat"].notna() & geocoded_crimes["lon"].notna()
    ].copy()

    if len(valid_data) == 0:
        raise ValueError("No valid coordinates found in geocoded_crimes")

    transformer = create_coordinate_transformer(
        source_crs="EPSG:4326", target_crs=graph_crs
    )

    lons = valid_data["lon"].values
    lats = valid_data["lat"].values

    # transform to graphs crs
    x_coords, y_coords = transform_coordinates_to_crs(lons, lats, transformer)

    # get crime scores
    if weights is None:
        weights = valid_data["crime_score"].values
    else:
        weights = weights[valid_data.index]

    weights = np.maximum(weights, 0.0)

    # filter out zero crime scores
    mask = weights > 0
    x_coords = x_coords[mask]
    y_coords = y_coords[mask]
    weights = weights[mask]

    if len(x_coords) == 0:
        raise ValueError("No points with positive weights")

    # normalize weights to a reasonable range for replication
    max_replications = 50
    weight_min = weights.min()
    weight_max = weights.max()

    if weight_max > weight_min:
        normalized_weights = 1 + (weights - weight_min) / (weight_max - weight_min) * (
            max_replications - 1
        )
    else:
        normalized_weights = np.ones_like(weights) * max_replications

    integer_weights = np.round(normalized_weights).astype(int)

    x_replicated = np.repeat(x_coords, integer_weights)
    y_replicated = np.repeat(y_coords, integer_weights)

    kde_data = np.vstack([x_replicated, y_replicated])

    # build KDE
    if bandwidth is not None:
        kde = gaussian_kde(kde_data, bw_method=bandwidth)
    else:
        kde = gaussian_kde(kde_data)

    return kde, transformer


def evaluate_kde_at_points(kde: gaussian_kde, points: np.ndarray) -> np.ndarray:
    """
    evaluate KDE at given coordinate points.

    points should already be in the graph's projected crs

    args:
        kde: fitted gaussian_kde object
        points: arr of shape (n_points, 2) where cols are [x, y] coords in the graph's projected crs

    returns:
        arr of risk scores
    """
    if points.shape[1] != 2:
        raise ValueError("points must have shape (n_points, 2) with columns [x, y]")

    points_T = points.T

    risk_scores = kde(points_T)

    # non-negative
    risk_scores = np.maximum(risk_scores, 0.0)

    return risk_scores

