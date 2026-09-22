"""
Real Vector Data Pipeline — Uttarkashi Hazard Intelligence Platform
====================================================================
Loads and processes real geospatial vector datasets:

1. GADM Administrative Boundary (actual district polygon)
2. OpenStreetMap Road Network (real road connectivity)
3. OpenStreetMap / HydroSHEDS River Network (real drainage)
4. Census 2011 Village Locations (real village coordinates & population)
5. GSI/NASA Landslide Inventory (ground-truth for ML training)

All functions return GeoJSON FeatureCollections ready for frontend display.
"""

import json
import math
import csv
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

DATASETS_DIR = Path(__file__).parent / "datasets"
VECTORS_DIR = DATASETS_DIR / "vectors"
INVENTORY_DIR = DATASETS_DIR / "inventory"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

# Uttarkashi bounding box
BBOX = {
    "min_lat": 30.45, "max_lat": 31.45,
    "min_lon": 77.85, "max_lon": 79.05
}


def load_district_boundary() -> Optional[dict]:
    """
    Load the actual Uttarkashi district boundary from GADM or existing data.
    Returns GeoJSON FeatureCollection.
    """
    # Check for GADM extract
    gadm_path = VECTORS_DIR / "uttarkashi_boundary_gadm.geojson"
    if gadm_path.exists():
        with open(gadm_path) as f:
            data = json.load(f)
        print(f"  Boundary: Loaded GADM boundary ({len(data.get('features', []))} features)")
        return data

    # Check for full GADM India file and extract
    gadm_full = VECTORS_DIR / "gadm41_IND_3.json"
    if gadm_full.exists():
        print("  Boundary: Extracting Uttarkashi from full GADM...")
        return _extract_from_gadm(gadm_full)

    # Fallback: use existing output boundary
    existing = OUTPUT_DIR / "district_boundary.geojson"
    if existing.exists():
        with open(existing) as f:
            data = json.load(f)
        print("  Boundary: Using existing approximate boundary (not GADM)")
        return data

    print("  Boundary: No boundary data available")
    return None


def _extract_from_gadm(gadm_path: Path) -> Optional[dict]:
    """Extract Uttarkashi features from GADM India Level 3."""
    try:
        with open(gadm_path, encoding='utf-8') as f:
            data = json.load(f)

        uttarkashi = []
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            # GADM Level 3 naming varies — check multiple fields
            name_fields = [
                props.get("NAME_3", ""),
                props.get("NAME_2", ""),
                props.get("NL_NAME_3", ""),
                props.get("NL_NAME_2", ""),
            ]
            if any("uttarkashi" in n.lower() for n in name_fields if n):
                uttarkashi.append(feat)

        if uttarkashi:
            result = {"type": "FeatureCollection", "features": uttarkashi}
            # Cache the extract
            dest = VECTORS_DIR / "uttarkashi_boundary_gadm.geojson"
            with open(dest, "w") as f:
                json.dump(result, f)
            print(f"  Boundary: Extracted {len(uttarkashi)} features from GADM")
            return result
    except Exception as e:
        print(f"  Boundary: GADM extraction failed: {e}")

    return None


def load_road_network() -> Optional[dict]:
    """
    Load real road network from OpenStreetMap data.
    Returns GeoJSON FeatureCollection of road LineStrings within Uttarkashi.
    """
    # Check for pre-processed GeoJSON
    for path in [
        VECTORS_DIR / "uttarkashi_roads_osm.geojson",
        VECTORS_DIR / "uttarkashi_roads_osm.json",
    ]:
        if path.exists():
            return _load_and_filter_geojson(path, "roads")

    # Check for Overpass API JSON
    overpass_path = VECTORS_DIR / "uttarkashi_roads_osm.json"
    if overpass_path.exists():
        return _convert_overpass_to_geojson(overpass_path, "highway")

    # Check for OSM shapefile extract
    osm_dir = VECTORS_DIR / "osm_uttarakhand"
    road_shp = list(osm_dir.glob("*roads*")) if osm_dir.exists() else []
    if road_shp:
        return _load_shapefile(road_shp[0])

    print("  Roads: No road network data available. Using proximity-to-town estimation.")
    return None


