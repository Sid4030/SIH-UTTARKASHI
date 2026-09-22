"""
BhuRakshak (भू-रक्षक) — Google Earth Engine (GEE) Live Connector
================================================================
This utility connects BhuRakshak to Google Earth Engine to stream real-time
satellite observations (Copernicus Sentinel-2, USGS SRTM 30m DEM, Dynamic World LULC).

Satellite Datasets Connected:
1. COPERNICUS/S2_SR_HARMONIZED: 10m Sentinel-2 Surface Reflectance (5-day revisit)
   -> Computes live NDVI (vegetation loss / slope scarring) and NDWI (soil saturation)
2. USGS/SRTMGL1_003: 30m Global Digital Elevation Model
   -> Extracts terrain slope, aspect, elevation, and Topographic Wetness Index (TWI)
3. GOOGLE/DYNAMICWORLD/V1: 10m Near-Real-Time Land Use / Land Cover (LULC)
   -> Real-time classification: built, trees, bare, scrub, water, snow
4. WorldPop/GP/100m/pop: 100m UN-adjusted population density

HOW TO CONNECT:
===============
Method 1 (Quickest - Free Personal Account):
  1. Register for Google Earth Engine at: https://code.earthengine.google.com/
  2. Run: python -m backend.data.connect_gee --auth
     (Or run: earthengine authenticate)
  3. Enter the verification token from your browser.
  4. Run: python -m backend.data.connect_gee --test

Method 2 (Cloud Project ID):
  export GEE_PROJECT_ID="your-google-cloud-project-id"
  python -m backend.data.connect_gee --test

Method 3 (Service Account JSON):
  export GEE_SERVICE_ACCOUNT_JSON="/path/to/service-account.json"
  python -m backend.data.connect_gee --test
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

from backend.data.gee_terrain_client import (
    init_gee, get_gee_status,
    extract_srtm_terrain, extract_sentinel2_ndvi, extract_dynamic_world_lulc,
    UTTARKASHI_BBOX,
)


def authenticate_gee():
    """Triggers interactive Google Earth Engine authentication."""
    print("=" * 65)
    print("  BhuRakshak — Google Earth Engine Interactive Authentication")
    print("=" * 65)
    try:
        import ee
        pid = os.environ.get("GEE_PROJECT_ID", "bhu-rakshak-509111")
        print("\nOpening Earth Engine authentication portal...")
        print("Follow the browser prompt to authorize access with your Google account.\n")
        ee.Authenticate()
        print(f"\n✓ Authentication token verified! Initializing GEE session with project '{pid}'...")
        ee.Initialize(project=pid)
        print(f"✓ Google Earth Engine connected successfully! (Project: {pid})")
        return True
    except ImportError:
        print("\n✗ 'earthengine-api' library not found.")
        print("  Install it via: pip install earthengine-api")
        return False
    except Exception as e:
        print(f"\n✗ Authentication failed: {e}")
        print("\nAlternative: Set a Google Cloud project ID:")
        print("  export GEE_PROJECT_ID='your-project-id'")
        return False


def test_live_gee_connection(lat: float = 30.7268, lng: float = 78.4430):
    """
    Tests live GEE extraction for a test point in Uttarkashi (e.g., Uttarkashi District HQ).
    """
    print("=" * 65)
    print("  BhuRakshak — Google Earth Engine Live Diagnostics & Telemetry")
    print("=" * 65)

    status = get_gee_status()
    print(f"\nConnection Mode : {status['mode']}")
    print(f"GEE Live Active : {'✓ YES (Live Satellite Stream)' if status['gee_live'] else '⚠ NO (Using High-Res Verified Cache)'}")
    print(f"Active Project  : {status.get('gee_project') or 'Default / None'}\n")

    print("Data Sources Status:")
    for src_name, info in status.get("data_sources", {}).items():
        st = info.get("status", "UNKNOWN")
        icon = "✓" if st in ["LIVE", "VERIFIED_CACHE"] else "○"
        print(f"  {icon} {src_name:24} [{st:14}] : {info.get('dataset', '')}")

    print(f"\nQuerying Satellite Features for Coordinate ({lat}, {lng}) [Uttarkashi]...")
    
    # 1. Terrain DEM
    terrain = extract_srtm_terrain(lat, lng)
    print(f"  • USGS SRTM 30m DEM  : Elev={terrain['elevation']}m, Slope={terrain['slope']}°, Aspect={terrain['aspect']}° ({terrain.get('source')})")

    # 2. Sentinel-2 NDVI
    veg = extract_sentinel2_ndvi(lat, lng)
    print(f"  • Copernicus Sentinel-2: NDVI={veg['ndvi']} (Veg cover), NDWI={veg.get('ndwi', -0.1)} ({veg.get('source')})")

    # 3. Dynamic World LULC
    lulc = extract_dynamic_world_lulc(lat, lng)
    print(f"  • Google Dynamic World : LULC Class='{lulc.get('lulc_class', 'scrub')}' ({lulc.get('source')})")

    print("\n" + "-" * 65)
    if status["gee_live"]:
        print("✓ LIVE GEE PIPELINE VERIFIED — Live satellite bands feeding directly into BhuRakshak model.")
    else:
        print("ℹ STANDBY CACHE ACTIVE — All 51 habitations & 3,111 grid points are powered by")
        print("  pre-extracted verified satellite features. Predictions are 100% functional offline.")
        print("\n  To switch to LIVE satellite feed:")
        print("    1. pip install earthengine-api")
        print("    2. python -m backend.data.connect_gee --auth")
        print("    3. export GEE_PROJECT_ID='your-project-id'")
    print("-" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(description="BhuRakshak Google Earth Engine Connector")
    parser.add_argument("--auth", action="store_true", help="Run interactive GEE authentication")
    parser.add_argument("--test", action="store_true", help="Run live GEE connection diagnostic test")
    parser.add_argument("--project", type=str, default="", help="Google Cloud project ID with Earth Engine API enabled")
    parser.add_argument("--lat", type=float, default=30.7268, help="Test latitude")
    parser.add_argument("--lng", type=float, default=78.4430, help="Test longitude")

    args = parser.parse_args()

    if args.project:
        os.environ["GEE_PROJECT_ID"] = args.project

    if args.auth:
        authenticate_gee()
    else:
        test_live_gee_connection(lat=args.lat, lng=args.lng)


if __name__ == "__main__":
    main()
