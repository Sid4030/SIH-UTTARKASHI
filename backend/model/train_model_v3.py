"""
THRIVE-Powered Hazard Model Training for Uttarkashi District (v3.0)
====================================================================
Replaces the old circular self-training pipeline with:

1. Ground-truth labels from REAL disaster inventory (not rule-generated)
2. THRIVE multi-hazard fusion algorithm (5-dimensional scoring)
3. Spatial cross-validation (prevents autocorrelation leakage)
4. Proper AHP with eigenvector-derived weights
5. Physics-constrained predictions (bounded by Factor of Safety)
6. Full provenance tracking of data sources

WHAT CHANGED from v2:
  - Labels: REAL disaster events → binary/soft labels (was: rule_based formula → labels)
  - Validation: Spatial cross-validation (was: random train/test split)
  - Zone scoring: THRIVE 5-dimension fusion (was: single XGBoost prediction)
  - AHP: Eigenvector method with consistency check (was: hardcoded weights)
  - Safe zones: Real road distance from OSM (was: distance to nearest town)
"""

import json
import math
import os
import sys
import numpy as np
from pathlib import Path

from backend.model.trigger_engine import classify_zone
from backend.model.thrive_engine import (
    run_thrive_pipeline, compute_thrive_score,
    compute_ahp_weights, compute_safe_zone_suitability_ahp,
    compute_vulnerability_index, compute_temporal_recurrence,
)
from backend.data.vector_pipeline import (
    load_landslide_inventory, load_river_network, load_road_network,
    compute_real_river_distance, compute_real_road_distance,
)

np.random.seed(42)


def generate_hazard_grid_geojson(thrive_grid):
    """Generate hazard grid as GeoJSON for map visualization using THRIVE scores."""
    features = []
    for cell in thrive_grid:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [cell["lng"], cell["lat"]]
            },
            "properties": {
                "hazard_probability": cell["thrive_score"],
                "zone": cell["zone"],
                "elevation": cell.get("elevation", 0),
                "slope": cell.get("slope", 0),
                "twi": cell.get("twi", 0),
                "rainfall_mm": cell.get("rainfall_mm", 0),
                "ndvi": cell.get("ndvi", 0),
                "lulc_class": cell.get("lulc_class", ""),
                "dimensions": cell.get("dimensions", {}),
            }
        })
    return {"type": "FeatureCollection", "features": features}


def generate_hazard_zone_polygons(thrive_grid, resolution=0.02):
    """Generate hazard zone boundary polygons from THRIVE grid."""
    zone_cells = {"red": [], "orange": [], "yellow": [], "green": []}
    for cell in thrive_grid:
        zone_cells[cell["zone"]].append(cell)

    zone_features = []
    zone_colors = {
        "red": "#ff4757", "orange": "#ff7f50",
        "yellow": "#ffd700", "green": "#2ed573"
    }
    zone_labels = {
        "red": "Red Zone — Permanent Relocation Required",
        "orange": "Orange Zone — High Risk, Short-term Relocation",
        "yellow": "Yellow Zone — Moderate Risk, Monitoring Required",
        "green": "Green Zone — Safe for Habitation"
    }

    for zone, cells in zone_cells.items():
        for cell in cells:
            half = resolution / 2
            polygon = [
                [cell["lng"] - half, cell["lat"] - half],
                [cell["lng"] + half, cell["lat"] - half],
                [cell["lng"] + half, cell["lat"] + half],
                [cell["lng"] - half, cell["lat"] + half],
                [cell["lng"] - half, cell["lat"] - half],
            ]
            zone_features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [polygon]},
                "properties": {
                    "zone": zone,
                    "label": zone_labels[zone],
                    "color": zone_colors[zone],
                    "cell_lat": cell["lat"],
                    "cell_lng": cell["lng"],
                    "hazard_probability": cell["thrive_score"],
                }
            })

    return {"type": "FeatureCollection", "features": zone_features}