def load_river_network() -> Optional[dict]:
    """
    Load real river/stream network from OSM or HydroSHEDS data.
    Returns GeoJSON FeatureCollection of river LineStrings.
    """
    for path in [
        VECTORS_DIR / "uttarkashi_rivers_osm.geojson",
        VECTORS_DIR / "uttarkashi_rivers_osm.json",
        VECTORS_DIR / "hydrorivers_uttarkashi.geojson",
    ]:
        if path.exists():
            return _load_and_filter_geojson(path, "rivers")

    # Check for Overpass API JSON
    overpass_path = VECTORS_DIR / "uttarkashi_rivers_osm.json"
    if overpass_path.exists():
        return _convert_overpass_to_geojson(overpass_path, "waterway")

    # Fallback: use existing hand-plotted rivers
    existing = OUTPUT_DIR / "rivers.geojson"
    if existing.exists():
        with open(existing) as f:
            data = json.load(f)
        print(f"  Rivers: Using existing rivers ({len(data.get('features', []))} segments)")
        return data

    print("  Rivers: No river data available")
    return None


def _load_and_filter_geojson(path: Path, layer_name: str) -> Optional[dict]:
    """Load a GeoJSON file and filter to Uttarkashi bounding box."""
    try:
        with open(path) as f:
            data = json.load(f)

        if data.get("type") == "FeatureCollection":
            filtered = []
            for feat in data.get("features", []):
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates", [])
                # Check if any coordinate falls within bbox
                if _geom_intersects_bbox(geom):
                    filtered.append(feat)

            if filtered:
                result = {"type": "FeatureCollection", "features": filtered}
                print(f"  {layer_name.title()}: Loaded {len(filtered)} features from {path.name}")
                return result

        print(f"  {layer_name.title()}: No features within bbox in {path.name}")
        return data  # Return all if filtering fails

    except Exception as e:
        print(f"  {layer_name.title()}: Failed to load {path.name}: {e}")
        return None


def _geom_intersects_bbox(geom: dict) -> bool:
    """Check if any coordinate in a geometry intersects the bounding box."""
    def check_coords(coords):
        if not coords:
            return False
        if isinstance(coords[0], (int, float)):
            lon, lat = coords[0], coords[1] if len(coords) > 1 else 0
            return (BBOX["min_lat"] <= lat <= BBOX["max_lat"] and
                    BBOX["min_lon"] <= lon <= BBOX["max_lon"])
        return any(check_coords(c) for c in coords)

    return check_coords(geom.get("coordinates", []))


def _convert_overpass_to_geojson(path: Path, key_tag: str) -> Optional[dict]:
    """Convert Overpass API JSON response to GeoJSON FeatureCollection."""
    try:
        with open(path) as f:
            data = json.load(f)

        features = []
        for element in data.get("elements", []):
            if element.get("type") == "way" and "geometry" in element:
                coords = [[pt["lon"], pt["lat"]] for pt in element["geometry"]]
                properties = element.get("tags", {})
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {
                        "name": properties.get("name", ""),
                        "type": properties.get(key_tag, "unknown"),
                        "osm_id": element.get("id"),
                    }
                })

        if features:
            result = {"type": "FeatureCollection", "features": features}
            # Save as GeoJSON for future use
            geojson_path = path.with_suffix('.geojson')
            with open(geojson_path, "w") as f:
                json.dump(result, f)
            print(f"  Converted {len(features)} Overpass elements to GeoJSON")
            return result

    except Exception as e:
        print(f"  Overpass conversion failed: {e}")
    return None


def _load_shapefile(path: Path) -> Optional[dict]:
    """Load a shapefile using geopandas and convert to GeoJSON."""
    try:
        import geopandas as gpd
        gdf = gpd.read_file(path)
        # Filter to Uttarkashi bbox
        gdf_filtered = gdf.cx[BBOX["min_lon"]:BBOX["max_lon"],
                              BBOX["min_lat"]:BBOX["max_lat"]]
        if len(gdf_filtered) > 0:
            result = json.loads(gdf_filtered.to_json())
            print(f"  Loaded {len(gdf_filtered)} features from {path.name}")
            return result
    except ImportError:
        print("  geopandas not available for shapefile loading")
    except Exception as e:
        print(f"  Shapefile loading failed: {e}")
    return None


