"""
quick test script for KDE pipeline w/o real data.
"""

import traceback
from geocoding.block_sampling import parse_block_address, generate_block_samples
from geocoding.kde_risk_surface import build_risk_kde, evaluate_kde_at_points
import pandas as pd
import numpy as np


# block address parsing
print("block address parsing test:")
test_addr = "800 BLOCK WASHINGTON ST"
parsed = parse_block_address(test_addr)
print(f"input: {test_addr}")
print(f"parsed: {parsed}")

if parsed["block_num"]:
    samples = generate_block_samples(
        parsed["block_num"],
        parsed["street_name"],
        parsed["direction"],
        parsed["suffix"],
        spacing=20,
    )
    print(f"generated {len(samples)} samples: {samples[:3]}")
    print("block address parsing works")

# KDE building with mock data
print("KDE building test:")
mock_data = pd.DataFrame({
    "lat": [42.3192, 42.3821, 42.3667, 42.3195, 42.3824],
    "lon": [-71.0599, -71.0808, -71.0370, -71.0602, -71.0811],
    "crime_score": [5.0, 3.0, 4.0, 2.0, 6.0],
})

print(f"created mock data with {len(mock_data)} crime locations")

try:
    # use UTM Zone 19N
    kde, transformer = build_risk_kde(mock_data, "EPSG:32619")
    print("KDE built")
    
    # evaluation
    from geocoding.kde_risk_surface import transform_coordinates_to_crs
    
    test_lon = -71.0599
    test_lat = 42.3192
    test_x, test_y = transform_coordinates_to_crs(
        np.array([test_lon]), np.array([test_lat]), transformer
    )
    
    test_points = np.array([[test_x[0], test_y[0]]])
    risk_score = evaluate_kde_at_points(kde, test_points)
    print(f"KDE works, risk score: {risk_score[0]:.10e}")  # scientific notation
    
except Exception as e:
    print(f"error: {e}")
    print(traceback.format_exc())

print("test complete")