def compute_village_thrive_scores(villages_geojson, thrive_grid, disaster_inventory,
                                   river_data=None, road_data=None):
    """Assign THRIVE scores and 5-dimension explainable vulnerability to villages."""
    updated_features = []
    ahp_weights = compute_ahp_weights()

    for village in villages_geojson["features"]:
        vlat = village["geometry"]["coordinates"][1]
        vlng = village["geometry"]["coordinates"][0]
        props = village["properties"]

        # 1. Spatial THRIVE probability from surrounding grid cells
        distances_scores = []
        for cell in thrive_grid:
            dlat = (vlat - cell["lat"]) * 111
            dlng = (vlng - cell["lng"]) * 95
            dist = math.sqrt(dlat**2 + dlng**2)
            if dist < 5:
                distances_scores.append((dist, cell["thrive_score"]))

        if distances_scores:
            total_weight = sum(1 / (d + 0.01)**2 for d, _ in distances_scores)
            spatial_thrive = sum((1 / (d + 0.01)**2) * s for d, s in distances_scores) / total_weight
        else:
            spatial_thrive = 0.3

        # 2. Compute village-specific THRIVE with vulnerability dimension
        pop = props.get("population", 100)
        dist_river = props.get("dist_river_km", compute_real_river_distance(vlat, vlng, river_data))
        dist_road = props.get("dist_road_km", compute_real_road_distance(vlat, vlng, road_data))

        village_thrive = compute_thrive_score(
            slope=props.get("slope", 15),
            elevation=props.get("elevation", 2000),
            aspect=props.get("aspect", 180),
            curvature=props.get("curvature", 0),
            twi=props.get("twi", 8),
            ndvi=props.get("ndvi", 0.5),
            dist_river_km=dist_river,
            rainfall_mm=props.get("rainfall_mm", 100),
            dist_road_km=dist_road,
            population=pop,
            is_town=props.get("is_town", False),
            households=props.get("households", 0),
            lat=vlat, lon=vlng,
            disaster_inventory=disaster_inventory,
            lulc_class=props.get("lulc_class", "scrubland"),
        )

        # Blend spatial grid THRIVE with village-specific THRIVE
        blended = 0.5 * spatial_thrive + 0.5 * village_thrive["thrive_score"]
        
        # Historical disaster proximity boost
        h_recurrence = village_thrive["dimensions"]["historical_recurrence"]
        if h_recurrence > 0.6:
            blended = min(1.0, blended + 0.15)
        elif h_recurrence > 0.3:
            blended = min(1.0, blended + 0.05)

        zone = classify_zone(blended)

        # Vulnerability index (0-100 scale for display)
        vulnerability_index = round(blended * 100, 1)

        # Find nearest disaster event
        min_d_dist = float('inf')
        nearest_disaster_name = "None"
        for event in disaster_inventory:
            dd = math.sqrt(((vlat - event["latitude"]) * 111)**2 +
                          ((vlng - event["longitude"]) * 95)**2)
            if dd < min_d_dist:
                min_d_dist = dd
                nearest_disaster_name = event.get("name", "Historical Event")

        # Update properties
        props["hazard_probability"] = round(float(blended), 4)
        props["zone"] = zone
        props["vulnerability_index"] = float(vulnerability_index)
        props["dist_disaster_km"] = round(float(min_d_dist), 2)
        props["dist_road_km"] = round(float(dist_road), 2)
        props["nearest_disaster"] = str(nearest_disaster_name)
        props["thrive_dimensions"] = village_thrive["dimensions"]
        props["score_breakdown"] = {
            "hazard_intensity": round(village_thrive["dimensions"]["landslide_susceptibility"] * 100, 1),
            "flood_exposure": round(village_thrive["dimensions"]["flood_susceptibility"] * 100, 1),
            "cloudburst_risk": round(village_thrive["dimensions"]["cloudburst_susceptibility"] * 100, 1),
            "population_exposure": round(village_thrive["dimensions"]["population_vulnerability"] * 100, 1),
            "disaster_history_proximity": round(village_thrive["dimensions"]["historical_recurrence"] * 100, 1),
        }

        updated_features.append(village)

    villages_geojson["features"] = updated_features
    return villages_geojson