def load_landslide_inventory() -> List[Dict[str, Any]]:
    """
    Load ground-truth landslide/disaster inventory for ML training.
    Returns list of verified disaster event dicts with lat/lon/type/year.
    """
    events = []

    # Priority 1: NASA Global Landslide Catalog extract
    nasa_path = INVENTORY_DIR / "uttarkashi_landslides_nasa.json"
    if nasa_path.exists():
        try:
            with open(nasa_path) as f:
                data = json.load(f)
            # Use Uttarkashi-specific events first, then wider Uttarakhand
            for event in data.get("uttarkashi", []):
                events.append({
                    "latitude": float(event.get("latitude", 0)),
                    "longitude": float(event.get("longitude", 0)),
                    "event_type": _normalize_event_type(event.get("landslide_trigger", "rainfall")),
                    "year": _extract_year(event.get("event_date", "")),
                    "name": event.get("event_title", "Unknown"),
                    "fatalities": int(event.get("fatality_count", 0) or 0),
                    "source": "NASA Global Landslide Catalog",
                    "is_verified": True,
                })
            if events:
                print(f"  Inventory: Loaded {len(events)} events from NASA catalog")
        except Exception as e:
            print(f"  Inventory: NASA catalog loading error: {e}")

    # Priority 2: Local verified inventory
    local_path = INVENTORY_DIR / "uttarkashi_landslides_local.json"
    if local_path.exists():
        try:
            with open(local_path) as f:
                local_events = json.load(f)
            for event in local_events:
                # Avoid duplicates by checking coordinates
                is_dup = any(
                    abs(e["latitude"] - event["latitude"]) < 0.01 and
                    abs(e["longitude"] - event["longitude"]) < 0.01 and
                    e.get("year") == event.get("year")
                    for e in events
                )
                if not is_dup:
                    events.append(event)
            print(f"  Inventory: Added local events, total: {len(events)}")
        except Exception as e:
            print(f"  Inventory: Local inventory loading error: {e}")

    # Priority 3: Fall back to hardcoded disaster sites
    if not events:
        from backend.data.generate_data import DISASTER_SITES
        for site in DISASTER_SITES:
            events.append({
                "latitude": site["lat"],
                "longitude": site["lng"],
                "event_type": site["type"],
                "year": site["year"],
                "name": site["name"],
                "fatalities": site["official_fatalities"],
                "source": site["statutory_source"],
                "is_verified": True,
            })
        print(f"  Inventory: Using {len(events)} hardcoded disaster events (fallback)")

    return events


def _normalize_event_type(trigger: str) -> str:
    """Normalize event type strings from various sources."""
    trigger = str(trigger).lower()
    if any(k in trigger for k in ["rain", "downpour", "monsoon", "cloudburst"]):
        return "cloudburst" if "cloud" in trigger else "flood"
    if any(k in trigger for k in ["slide", "slope", "debris", "mass"]):
        return "landslide"
    if any(k in trigger for k in ["flood", "inundation", "surge"]):
        return "flood"
    if any(k in trigger for k in ["earthquake", "seismic"]):
        return "earthquake"
    return "landslide"  # default


def _extract_year(date_str: str) -> int:
    """Extract year from various date formats."""
    if not date_str:
        return 2020
    try:
        # Try common formats
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y"]:
            try:
                from datetime import datetime
                return datetime.strptime(str(date_str)[:10], fmt).year
            except ValueError:
                continue
        # Try extracting 4-digit year
        import re
        match = re.search(r'(19|20)\d{2}', str(date_str))
        if match:
            return int(match.group())
    except Exception:
        pass
    return 2020


_RIVER_TREE = None
_RIVER_POINTS = None
_ROAD_TREE = None
_ROAD_POINTS = None

def _get_river_kdtree(river_data: dict):
    global _RIVER_TREE, _RIVER_POINTS
    if _RIVER_TREE is not None:
        return _RIVER_TREE
    if not river_data or "features" not in river_data:
        return None
    from scipy.spatial import cKDTree
    points = []
    for feat in river_data["features"]:
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        # GeoJSON could be LineString or MultiLineString
        def extract_coords(c):
            if not c:
                return
            if isinstance(c[0], (int, float)):
                points.append([c[1] * 111.0, c[0] * 95.0]) # lat_km, lon_km
            else:
                for sub in c:
                    extract_coords(sub)
        extract_coords(coords)
    if points:
        _RIVER_POINTS = np.array(points)
        _RIVER_TREE = cKDTree(_RIVER_POINTS)
    return _RIVER_TREE


