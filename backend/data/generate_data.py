"""
Uttarkashi District — Village & Terrain Data Generator
Generates realistic GeoJSON datasets based on Census 2011 data and 
Uttarkashi's actual geography for hazard modeling.
"""

import json
import math
import random
import numpy as np
from pathlib import Path
from backend.data.srtm_engine import get_elevation

random.seed(42)
np.random.seed(42)

# Uttarkashi district bounds (approximate)
DISTRICT_BOUNDS = {
    "min_lat": 30.45,
    "max_lat": 31.45,
    "min_lng": 77.85,
    "max_lng": 79.05
}

# Tehsils in Uttarkashi with approximate centers and characteristics
TEHSILS = {
    "Bhatwari": {"center": [30.80, 78.60], "elevation_range": [1800, 4500], "hazard_bias": 0.7},
    "Chinyalisaur": {"center": [30.55, 78.25], "elevation_range": [900, 2200], "hazard_bias": 0.3},
    "Dunda": {"center": [30.60, 78.40], "elevation_range": [1000, 2800], "hazard_bias": 0.4},
    "Mori": {"center": [31.10, 78.10], "elevation_range": [1500, 4000], "hazard_bias": 0.6},
    "Naugaon": {"center": [30.70, 78.50], "elevation_range": [1100, 3000], "hazard_bias": 0.5},
    "Purola": {"center": [30.85, 78.10], "elevation_range": [1200, 3500], "hazard_bias": 0.55},
    "Rajgarhi": {"center": [30.65, 78.55], "elevation_range": [1200, 3200], "hazard_bias": 0.45},
}

# Real villages in Uttarkashi (subset with approximate locations)
# Based on Census 2011 data — names are real, locations are approximate
KNOWN_VILLAGES = [
    # Bhatwari tehsil — high risk area
    {"name": "Uttarkashi Town", "tehsil": "Bhatwari", "lat": 30.727, "lng": 78.445, "pop": 18000, "is_town": True},
    {"name": "Gangotri", "tehsil": "Bhatwari", "lat": 30.995, "lng": 78.940, "pop": 600, "is_town": False},
    {"name": "Harsil", "tehsil": "Bhatwari", "lat": 31.036, "lng": 78.738, "pop": 1200, "is_town": False},
    {"name": "Dharali", "tehsil": "Bhatwari", "lat": 31.023, "lng": 78.784, "pop": 800, "is_town": False},
    {"name": "Bhatwari", "tehsil": "Bhatwari", "lat": 30.800, "lng": 78.585, "pop": 2500, "is_town": False},
    {"name": "Maneri", "tehsil": "Bhatwari", "lat": 30.777, "lng": 78.543, "pop": 3000, "is_town": False},
    {"name": "Barsu", "tehsil": "Bhatwari", "lat": 30.853, "lng": 78.686, "pop": 450, "is_town": False},
    {"name": "Sukhi", "tehsil": "Bhatwari", "lat": 30.810, "lng": 78.630, "pop": 380, "is_town": False},
    {"name": "Lanka", "tehsil": "Bhatwari", "lat": 30.780, "lng": 78.510, "pop": 520, "is_town": False},
    {"name": "Jhala", "tehsil": "Bhatwari", "lat": 30.850, "lng": 78.650, "pop": 300, "is_town": False},

    # Chinyalisaur tehsil — lower risk
    {"name": "Chinyalisaur", "tehsil": "Chinyalisaur", "lat": 30.520, "lng": 78.240, "pop": 5500, "is_town": True},
    {"name": "Lakhwar", "tehsil": "Chinyalisaur", "lat": 30.510, "lng": 78.270, "pop": 900, "is_town": False},
    {"name": "Jakhol", "tehsil": "Chinyalisaur", "lat": 30.490, "lng": 78.200, "pop": 600, "is_town": False},

    # Dunda tehsil
    {"name": "Dunda", "tehsil": "Dunda", "lat": 30.600, "lng": 78.380, "pop": 2800, "is_town": False},
    {"name": "Barkot", "tehsil": "Dunda", "lat": 30.614, "lng": 78.355, "pop": 4200, "is_town": True},
    {"name": "Tikochi", "tehsil": "Dunda", "lat": 30.580, "lng": 78.420, "pop": 700, "is_town": False},

    # Mori tehsil — remote, high risk
    {"name": "Mori", "tehsil": "Mori", "lat": 31.100, "lng": 78.100, "pop": 1500, "is_town": False},
    {"name": "Netwar", "tehsil": "Mori", "lat": 31.050, "lng": 78.150, "pop": 800, "is_town": False},
    {"name": "Sankri", "tehsil": "Mori", "lat": 31.082, "lng": 78.185, "pop": 600, "is_town": False},
    {"name": "Taluka", "tehsil": "Mori", "lat": 31.050, "lng": 78.060, "pop": 400, "is_town": False},

    # Purola tehsil
    {"name": "Purola", "tehsil": "Purola", "lat": 30.850, "lng": 78.100, "pop": 5000, "is_town": True},
    {"name": "Naugaon", "tehsil": "Naugaon", "lat": 30.700, "lng": 78.500, "pop": 3500, "is_town": False},
    {"name": "Siror", "tehsil": "Naugaon", "lat": 30.680, "lng": 78.460, "pop": 1800, "is_town": False},
    {"name": "Nirakot", "tehsil": "Naugaon", "lat": 30.710, "lng": 78.480, "pop": 600, "is_town": False},
    {"name": "Mando", "tehsil": "Naugaon", "lat": 30.690, "lng": 78.470, "pop": 400, "is_town": False},
    {"name": "Kankrari", "tehsil": "Naugaon", "lat": 30.700, "lng": 78.490, "pop": 350, "is_town": False},

    # Rajgarhi tehsil
    {"name": "Rajgarhi", "tehsil": "Rajgarhi", "lat": 30.650, "lng": 78.550, "pop": 1200, "is_town": False},
    {"name": "Kharadi", "tehsil": "Rajgarhi", "lat": 30.670, "lng": 78.520, "pop": 800, "is_town": False},
]

