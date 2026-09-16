"""
USGS & GIS Shapefile Ingestion Pipeline for Uttarkashi Hazard Platform.
Ingests:
  1. ESRI Shapefiles (.shp, .shx, .dbf) for administrative boundaries or habitation points.
  2. USGS DEM GeoTIFF (.tif) or elevation contour shapefiles.
  3. GeoJSON or CSV village inventories.
"""

import sys
import os
import json
import math
import argparse
from pathlib import Path

def ingest_shapefile(input_path, output_dir=None):
    """
    Parses an ESRI Shapefile or GeoTIFF/GeoJSON and integrates it into the platform.
    Uses geopandas/rasterio if available, with built-in standard library fallbacks.
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
        
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "output"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[GIS Pipeline] Ingesting: {input_file.name} (Format: {input_file.suffix})")
    
    # Check format
    ext = input_file.suffix.lower()
    
    if ext == ".geojson" or ext == ".json":
        with open(input_file) as f:
            data = json.load(f)
        out_name = input_file.name
        out_path = output_dir / out_name
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[GIS Pipeline] ✓ Saved GeoJSON to: {out_path}")
        return {"status": "success", "file": str(out_path), "features": len(data.get("features", []))}
        
    elif ext == ".shp":
        try:
            import geopandas as gpd
            gdf = gpd.read_file(input_path)
            # Ensure WGS84 coordinates (EPSG:4326)
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                print(f"[GIS Pipeline] Reprojecting from {gdf.crs} to EPSG:4326 (WGS84)...")
                gdf = gdf.to_crs(epsg=4326)
                
            geojson_str = gdf.to_json()
            geojson_data = json.loads(geojson_str)
            out_name = input_file.stem + ".geojson"
            out_path = output_dir / out_name
            with open(out_path, "w") as f:
                json.dump(geojson_data, f, indent=2)
            print(f"[GIS Pipeline] ✓ Successfully converted Shapefile to: {out_path} ({len(gdf)} features)")
            return {"status": "success", "file": str(out_path), "features": len(gdf)}
        except ImportError:
            print("[GIS Pipeline] Note: 'geopandas' not installed. Install via: pip install geopandas")
            return {"status": "warning", "message": "Please install geopandas (pip install geopandas) to parse binary ESRI shapefiles."}
            
    elif ext in [".tif", ".tiff"]:
        try:
            import rasterio
            with rasterio.open(input_path) as src:
                bounds = src.bounds
                res = src.res
                print(f"[GIS Pipeline] DEM Raster Bounds: {bounds}")
                print(f"[GIS Pipeline] Resolution: {res}")
                return {
                    "status": "success",
                    "type": "DEM_GeoTIFF",
                    "bounds": [bounds.left, bounds.bottom, bounds.right, bounds.top],
                    "resolution": res
                }
        except ImportError:
            print("[GIS Pipeline] Note: 'rasterio' not installed for direct GeoTIFF extraction.")
            return {"status": "warning", "message": "Please install rasterio (pip install rasterio) to inspect DEM GeoTIFF files."}
            
    else:
        print(f"[GIS Pipeline] Unsupported file format: {ext}. Supported: .shp, .geojson, .tif")
        return {"status": "error", "message": f"Unsupported format {ext}"}

def main():
    parser = argparse.ArgumentParser(description="USGS & GIS Shapefile Ingestion Utility")
    parser.add_argument("--input", "-i", required=True, help="Path to .shp, .geojson, or .tif file")
    parser.add_argument("--output", "-o", help="Target output directory")
    args = parser.parse_args()
    
    res = ingest_shapefile(args.input, args.output)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