def _get_road_kdtree(road_data: dict):
    global _ROAD_TREE, _ROAD_POINTS
    if _ROAD_TREE is not None:
        return _ROAD_TREE
    if not road_data or "features" not in road_data:
        return None
    from scipy.spatial import cKDTree
    points = []
    for feat in road_data["features"]:
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        def extract_coords(c):
            if not c:
                return
            if isinstance(c[0], (int, float)):
                points.append([c[1] * 111.0, c[0] * 95.0])
            else:
                for sub in c:
                    extract_coords(sub)
        extract_coords(coords)
    if points:
        _ROAD_POINTS = np.array(points)
        _ROAD_TREE = cKDTree(_ROAD_POINTS)
    return _ROAD_TREE


def compute_real_river_distance(lat: float, lon: float, river_data: dict = None) -> float:
    """
    Compute distance to nearest river/stream from real vector data using cKDTree index.
    Falls back to the hardcoded river approximation if no vector data available.
    """
    tree = _get_river_kdtree(river_data)
    if tree is not None:
        query_pt = [lat * 111.0, lon * 95.0]
        dist, _ = tree.query(query_pt)
        return float(dist)

    # Fallback to hardcoded rivers
    from backend.data.generate_data import distance_to_nearest_river
    return distance_to_nearest_river(lat, lon)


def compute_real_road_distance(lat: float, lon: float, road_data: dict = None) -> float:
    """
    Compute distance to nearest road from real OSM data using cKDTree index.
    Returns distance in km.
    """
    tree = _get_road_kdtree(road_data)
    if tree is not None:
        query_pt = [lat * 111.0, lon * 95.0]
        dist, _ = tree.query(query_pt)
        return float(dist)

    # Fallback: estimate from town distance
    return _estimate_road_distance_from_towns(lat, lon)


def _estimate_road_distance_from_towns(lat: float, lon: float) -> float:
    """
    Estimate road distance based on proximity to known highway network corridors:
    NH-108 (Bhagirathi corridor), NH-134 (Yamuna corridor), and SH-17 (Tons corridor).
    """
    corridor_nodes = [
        # NH-108 / NH-34 Bhagirathi Highway nodes
        (30.550, 78.310),  # Dharasu Junction
        (30.520, 78.240),  # Chinyalisaur
        (30.600, 78.380),  # Dunda
        (30.660, 78.420),  # Matli
        (30.727, 78.445),  # Uttarkashi Town
        (30.735, 78.480),  # Gangori
        (30.777, 78.543),  # Maneri
        (30.800, 78.585),  # Bhatwari
        (30.810, 78.630),  # Sukhi
        (30.850, 78.650),  # Jhala
        (31.036, 78.738),  # Harsil
        (31.023, 78.784),  # Dharali
        (30.780, 78.510),  # Lanka
        (30.995, 78.940),  # Gangotri
        # NH-134 Yamunotri Highway nodes
        (30.614, 78.355),  # Barkot
        (30.700, 78.500),  # Naugaon
        (30.670, 78.520),  # Kharadi
        (30.650, 78.550),  # Rajgarhi
        (30.985, 78.442),  # Janki Chatti
        (30.990, 78.450),  # Kharsali
        # SH-17 Tons Valley Road nodes
        (30.850, 78.100),  # Purola
        (31.100, 78.100),  # Mori
        (31.050, 78.150),  # Netwar
        (31.082, 78.185),  # Sankri
    ]
    min_dist = float('inf')
    for t_lat, t_lon in corridor_nodes:
        dlat = (lat - t_lat) * 111.0
        dlon = (lon - t_lon) * 95.0
        dist = math.sqrt(dlat**2 + dlon**2)
        min_dist = min(min_dist, dist)
    return round(float(min_dist), 2)