def compute_safe_zones_thrive(thrive_grid, villages_geojson,
                               river_data=None, road_data=None):
    """Identify safe relocation sites using THRIVE + proper AHP."""
    ahp_weights = compute_ahp_weights()
    safe_zones = []

    for cell in thrive_grid:
        if cell["thrive_score"] >= 0.40:
            continue  # Skip hazardous cells

        dist_river = cell.get("dist_river_km", 5.0)
        dist_road = cell.get("dist_road_km", compute_real_road_distance(
            cell["lat"], cell["lng"], road_data))

        hazard_safety_score = 1.0 - cell["thrive_score"]
        
        ahp_result = compute_safe_zone_suitability_ahp(
            hazard_safety_score=hazard_safety_score,
            slope=cell.get("slope", 15),
            dist_river_km=dist_river,
            dist_road_km=dist_road,
            ndvi=cell.get("ndvi", 0.5),
            elevation=cell.get("elevation", 2000),
            lulc_class=cell.get("lulc_class", "scrubland"),
            ahp_weights=ahp_weights,
        )

        if ahp_result["suitability_score"] >= 3.2:
            safe_zones.append({
                "lat": float(cell["lat"]),
                "lng": float(cell["lng"]),
                "suitability_score": ahp_result["suitability_score"],
                "carrying_capacity": ahp_result["carrying_capacity"],
                "elevation": float(cell.get("elevation", 0)),
                "slope": float(cell.get("slope", 0)),
                "dist_river_km": float(dist_river),
                "dist_road_km": float(dist_road),
                "lulc_class": cell.get("lulc_class", "scrubland"),
                "scores": ahp_result["criteria_scores"],
                "ahp_method": ahp_result["ahp_method"],
            })

    safe_zones.sort(key=lambda x: x["suitability_score"], reverse=True)
    return safe_zones


def safe_zones_to_geojson(safe_zones):
    """Convert safe zones to GeoJSON."""
    features = []
    resolution = 0.02
    for i, sz in enumerate(safe_zones):
        half = resolution / 2
        polygon = [
            [sz["lng"] - half, sz["lat"] - half],
            [sz["lng"] + half, sz["lat"] - half],
            [sz["lng"] + half, sz["lat"] + half],
            [sz["lng"] - half, sz["lat"] + half],
            [sz["lng"] - half, sz["lat"] - half],
        ]
        score = sz["suitability_score"]
        if score >= 4.5: rating = "Excellent"
        elif score >= 4.0: rating = "Very Good"
        elif score >= 3.5: rating = "Good"
        else: rating = "Moderate"

        features.append({
            "type": "Feature", "id": i + 1,
            "geometry": {"type": "Polygon", "coordinates": [polygon]},
            "properties": {
                "id": i + 1,
                "suitability_score": sz["suitability_score"],
                "rating": rating,
                "carrying_capacity": sz["carrying_capacity"],
                "elevation": sz["elevation"],
                "slope": sz["slope"],
                "dist_river_km": sz["dist_river_km"],
                "dist_road_km": sz.get("dist_road_km", 5.0),
                "lulc_class": sz.get("lulc_class", ""),
                "ahp_method": sz.get("ahp_method", "eigenvector"),
                "scores": sz["scores"],
            }
        })
    return {"type": "FeatureCollection", "features": features}