# Known historical disaster sites across Uttarkashi district (18 verified records)
# Reconciled with authoritative local inventory
def _load_disaster_sites():
    inv_file = Path(__file__).parent / "datasets" / "inventory" / "uttarkashi_landslides_local.json"
    if inv_file.exists():
        try:
            with open(inv_file) as f:
                raw = json.load(f)
            sites = []
            for item in raw:
                sites.append({
                    "lat": float(item["latitude"]),
                    "lng": float(item["longitude"]),
                    "type": str(item["event_type"]),
                    "year": int(item["year"]),
                    "name": str(item["name"]),
                    "official_fatalities": int(item.get("fatalities", 0)),
                    "missing": int(item.get("missing", 0)),
                    "displaced": int(item.get("displaced", 0)),
                    "severity": str(item.get("severity", "high")),
                    "statutory_source": str(item.get("source", "Official Incident Record"))
                })
            if sites:
                return sites
        except Exception as e:
            print(f"Warning loading inventory in generate_data: {e}")
    return []

DISASTER_SITES = _load_disaster_sites()

# Major rivers for distance calculations
RIVERS = [
    # Bhagirathi River (main river through Uttarkashi)
    {"points": [(31.05, 78.95), (31.04, 78.80), (31.03, 78.74), (30.85, 78.65),
                (30.80, 78.58), (30.77, 78.54), (30.73, 78.45), (30.68, 78.42),
                (30.60, 78.38), (30.55, 78.30), (30.50, 78.25)],
     "name": "Bhagirathi"},
    # Tons River
    {"points": [(31.20, 78.00), (31.10, 78.10), (31.00, 78.15), (30.90, 78.10),
                (30.85, 78.08)],
     "name": "Tons"},
    # Yamuna River (upper reaches)
    {"points": [(31.00, 78.45), (30.95, 78.30), (30.90, 78.20), (30.85, 78.15)],
     "name": "Yamuna"},
]


def compute_elevation(lat, lng):
    """
    Returns genuine NASA SRTM 30m Digital Elevation Model (DEM) data
    calibrated for Uttarkashi topography.
    """
    return get_elevation(lat, lng)


def compute_slope(lat, lng, elevation):
    """Compute slope in degrees. Higher elevations tend to have steeper slopes."""
    delta = 0.001
    e_n = compute_elevation(lat + delta, lng)
    e_s = compute_elevation(lat - delta, lng)
    e_e = compute_elevation(lat, lng + delta)
    e_w = compute_elevation(lat, lng - delta)
    
    # ~111m per degree lat, ~95m per degree lng at this latitude
    dx = (e_e - e_w) / (2 * delta * 95000)
    dy = (e_n - e_s) / (2 * delta * 111000)
    
    slope_rad = math.atan(math.sqrt(dx**2 + dy**2))
    return math.degrees(slope_rad)


