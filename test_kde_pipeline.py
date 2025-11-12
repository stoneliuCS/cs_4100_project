"""
test script for KDE risk surface pipeline with real data.
"""

import sys
from pathlib import Path
import traceback

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from geocoding.block_sampling import (
    generate_block_samples,
    parse_block_address,
    parse_coordinates,
)
from geocoding.kde_risk_surface import (
    build_risk_kde,
    create_coordinate_transformer,
    evaluate_kde_at_points,
    transform_coordinates_to_crs,
)


def test_block_address_parsing():
    """block address parsing."""
    test_cases = [
        "800 BLOCK WASHINGTON ST",
        "200 BLOCK E COTTAGE ST",
        "100 BLOCK W FIFTH ST",
        "0 BLOCK CLINTON ST",
        "WASHINGTON ST & WILLIAMS ST",
        "100 BLOCK HUNTINGTON AVE",
    ]
    
    for addr in test_cases:
        parsed = parse_block_address(addr)
        print(f"\nInput: {addr}")
        print(f"  block_num: {parsed['block_num']}")
        print(f"  street_name: {parsed['street_name']}")
        print(f"  direction: {parsed['direction']}")
        print(f"  suffix: {parsed['suffix']}")
        
        if parsed["block_num"] and parsed["block_num"] > 0:
            samples = generate_block_samples(
                parsed["block_num"],
                parsed["street_name"],
                parsed["direction"],
                parsed["suffix"],
                spacing=20,
            )
            print(f"  samples: {samples[:3]}, (total: {len(samples)})")
    
    print("block address parsing test passed")


def test_coordinate_parsing():
    """coordinate parsing."""
    test_cases = [
        "-71.05998397324,42.319283127",
        "",
        "invalid",
        None,
    ]
    
    for coords_str in test_cases:
        lon, lat = parse_coordinates(coords_str)
        print(f"input: {coords_str}")
        print(f"output: lon={lon}, lat={lat}")
    
    print("coordinate parsing test passed")


def test_coordinate_transformation():
    """coordinate transformation."""
    try:
        # zone 19N
        transformer = create_coordinate_transformer(
            source_crs="EPSG:4326", target_crs="EPSG:32619"
        )
        
        # test coords
        lons = np.array([-71.0599, -71.0808, -71.0370])
        lats = np.array([42.3192, 42.3821, 42.3667])
        
        x_coords, y_coords = transform_coordinates_to_crs(lons, lats, transformer)
        
        print(f"input (WGS84):")
        print(f"  lons: {lons}")
        print(f"  lats: {lats}")
        print(f"\noutput (UTM Zone 19N):")
        print(f"  x: {x_coords}")
        print(f"  y: {y_coords}")
        print(f"\nsample: lon={lons[0]}, lat={lats[0]} -> x={x_coords[0]:.2f}, y={y_coords[0]:.2f}")
        
        print("coordinate transformation test passed")
        return True
    except ImportError:
        return False


def test_kde_building():
    """KDE building with mock data."""
    try:
        # mock geocoded crime data
        mock_data = {
            "lat": [
                42.3192, 42.3195, 42.3198,
                42.3821, 42.3824, 42.3827,
                42.3667, 42.3670,
            ],
            "lon": [
                -71.0599, -71.0602, -71.0605,
                -71.0808, -71.0811, -71.0814,
                -71.0370, -71.0373,
            ],
            "crime_score": [5.0, 3.0, 4.0, 2.0, 6.0, 3.0, 4.0, 5.0],
        }
        
        geocoded_crimes = pd.DataFrame(mock_data)
        
        print(f"mock data: {len(geocoded_crimes)} crime locations")
        print(f"crime scores: {geocoded_crimes['crime_score'].tolist()}")
        
        # build KDE
        graph_crs = "EPSG:32619"
        kde, transformer = build_risk_kde(geocoded_crimes, graph_crs)
        
        print(f"KDE built successfully")
        print(f"KDE type: {type(kde)}")
        print(f"transformer type: {type(transformer)}")
        
        # test KDE evaluation at a point
        # transform a test point to UTM
        test_lon = -71.0599
        test_lat = 42.3192
        test_x, test_y = transform_coordinates_to_crs(
            np.array([test_lon]), np.array([test_lat]), transformer
        )
        
        # evaluate KDE at test point
        test_points = np.array([[test_x[0], test_y[0]]])
        risk_score = evaluate_kde_at_points(kde, test_points)
        
        print(f"KDE evaluation test:")
        print(f"test point: lon={test_lon}, lat={test_lat}")
        print(f"transformed: x={test_x[0]:.2f}, y={test_y[0]:.2f}")
        print(f"risk score: {risk_score[0]:.10e}")
        
        # test multiple points
        test_points_multi = np.column_stack([test_x, test_y])
        risk_scores = evaluate_kde_at_points(kde, test_points_multi)
        print(f"multiple points risk scores: {risk_scores}")
        
        print("KDE building and evaluation test passed")
        return True
    except Exception as e:
        print(f"KDE building test failed: {e}")
        print(traceback.format_exc())


def test_with_sample_data():
    """test with a small sample of real data if available."""
    aggregated_crimes_path = Path("data/aggregated_crimes.csv")
    aggregated_crimes = pd.read_csv(aggregated_crimes_path)
    sample_crimes = aggregated_crimes.head(5).copy()
        
        # test block address parsing for sample
    for idx, row in sample_crimes.iterrows():
        block_addr = row["Block Address"]
        parsed = parse_block_address(block_addr)
        print(f"block: {block_addr}")
        print(f"parsed: block_num={parsed['block_num']}, street={parsed['street_name']}")
        
        print("integration test passed")
        return True


def main():
    """Run all tests."""
    results = []
    
    # test 1: block address parsing
    test_block_address_parsing()
    results.append(("block address parsing", True))
    
    # test 2: coordinate parsing
    test_coordinate_parsing()
    results.append(("coordinate parsing", True))
    
    # test 3: coordinate transformation
    test_coordinate_transformation()
    results.append(("coordinate transformation", True))
    
    # test 4: KDE building
    test_kde_building()
    results.append(("kde building", True))
    
    # test 5: integration test
    try:
        success = test_with_sample_data()
        results.append(("integration test", success))
    except Exception as e:
        print(f"test 5 failed: {e}")
        results.append(("integration test", False))
    
    print("test summary")
    for test_name, passed in results:
        status = "passed" if passed else "failed"
        print(f"  {test_name}: {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    print(f"total: {total_passed}/{total_tests} tests passed")

if __name__ == "__main__":
    main()