def compute_relocation_priorities_thrive(villages_geojson, safe_zones, disaster_inventory):
    """Compute relocation priorities using THRIVE scores."""
    priorities = []
    capacity_ledger = {i: sz["carrying_capacity"] for i, sz in enumerate(safe_zones)}

    candidates = [v for v in villages_geojson["features"]
                  if v["properties"].get("zone") in ["red", "orange"]]
    candidates.sort(key=lambda v: v["properties"].get("vulnerability_index", 0), reverse=True)

    for village in candidates:
        props = village["properties"]
        vlat = village["geometry"]["coordinates"][1]
        vlng = village["geometry"]["coordinates"][0]
        pop = props.get("population", 100)
        zone = props.get("zone", "orange")
        vi = props.get("vulnerability_index", 50.0)
        slope = props.get("slope", 15.0)
        dist_disaster = props.get("dist_disaster_km", 10.0)
        nearest_disaster = props.get("nearest_disaster", "Historical Event")
        dist_river = props.get("dist_river_km", 5.0)
        dist_road = props.get("dist_road_km", 5.0)
        breakdown = props.get("score_breakdown", {})
        thrive_dims = props.get("thrive_dimensions", {})

        # Find nearest safe zone with capacity
        best_safe, best_dist, best_idx = None, float('inf'), None
        for idx, sz in enumerate(safe_zones[:60]):
            dlat = (vlat - sz["lat"]) * 111
            dlng = (vlng - sz["lng"]) * 95
            dist = math.sqrt(dlat**2 + dlng**2)
            has_headroom = capacity_ledger.get(idx, 0) >= (pop * 0.5)
            effective_dist = dist if has_headroom else dist + 15.0
            if effective_dist < best_dist:
                best_dist = dist
                best_safe = sz
                best_idx = idx

        if best_idx is not None:
            capacity_ledger[best_idx] = max(0, capacity_ledger[best_idx] - pop)
            remaining_cap = capacity_ledger[best_idx]
        else:
            remaining_cap = 0

        # Priority scoring with THRIVE dimensions
        zone_weight = 20.0 if zone == "red" else 10.0
        pop_weight = min(20.0, (math.log10(max(pop, 10)) / 4.0) * 20.0)
        priority_score = round(min(100.0, (vi * 0.60) + pop_weight + zone_weight), 1)

        # Timeline classification
        if zone == "red" and (vi >= 65.0 or dist_disaster < 2.5 or slope > 30.0):
            timeline = "immediate"
            urgency_level = "CRITICAL / IMMEDIATE"
            rationale = (
                f"IMMEDIATE EVACUATION: THRIVE score {props.get('hazard_probability', 0)*100:.0f}% "
                f"(Landslide: {thrive_dims.get('landslide_susceptibility', 0)*100:.0f}%, "
                f"Flood: {thrive_dims.get('flood_susceptibility', 0)*100:.0f}%, "
                f"Cloudburst: {thrive_dims.get('cloudburst_susceptibility', 0)*100:.0f}%). "
                f"{pop:,} residents on {slope:.1f}° slope, {dist_disaster:.1f}km from {nearest_disaster}."
            )
            action = (
                f"Invoke DM Act Sec 30: Mandatory pre-monsoon evacuation to Safe Site Alpha-{best_idx+1 if best_idx else 1} "
                f"({best_dist:.1f}km, Road: {dist_road:.1f}km). SDRF permanent rehabilitation package."
            )
        elif zone == "red" or (zone == "orange" and vi >= 58.0):
            timeline = "short_term"
            urgency_level = "HIGH RISK / SHORT-TERM"
            rationale = (
                f"SHORT-TERM RELOCATION: THRIVE VI {vi}/100. Multi-hazard exposure "
                f"(Recurrence: {thrive_dims.get('historical_recurrence', 0)*100:.0f}%). "
                f"{pop:,} residents, {dist_disaster:.1f}km from disaster corridor."
            )
            action = (
                f"Phase-1 pre-monsoon staging at Safe Site Alpha-{best_idx+1 if best_idx else 1}. "
                f"Deploy slope sensors and early warning siren."
            )
        else:
            timeline = "medium_term"
            urgency_level = "MODERATE RISK / MEDIUM-TERM"
            rationale = (
                f"MEDIUM-TERM MITIGATION: THRIVE VI {vi}/100. "
                f"{pop:,} residents vulnerable during extreme events."
            )
            action = (
                f"Bio-engineering slope stabilization + planned voluntary relocation "
                f"to Safe Site Alpha-{best_idx+1 if best_idx else 1}."
            )

        priorities.append({
            "village_id": props["id"],
            "village_name": props["name"],
            "tehsil": props.get("tehsil", ""),
            "population": pop,
            "households": props.get("households", int(pop / 5.2)),
            "current_zone": zone,
            "hazard_probability": props.get("hazard_probability", 0.7),
            "vulnerability_index": vi,
            "priority_score": priority_score,
            "timeline": timeline,
            "urgency_level": urgency_level,
            "defensible_rationale": rationale,
            "recommended_action": action,
            "score_breakdown": breakdown,
            "thrive_dimensions": thrive_dims,
            "relocation_distance_km": round(best_dist, 2) if best_safe else None,
            "suggested_safe_zone": {
                "site_id": (best_idx + 1) if best_idx is not None else None,
                "lat": best_safe["lat"] if best_safe else None,
                "lng": best_safe["lng"] if best_safe else None,
                "suitability_score": best_safe["suitability_score"] if best_safe else None,
                "total_carrying_capacity": best_safe["carrying_capacity"] if best_safe else None,
                "remaining_capacity_headroom": remaining_cap,
            } if best_safe else None
        })

    priorities.sort(key=lambda x: x["priority_score"], reverse=True)
    for i, p in enumerate(priorities):
        p["rank"] = i + 1

    return priorities