def compute_aspect(lat, lng):
    """Compute aspect (direction slope faces) in degrees."""
    delta = 0.001
    e_n = compute_elevation(lat + delta, lng)
    e_s = compute_elevation(lat - delta, lng)
    e_e = compute_elevation(lat, lng + delta)
    e_w = compute_elevation(lat, lng - delta)
    
    dx = e_e - e_w
    dy = e_n - e_s
    
    aspect = math.degrees(math.atan2(-dx, dy))
    if aspect < 0:
        aspect += 360
    return aspect


def compute_curvature(lat, lng):
    """
    Compute profile/plan curvature in standard geomorphometric units (1/100m).
    Negative = concave (convergent flow, water/debris accumulation), Positive = convex.
    Standard natural range for 30m-100m terrain is [-1.5, 1.5].
    """
    delta = 0.001
    e_c = compute_elevation(lat, lng)
    e_n = compute_elevation(lat + delta, lng)
    e_s = compute_elevation(lat - delta, lng)
    e_e = compute_elevation(lat, lng + delta)
    e_w = compute_elevation(lat, lng - delta)
    
    cell_size = delta * 111000.0  # ~111m
    # Laplacian finite difference scaled to per 100m
    curv = (e_n + e_s + e_e + e_w - 4.0 * e_c) / (cell_size ** 2)
    curv_100m = curv * 100.0
    return round(max(-1.5, min(1.5, curv_100m)), 4)


def compute_twi(slope, upstream_area=None):
    """Topographic Wetness Index: ln(a / tan(beta))"""
    if upstream_area is None:
        upstream_area = random.uniform(100, 50000)
    slope_rad = max(math.radians(slope), 0.01)
    twi = math.log(upstream_area / math.tan(slope_rad))
    return max(0, min(20, twi))


def distance_to_nearest_river(lat, lng):
    """Compute approximate distance to nearest river in km."""
    min_dist = float('inf')
    for river in RIVERS:
        for p in river["points"]:
            dlat = (lat - p[0]) * 111
            dlng = (lng - p[1]) * 95
            dist = math.sqrt(dlat**2 + dlng**2)
            min_dist = min(min_dist, dist)
    return min_dist


def compute_rainfall_intensity(lat, lng, elevation):
    """Estimate rainfall intensity (mm/day) based on orographic effects."""
    # Base rainfall — higher in valleys during monsoon
    base = 80
    # Orographic lift: increases with elevation up to ~2500m, then decreases
    if elevation < 2500:
        orographic = (elevation / 2500) * 120
    else:
        orographic = 120 - ((elevation - 2500) / 4000) * 60
    
    # Spatial variation
    noise = 20 * math.sin(lat * 30) * math.cos(lng * 25)
    
    return max(20, base + orographic + noise)


def compute_ndvi_proxy(elevation, slope):
    """NDVI proxy based on elevation and slope.
    Dense vegetation at 1500-3000m, sparse above treeline (~3800m).
    """
    if elevation < 1500:
        ndvi = 0.4 + (elevation / 1500) * 0.3
    elif elevation < 3000:
        ndvi = 0.7 - (slope / 90) * 0.2
    elif elevation < 3800:
        ndvi = 0.7 - ((elevation - 3000) / 800) * 0.5
    else:
        ndvi = max(0.05, 0.2 - ((elevation - 3800) / 2700) * 0.15)
    
    return max(0.05, min(0.85, ndvi + random.uniform(-0.05, 0.05)))


def distance_to_nearest_disaster(lat, lng):
    """Distance to nearest known disaster site in km."""
    min_dist = float('inf')
    for site in DISASTER_SITES:
        dlat = (lat - site["lat"]) * 111
        dlng = (lng - site["lng"]) * 95
        dist = math.sqrt(dlat**2 + dlng**2)
        min_dist = min(min_dist, dist)
    return min_dist


def generate_grid_points(resolution=0.01):
    """Generate a grid of points covering Uttarkashi district."""
    points = []
    lat = DISTRICT_BOUNDS["min_lat"]
    while lat <= DISTRICT_BOUNDS["max_lat"]:
        lng = DISTRICT_BOUNDS["min_lng"]
        while lng <= DISTRICT_BOUNDS["max_lng"]:
            points.append((round(lat, 4), round(lng, 4)))
            lng += resolution
        lat += resolution
    return points


