"""
BhuRakshak (भू-रक्षक) — Google Earth Engine Live Tile & Telemetry Service
=======================================================================
Generates live MapIDs and XYZ raster tile endpoints from Google Earth Engine
to stream high-resolution satellite imagery directly into MapLibre GL JS:
1. Copernicus Sentinel-2 True Color (10m optical surface reflectance)
2. Copernicus Sentinel-2 NDVI (Vegetation vigor & debris scarp detection)
3. Google Dynamic World (10m near-real-time Land Use / Land Cover)
4. USGS SRTM 30m Topographic Hillshade & Slope
"""

import os
import time
from typing import Dict, Any, Optional

_TILE_CACHE: Dict[str, Any] = {}
_CACHE_TIMESTAMP = 0.0
_CACHE_TTL = 7200.0  # 2 hours cache for Earth Engine MapIDs


def get_gee_tile_layers(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Returns live Google Earth Engine tile URL endpoints for MapLibre GL JS.
    Earth Engine generates secure XYZ raster tiles streamed directly from Google's
    supercomputing clusters to the browser.
    """
    global _TILE_CACHE, _CACHE_TIMESTAMP
    now = time.time()
    
    if not force_refresh and _TILE_CACHE and (now - _CACHE_TIMESTAMP) < _CACHE_TTL:
        return _TILE_CACHE

    pid = os.environ.get("GEE_PROJECT_ID", "bhu-rakshak-509111")
    
    try:
        import ee
        try:
            ee.Initialize(project=pid)
        except Exception:
            pass  # May already be initialized

        # Uttarkashi Bounding Box Geometry
        bbox = ee.Geometry.BBox(77.85, 30.35, 79.15, 31.30)
        center_pt = ee.Geometry.Point([78.4430, 30.7268])

        # 1. Copernicus Sentinel-2 Harmonized (Latest cloud-screened mosaic)
        s2_collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(center_pt)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
            .sort("system:time_start", False)
        )
        s2_image = s2_collection.first()

        # True Color RGB (B4=Red, B3=Green, B2=Blue)
        rgb_vis = {
            "bands": ["B4", "B3", "B2"],
            "min": 0,
            "max": 3000,
            "gamma": 1.4
        }
        s2_map = s2_image.getMapId(rgb_vis)
        tile_url_rgb = s2_map["tile_fetcher"].url_format

        # 2. Sentinel-2 Normalized Difference Vegetation Index (NDVI)
        ndvi = s2_image.normalizedDifference(["B8", "B4"]).rename("ndvi")
        ndvi_vis = {
            "min": 0.0,
            "max": 0.8,
            "palette": [
                "#d73027", "#f46d43", "#fdae61", "#fee08b",
                "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850"
            ]
        }
        ndvi_map = ndvi.getMapId(ndvi_vis)
        tile_url_ndvi = ndvi_map["tile_fetcher"].url_format

        # 3. USGS SRTM 30m Hillshade & Slope
        srtm = ee.Image("USGS/SRTMGL1_003")
        hillshade = ee.Terrain.hillshade(srtm)
        hs_vis = {"min": 0, "max": 255}
        hs_map = hillshade.getMapId(hs_vis)
        tile_url_hs = hs_map["tile_fetcher"].url_format

        # 4. Google Dynamic World (10m Near-Real-Time LULC)
        dw = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
            .filterBounds(center_pt)
            .filterDate("2024-01-01", "2024-12-31")
            .select("label")
            .mode()
        )
        dw_vis = {
            "min": 0,
            "max": 8,
            "palette": [
                "#419BDF",  # 0: water (blue)
                "#397D49",  # 1: trees (forest green)
                "#88B053",  # 2: grass (light green)
                "#7A87C6",  # 3: flooded_vegetation
                "#E49635",  # 4: crops (orange)
                "#DFC35A",  # 5: scrub (khaki)
                "#C4281B",  # 6: built (red)
                "#A59B8F",  # 7: bare (brown)
                "#B39FE1"   # 8: snow_ice (purple/white)
            ]
        }
        dw_map = dw.getMapId(dw_vis)
        tile_url_dw = dw_map["tile_fetcher"].url_format

        result = {
            "status": "online",
            "provider": "Google Earth Engine",
            "project_id": pid,
            "cached_at": now,
            "layers": {
                "sentinel2_rgb": {
                    "id": "sentinel2_rgb",
                    "name": "Sentinel-2 Optical (10m True Color)",
                    "description": "Copernicus 10m surface reflectance (revisit every 5 days)",
                    "tile_url": tile_url_rgb,
                    "attribution": "ESA Copernicus / Google Earth Engine",
                    "type": "raster",
                    "default_opacity": 0.85
                },
                "sentinel2_ndvi": {
                    "id": "sentinel2_ndvi",
                    "name": "Sentinel-2 NDVI (Vegetation & Scarring)",
                    "description": "Normalized Difference Vegetation Index (identifies slope scarification)",
                    "tile_url": tile_url_ndvi,
                    "attribution": "ESA Copernicus / Google Earth Engine",
                    "type": "raster",
                    "default_opacity": 0.75
                },
                "dynamic_world": {
                    "id": "dynamic_world",
                    "name": "Dynamic World Real-Time LULC (10m)",
                    "description": "Google & WRI near-real-time 10m AI land cover classification",
                    "tile_url": tile_url_dw,
                    "attribution": "Google / WRI / Dynamic World",
                    "type": "raster",
                    "default_opacity": 0.70
                },
                "srtm_hillshade": {
                    "id": "srtm_hillshade",
                    "name": "USGS SRTM 30m Hillshade",
                    "description": "Topographic hillshade revealing ridges, gorges, and valley floors",
                    "tile_url": tile_url_hs,
                    "attribution": "USGS / NASA / Google Earth Engine",
                    "type": "raster",
                    "default_opacity": 0.65
                }
            }
        }
        _TILE_CACHE = result
        _CACHE_TIMESTAMP = now
        return result

    except Exception as e:
        print(f"⚠ GEE live tile generation notice: {e}")
        # Return fallback high-res open satellite/terrain endpoints
        return {
            "status": "fallback_online",
            "provider": "Esri / OpenStreetMap (GEE Quota Fallback)",
            "project_id": pid,
            "error_detail": str(e),
            "layers": {
                "sentinel2_rgb": {
                    "id": "sentinel2_rgb",
                    "name": "High-Res Satellite (World Imagery)",
                    "description": "High-resolution satellite imagery fallback",
                    "tile_url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                    "attribution": "Esri, Maxar, Earthstar Geographics",
                    "type": "raster",
                    "default_opacity": 0.85
                },
                "srtm_hillshade": {
                    "id": "srtm_hillshade",
                    "name": "Shaded Relief Terrain",
                    "description": "Topographic shaded relief fallback",
                    "tile_url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}",
                    "attribution": "Esri, USGS",
                    "type": "raster",
                    "default_opacity": 0.65
                }
            }
        }