# ---------------------------------------------------------------------------
# Main Training Pipeline
# ---------------------------------------------------------------------------
def main():
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    output_dir = script_dir.parent / "output"
    output_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("THRIVE HAZARD MODEL v3.0 — UTTARKASHI")
    print("=" * 60)

    # 1. Load terrain features
    print("\n[1/7] Loading terrain features...")
    with open(output_dir / "terrain_features.json") as f:
        terrain_features = json.load(f)
    print(f"  ✓ Loaded {len(terrain_features)} grid points")

    # 2. Load disaster inventory (REAL ground-truth)
    print("\n[2/7] Loading disaster inventory for ground-truth labels...")
    disaster_inventory = load_landslide_inventory()
    print(f"  ✓ Loaded {len(disaster_inventory)} verified disaster events")

    # 3. Load vector data
    print("\n[3/7] Loading vector datasets...")
    river_data = load_river_network()
    road_data = load_road_network()

    # 4. Run THRIVE pipeline (train + compute grid scores)
    print("\n[4/7] Running THRIVE multi-hazard fusion pipeline...")
    thrive_results = run_thrive_pipeline(
        terrain_features, disaster_inventory,
        river_data=river_data, road_data=road_data,
    )

    thrive_grid = thrive_results["thrive_grid"]
    metrics = thrive_results["model_metrics"]

    # Save model metrics
    with open(output_dir / "model_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"  ✓ THRIVE model trained")

    # 5. Generate hazard zone outputs
    print("\n[5/7] Generating hazard zone maps...")
    hazard_grid = generate_hazard_grid_geojson(thrive_grid)
    with open(output_dir / "hazard_grid.geojson", "w") as f:
        json.dump(hazard_grid, f, indent=2)

    hazard_zones = generate_hazard_zone_polygons(thrive_grid)
    with open(output_dir / "hazard_zones.geojson", "w") as f:
        json.dump(hazard_zones, f, indent=2)

    zone_counts = thrive_results["zone_counts"]
    print(f"  ✓ Zone distribution: {json.dumps(zone_counts)}")

    # 6. Compute village THRIVE scores and safe zones
    print("\n[6/7] Computing village THRIVE scores and safe zones...")
    with open(output_dir / "villages_raw.geojson") as f:
        villages_geojson = json.load(f)

    villages_geojson = compute_village_thrive_scores(
        villages_geojson, thrive_grid, disaster_inventory,
        river_data, road_data
    )
    with open(output_dir / "villages.geojson", "w") as f:
        json.dump(villages_geojson, f, indent=2)

    village_zones = {}
    for v in villages_geojson["features"]:
        z = v["properties"]["zone"]
        village_zones[z] = village_zones.get(z, 0) + 1
    print(f"  ✓ Village zones: {json.dumps(village_zones)}")

    safe_zones = compute_safe_zones_thrive(
        thrive_grid, villages_geojson, river_data, road_data)
    safe_zones_geojson = safe_zones_to_geojson(safe_zones)
    with open(output_dir / "safe_zones.geojson", "w") as f:
        json.dump(safe_zones_geojson, f, indent=2)
    print(f"  ✓ Identified {len(safe_zones)} safe zones (AHP eigenvector method)")

    # 7. Relocation priorities
    print("\n[7/7] Computing relocation priorities...")
    priorities = compute_relocation_priorities_thrive(
        villages_geojson, safe_zones, disaster_inventory)
    with open(output_dir / "relocation_priorities.json", "w") as f:
        json.dump(priorities, f, indent=2)

    immediate = sum(1 for p in priorities if p["timeline"] == "immediate")
    short_term = sum(1 for p in priorities if p["timeline"] == "short_term")
    medium_term = sum(1 for p in priorities if p["timeline"] == "medium_term")
    total_pop = sum(p["population"] for p in priorities)

    print(f"  ✓ Relocation priorities:")
    print(f"    Immediate:   {immediate} villages")
    print(f"    Short-term:  {short_term} villages")
    print(f"    Medium-term: {medium_term} villages")
    print(f"    Total population to relocate: {total_pop:,}")

    # Summary
    print("\n" + "=" * 60)
    print("THRIVE MODEL TRAINING & ANALYSIS COMPLETE")
    print(f"\n  Algorithm: THRIVE (Terrain-Hydro-Risk Integrated Vulnerability Engine)")
    print(f"  Ground-Truth: {len(disaster_inventory)} verified disaster events")
    print(f"  ML Model: {metrics.get('model_type', 'XGBoost')}")
    print(f"  AHP Method: Eigenvector with consistency check")
    print(f"\nOutput files:")
    for fp in sorted(output_dir.glob("*")):
        size = fp.stat().st_size / 1024
        print(f"  • {fp.name} ({size:.1f} KB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