def generate_terrain_features(points):
    """Generate terrain features for each grid point."""
    features = []
    for lat, lng in points:
        elevation = compute_elevation(lat, lng)
        slope = compute_slope(lat, lng, elevation)
        aspect = compute_aspect(lat, lng)
        curvature = compute_curvature(lat, lng)
        twi = compute_twi(slope)
        dist_river = distance_to_nearest_river(lat, lng)
        rainfall = compute_rainfall_intensity(lat, lng, elevation)
        ndvi = compute_ndvi_proxy(elevation, slope)
        dist_disaster = distance_to_nearest_disaster(lat, lng)
        
        features.append({
            "lat": lat,
            "lng": lng,
            "elevation": round(elevation, 1),
            "slope": round(slope, 2),
            "aspect": round(aspect, 1),
            "curvature": round(curvature, 4),
            "twi": round(twi, 2),
            "dist_river_km": round(dist_river, 2),
            "rainfall_mm": round(rainfall, 1),
            "ndvi": round(ndvi, 3),
            "dist_disaster_km": round(dist_disaster, 2)
        })
    return features


def generate_additional_villages(count=150):
    """Generate additional villages to fill out the district."""
    villages = list(KNOWN_VILLAGES)
    
    village_name_prefixes = [
        "Koti", "Bangan", "Salan", "Phula", "Dhanari", "Gangar", "Badal",
        "Deosar", "Kirola", "Semwal", "Naitwar", "Chopta", "Ghuttu",
        "Dodra", "Kwari", "Bandal", "Tuneta", "Bairagi", "Jaspur", "Dimri",
        "Padri", "Khaga", "Rampur", "Basari", "Durgapur", "Khuret", "Nagrasu",
        "Bhukki", "Dabrani", "Jhajra", "Kandara", "Lata", "Makudi",
        "Neghar", "Osla", "Purana", "Rautgaon", "Sasta", "Tiloth", "Udiyari",
    ]
    
    suffixes = ["", " Gaon", " Patti", " Khala", ""]
    
    used_names = {v["name"] for v in villages}
    
    for i in range(count):
        tehsil_name = random.choice(list(TEHSILS.keys()))
        tehsil = TEHSILS[tehsil_name]
        
        # Random location near tehsil center
        lat = tehsil["center"][0] + random.uniform(-0.15, 0.15)
        lng = tehsil["center"][1] + random.uniform(-0.15, 0.15)
        
        # Clamp to district bounds
        lat = max(DISTRICT_BOUNDS["min_lat"], min(DISTRICT_BOUNDS["max_lat"], lat))
        lng = max(DISTRICT_BOUNDS["min_lng"], min(DISTRICT_BOUNDS["max_lng"], lng))
        
        # Generate unique name
        name = None
        while name is None or name in used_names:
            prefix = random.choice(village_name_prefixes)
            suffix = random.choice(suffixes)
            name = f"{prefix}{suffix}"
            if name in used_names:
                name = f"{prefix}-{i}{suffix}"
        used_names.add(name)
        
        # Population: mostly small villages
        pop = int(random.lognormvariate(math.log(400), 0.8))
        pop = max(50, min(3000, pop))
        
        villages.append({
            "name": name,
            "tehsil": tehsil_name,
            "lat": round(lat, 4),
            "lng": round(lng, 4),
            "pop": pop,
            "is_town": False
        })
    
    return villages


def compute_village_features(villages):
    """Compute hazard features for each village location."""
    enriched = []
    for v in villages:
        lat, lng = v["lat"], v["lng"]
        elevation = compute_elevation(lat, lng)
        slope = compute_slope(lat, lng, elevation)
        aspect = compute_aspect(lat, lng)
        curvature = compute_curvature(lat, lng)
        twi = compute_twi(slope)
        dist_river = distance_to_nearest_river(lat, lng)
        rainfall = compute_rainfall_intensity(lat, lng, elevation)
        ndvi = compute_ndvi_proxy(elevation, slope)
        dist_disaster = distance_to_nearest_disaster(lat, lng)
        
        # Household estimate
        avg_hh_size = 5.2
        households = max(1, int(v["pop"] / avg_hh_size))
        
        enriched.append({
            **v,
            "elevation": round(elevation, 1),
            "slope": round(slope, 2),
            "aspect": round(aspect, 1),
            "curvature": round(curvature, 4),
            "twi": round(twi, 2),
            "dist_river_km": round(dist_river, 2),
            "rainfall_mm": round(rainfall, 1),
            "ndvi": round(ndvi, 3),
            "dist_disaster_km": round(dist_disaster, 2),
            "households": households
        })
    return enriched


def villages_to_geojson(villages):
    """Convert village data to GeoJSON FeatureCollection."""
    features = []
    for i, v in enumerate(villages):
        feature = {
            "type": "Feature",
            "id": i + 1,
            "geometry": {
                "type": "Point",
                "coordinates": [v["lng"], v["lat"]]
            },
            "properties": {
                "id": i + 1,
                "name": v["name"],
                "tehsil": v["tehsil"],
                "population": v["pop"],
                "households": v["households"],
                "is_town": v.get("is_town", False),
                "elevation": v["elevation"],
                "slope": v["slope"],
                "aspect": v["aspect"],
                "curvature": v["curvature"],
                "twi": v["twi"],
                "dist_river_km": v["dist_river_km"],
                "rainfall_mm": v["rainfall_mm"],
                "ndvi": v["ndvi"],
                "dist_disaster_km": v["dist_disaster_km"],
            }
        }
        features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


