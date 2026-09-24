"""
Export datasets to clean, standardized CSV and JSON formats for Google Colab model training.
Exports:
1. uttarkashi_terrain_grid_3111.csv & .json (3,111 terrain points with 11 features, THRIVE score, surrogate target, zone)
2. uttarkashi_historical_disasters_18.csv & .json (18 verified historical disaster events)
3. uttarkashi_habitations_census2011_51.csv & .json (51 official census habitations)
"""

import json
import math
import numpy as np
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
EXPORT_DIR = OUTPUT_DIR / "colab_export"
EXPORT_DIR.mkdir(exist_ok=True, parents=True)

# 1. Historical Disasters (18 verified events)
print("[1/3] Exporting 18 Historically Verified Disasters...")
disasters_path = BASE_DIR / "data" / "datasets" / "inventory" / "uttarkashi_landslides_local.json"
if not disasters_path.exists():
    disasters_path = OUTPUT_DIR / "disaster_history.geojson"
    with open(disasters_path) as f:
        gh = json.load(f)
    disaster_list = []
    for feat in gh["features"]:
        p = feat["properties"]
        c = feat["geometry"]["coordinates"]
        disaster_list.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "latitude": c[1],
            "longitude": c[0],
            "event_type": p.get("type"),
            "year": p.get("year"),
            "severity": p.get("severity"),
            "fatalities": p.get("casualties", 0),
            "missing": p.get("missing", 0),
            "displaced": p.get("displaced", 0),
            "source": p.get("source")
        })
else:
    with open(disasters_path) as f:
        disaster_list = json.load(f)

df_disasters = pd.DataFrame(disaster_list)
df_disasters.to_csv(EXPORT_DIR / "uttarkashi_historical_disasters_18.csv", index=False)
with open(EXPORT_DIR / "uttarkashi_historical_disasters_18.json", "w") as f:
    json.dump(disaster_list, f, indent=2)
print(f"  ✓ Saved {len(df_disasters)} disaster records to CSV and JSON.")

# 2. Habitations (51 Census 2011 villages/towns)
print("\n[2/3] Exporting 51 Statutory Census Habitations...")
villages_geojson_path = OUTPUT_DIR / "villages.geojson"
with open(villages_geojson_path) as f:
    v_geo = json.load(f)

villages_list = []
for feat in v_geo["features"]:
    p = feat["properties"]
    c = feat["geometry"]["coordinates"]
    dims = p.get("thrive_dimensions", {})
    villages_list.append({
        "village_id": p.get("id"),
        "name": p.get("name"),
        "tehsil": p.get("tehsil"),
        "census_code": p.get("census_code"),
        "latitude": c[1],
        "longitude": c[0],
        "population": p.get("population"),
        "households": p.get("households"),
        "is_town": p.get("is_town", False),
        "elevation_m": p.get("elevation"),
        "slope_deg": p.get("slope"),
        "aspect_deg": p.get("aspect"),
        "curvature": p.get("curvature"),
        "twi": p.get("twi"),
        "dist_river_km": p.get("dist_river_km"),
        "dist_road_km": p.get("dist_road_km"),
        "dist_disaster_km": p.get("dist_disaster_km"),
        "hazard_probability": p.get("hazard_probability"),
        "zone": p.get("zone"),
        "vulnerability_index": p.get("vulnerability_index"),
        "thrive_landslide": dims.get("landslide_susceptibility", 0.0),
        "thrive_flood": dims.get("flood_susceptibility", 0.0),
        "thrive_cloudburst": dims.get("cloudburst_susceptibility", 0.0),
        "thrive_vulnerability": dims.get("population_vulnerability", 0.0),
        "thrive_recurrence": dims.get("historical_recurrence", 0.0)
    })

df_villages = pd.DataFrame(villages_list)
df_villages.to_csv(EXPORT_DIR / "uttarkashi_habitations_census2011_51.csv", index=False)
with open(EXPORT_DIR / "uttarkashi_habitations_census2011_51.json", "w") as f:
    json.dump(villages_list, f, indent=2)
print(f"  ✓ Saved {len(df_villages)} habitation records to CSV and JSON.")

# 3. Grid Dataset (3,111 terrain points with 11 features + targets)
print("\n[3/3] Exporting 3,111 Terrain Grid Points with 11 Model Features...")
with open(OUTPUT_DIR / "terrain_features.json") as f:
    terrain_list = json.load(f)

with open(OUTPUT_DIR / "hazard_grid.geojson") as f:
    grid_geo = json.load(f)