def load_census_villages() -> List[Dict[str, Any]]:
    """
    Load real Census 2011 village data for Uttarkashi.
    Falls back to the known villages list if no Census data available.
    """
    # Check for Census CSV
    census_paths = [
        VECTORS_DIR / "uttarkashi_villages_census2011.csv",
        VECTORS_DIR / "census_villages.csv",
    ]

    for path in census_paths:
        if path.exists():
            try:
                villages = []
                with open(path, encoding='utf-8', errors='replace') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            lat = float(row.get("latitude", 0) or 0)
                            lon = float(row.get("longitude", 0) or 0)
                            pop = int(row.get("population", 0) or 0)
                            if lat > 0 and lon > 0 and pop > 0:
                                villages.append({
                                    "name": row.get("village_name", row.get("name", "Unknown")),
                                    "tehsil": row.get("tehsil", row.get("sub_district", "")),
                                    "lat": lat,
                                    "lng": lon,
                                    "pop": pop,
                                    "is_town": pop > 5000,
                                    "census_code": row.get("census_code", ""),
                                })
                        except (ValueError, TypeError):
                            continue
                if villages:
                    print(f"  Villages: Loaded {len(villages)} from Census CSV")
                    return villages
            except Exception as e:
                print(f"  Villages: Census CSV loading error: {e}")

    # Fallback: use existing known villages
    from backend.data.generate_data import KNOWN_VILLAGES
    print(f"  Villages: Using {len(KNOWN_VILLAGES)} known villages (Census data not found)")
    return KNOWN_VILLAGES


def get_vector_status() -> Dict[str, Any]:
    """Get status of all vector data sources."""
    return {
        "boundary": {
            "available": any([
                (VECTORS_DIR / "uttarkashi_boundary_gadm.geojson").exists(),
                (VECTORS_DIR / "gadm41_IND_3.json").exists(),
                (OUTPUT_DIR / "district_boundary.geojson").exists(),
            ]),
            "source": "GADM" if (VECTORS_DIR / "uttarkashi_boundary_gadm.geojson").exists()
                      else "Approximate" if (OUTPUT_DIR / "district_boundary.geojson").exists()
                      else "None"
        },
        "roads": {
            "available": any([
                (VECTORS_DIR / "uttarkashi_roads_osm.json").exists(),
                (VECTORS_DIR / "uttarkashi_roads_osm.geojson").exists(),
            ]),
            "source": "OpenStreetMap" if any([
                (VECTORS_DIR / "uttarkashi_roads_osm.json").exists(),
                (VECTORS_DIR / "uttarkashi_roads_osm.geojson").exists(),
            ]) else "Town-Distance Estimation"
        },
        "rivers": {
            "available": any([
                (VECTORS_DIR / "uttarkashi_rivers_osm.json").exists(),
                (VECTORS_DIR / "uttarkashi_rivers_osm.geojson").exists(),
                (OUTPUT_DIR / "rivers.geojson").exists(),
            ]),
            "source": "OpenStreetMap" if any([
                (VECTORS_DIR / "uttarkashi_rivers_osm.json").exists(),
            ]) else "Hand-plotted" if (OUTPUT_DIR / "rivers.geojson").exists() else "None"
        },
        "inventory": {
            "available": any([
                (INVENTORY_DIR / "uttarkashi_landslides_nasa.json").exists(),
                (INVENTORY_DIR / "uttarkashi_landslides_local.json").exists(),
            ]),
            "source": "NASA+Local" if (INVENTORY_DIR / "uttarkashi_landslides_nasa.json").exists()
                      else "Local" if (INVENTORY_DIR / "uttarkashi_landslides_local.json").exists()
                      else "Hardcoded"
        },
        "villages": {
            "available": any([
                (VECTORS_DIR / "uttarkashi_villages_census2011.csv").exists(),
            ]),
            "source": "Census 2011" if (VECTORS_DIR / "uttarkashi_villages_census2011.csv").exists()
                      else "Known Villages List"
        }
    }


if __name__ == "__main__":
    print("=" * 60)
    print("VECTOR DATA PIPELINE — DIAGNOSTICS")
    print("=" * 60)

    status = get_vector_status()
    for layer, info in status.items():
        symbol = "✓" if info["available"] else "✗"
        print(f"\n  {symbol} {layer.upper()}: {info['source']}")

    print("\n  Loading inventory...")
    inventory = load_landslide_inventory()
    print(f"  Total disaster events: {len(inventory)}")
    for event in inventory[:5]:
        print(f"    • {event['name']} ({event['year']}) @ {event['latitude']:.3f}, {event['longitude']:.3f}")