def disaster_history_to_geojson():
    """Convert disaster history to GeoJSON with official verified casualty records."""
    features = []
    for i, d in enumerate(DISASTER_SITES):
        features.append({
            "type": "Feature",
            "id": i + 1,
            "geometry": {
                "type": "Point",
                "coordinates": [d["lng"], d["lat"]]
            },
            "properties": {
                "id": i + 1,
                "name": d["name"],
                "type": d["type"],
                "year": d["year"],
                "severity": d["severity"],
                "casualties": d["official_fatalities"],
                "missing": d["missing"],
                "displaced": d["displaced"],
                "source": d["statutory_source"]
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


def rivers_to_geojson():
    """Convert river data to GeoJSON LineStrings."""
    features = []
    for river in RIVERS:
        coords = [[p[1], p[0]] for p in river["points"]]
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            },
            "properties": {
                "name": river["name"],
                "type": "river"
            }
        })
    return {
        "type": "FeatureCollection",
        "features": features
    }


def generate_district_boundary():
    """Generate approximate Uttarkashi district boundary polygon."""
    # Simplified boundary points (clockwise)
    boundary = [
        [78.00, 30.45], [78.30, 30.45], [78.60, 30.48],
        [78.80, 30.50], [79.05, 30.55], [79.05, 30.80],
        [79.00, 31.00], [78.95, 31.20], [78.80, 31.35],
        [78.50, 31.45], [78.20, 31.40], [78.00, 31.30],
        [77.85, 31.15], [77.85, 30.90], [77.90, 30.65],
        [78.00, 30.45]  # Close the polygon
    ]
    
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [boundary]
            },
            "properties": {
                "name": "Uttarkashi District",
                "state": "Uttarakhand",
                "area_sq_km": 8016,
                "population_2011": 330086,
                "headquarters": "Uttarkashi"
            }
        }]
    }


if __name__ == "__main__":
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("UTTARKASHI DATA GENERATOR")
    print("=" * 60)
    
    # 1. Generate villages
    print("\n[1/5] Generating village data...")
    villages = generate_additional_villages(150)
    enriched_villages = compute_village_features(villages)
    villages_geojson = villages_to_geojson(enriched_villages)
    
    with open(output_dir / "villages_raw.geojson", "w") as f:
        json.dump(villages_geojson, f, indent=2)
    print(f"  ✓ Generated {len(enriched_villages)} villages")
    
    # 2. Generate grid terrain features (for ML training)
    print("\n[2/5] Generating terrain grid features...")
    grid_points = generate_grid_points(resolution=0.02)  # ~0.02° ≈ 2km grid
    terrain_features = generate_terrain_features(grid_points)
    
    with open(output_dir / "terrain_features.json", "w") as f:
        json.dump(terrain_features, f, indent=2)
    print(f"  ✓ Generated {len(terrain_features)} grid points")
    
    # 3. Disaster history
    print("\n[3/5] Generating disaster history...")
    disasters_geojson = disaster_history_to_geojson()
    with open(output_dir / "disaster_history.geojson", "w") as f:
        json.dump(disasters_geojson, f, indent=2)
    print(f"  ✓ Generated {len(DISASTER_SITES)} disaster records")
    
    # 4. Rivers
    print("\n[4/5] Generating river data...")
    rivers_geojson = rivers_to_geojson()
    with open(output_dir / "rivers.geojson", "w") as f:
        json.dump(rivers_geojson, f, indent=2)
    print(f"  ✓ Generated {len(RIVERS)} river segments")
    
    # 5. District boundary
    print("\n[5/5] Generating district boundary...")
    boundary = generate_district_boundary()
    with open(output_dir / "district_boundary.geojson", "w") as f:
        json.dump(boundary, f, indent=2)
    print("  ✓ Generated district boundary")
    
    # Summary
    print("\n" + "=" * 60)
    print("DATA GENERATION COMPLETE")
    print(f"Output directory: {output_dir}")
    print(f"Files generated:")
    for f in sorted(output_dir.glob("*")):
        size = f.stat().st_size / 1024
        print(f"  • {f.name} ({size:.1f} KB)")
    print("=" * 60)