# Build road network distance fallback helper
from backend.data.vector_pipeline import compute_real_road_distance

grid_rows = []
for i, pt in enumerate(terrain_list):
    props = grid_geo["features"][i]["properties"]
    clat = pt["lat"]
    clng = pt["lng"]
    slope = float(pt.get("slope", 15.0))
    elev = float(pt.get("elevation", 1500.0))
    aspect = float(pt.get("aspect", 180.0))
    curvature = float(pt.get("curvature", 0.0))
    twi = float(pt.get("twi", 8.0))
    ndvi = float(pt.get("ndvi", 0.45))
    dist_river = float(pt.get("dist_river_km", 2.0))
    dist_road = float(pt.get("dist_road_km", compute_real_road_distance(clat, clng)))
    rain_nominal = float(pt.get("rainfall_mm", 120.0))

    # Features used by DualBrain AI:
    # 1. slope
    # 2. elevation
    # 3. aspect
    # 4. curvature
    # 5. twi
    # 6. ndvi
    # 7. dist_river_km
    # 8. dist_road_km
    # 9. rainfall_intensity (baseline nominal: 35.0 mm/hr or scaled from rainfall_mm)
    # 10. antecedent_saturation (baseline: 50.0 mm)
    # 11. seismic_kh (baseline: 0.0g)
    rain_intensity = round(max(5.0, rain_nominal * 0.35), 2)
    antecedent_sat = round(max(10.0, rain_nominal * 0.45), 2)
    seismic_kh = 0.05

    # Compute Ground Truth Proxy target (from dual_brain_ai.py)
    min_dist_disaster = float("inf")
    for ev in disaster_list:
        elat = ev["latitude"]
        elng = ev["longitude"]
        d = math.sqrt(((clat - elat) * 111.0) ** 2 + ((clng - elng) * 95.0) ** 2)
        if d < min_dist_disaster:
            min_dist_disaster = d

    slope_risk = min(1.0, slope / 45.0)
    prox_risk = max(0.0, 1.0 - (min_dist_disaster / 12.0))
    rain_risk = min(1.0, rain_nominal / 250.0)
    surrogate_target = round(float(np.clip(0.45 * slope_risk + 0.35 * prox_risk + 0.20 * rain_risk, 0.02, 0.98)), 4)

    thrive_score = round(float(props.get("hazard_probability", surrogate_target)), 4)
    zone = props.get("zone", "green")
    zone_code = {"green": 0, "yellow": 1, "orange": 2, "red": 3}.get(zone, 0)

    dims = props.get("dimensions", {})

    grid_rows.append({
        "cell_id": i + 1,
        "latitude": clat,
        "longitude": clng,
        # 11 Training Features
        "slope": slope,
        "elevation": elev,
        "aspect": aspect,
        "curvature": curvature,
        "twi": twi,
        "ndvi": ndvi,
        "dist_river_km": dist_river,
        "dist_road_km": dist_road,
        "rainfall_intensity": rain_intensity,
        "antecedent_saturation": antecedent_sat,
        "seismic_kh": seismic_kh,
        # Proximity & Physical context
        "dist_disaster_km": round(min_dist_disaster, 2),
        "rainfall_mm_annual_proxy": rain_nominal,
        # Targets
        "target_hazard_score": surrogate_target,
        "thrive_hazard_score": thrive_score,
        "zone": zone,
        "zone_code": zone_code,
        # 5 THRIVE Dimensions
        "dim_landslide": dims.get("landslide_susceptibility", 0.0),
        "dim_flood": dims.get("flood_susceptibility", 0.0),
        "dim_cloudburst": dims.get("cloudburst_susceptibility", 0.0),
        "dim_vulnerability": dims.get("population_vulnerability", 0.0),
        "dim_recurrence": dims.get("historical_recurrence", 0.0)
    })

df_grid = pd.DataFrame(grid_rows)
df_grid.to_csv(EXPORT_DIR / "uttarkashi_terrain_grid_3111.csv", index=False)
with open(EXPORT_DIR / "uttarkashi_terrain_grid_3111.json", "w") as f:
    json.dump(grid_rows, f, indent=2)
print(f"  ✓ Saved {len(df_grid)} grid cells to CSV and JSON.")

print("\n" + "=" * 60)
print(f"ALL COLAB EXPORTS CREATED IN: {EXPORT_DIR}")
for p in sorted(EXPORT_DIR.glob("*")):
    size_kb = p.stat().st_size / 1024
    print(f"  • {p.name} ({size_kb:.1f} KB)")
print("=" * 60)
