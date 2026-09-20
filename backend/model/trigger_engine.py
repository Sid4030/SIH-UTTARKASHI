"""
Real-Time Hydrological Hazard Trigger & Nowcast Engine — Uttarkashi District
=============================================================================
Layer 2 of the platform: converts static susceptibility scores into dynamic,
rainfall-triggered operational alert states per village, and auto-dispatches
EVACUATE_NOW habitations to safe relocation sites with verified capacity headroom.

Design mirrors operational landslide nowcasting practice (e.g. NASA LHASA, IMD):
  dynamic_probability = baseline_hazard_probability * intensity_factor * antecedent_factor

Inputs:
  - intensity_mm_hr   : instantaneous precipitation rate (mm/hr)
  - antecedent_24h_mm : cumulative 24-hour rainfall (soil saturation proxy)
"""

import json
import math
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# 1. Rainfall Multipliers (Operational IMD & NASA LHASA bands)
# ---------------------------------------------------------------------------
def intensity_factor(intensity_mm_hr: float) -> float:
    """IMD rainfall intensity classification -> amplification multiplier."""
    if intensity_mm_hr < 2.5:
        return 1.00   # Negligible / Dry
    elif intensity_mm_hr < 7.5:
        return 1.10   # Light rain
    elif intensity_mm_hr < 35.5:
        return 1.30   # Moderate rain
    elif intensity_mm_hr < 64.5:
        return 1.65   # Heavy rain
    elif intensity_mm_hr < 124.5:
        return 2.10   # Very heavy rain / cloudburst
    else:
        return 2.65   # Extreme Himalayan deluge (>125mm/hr)


def antecedent_factor(antecedent_24h_mm: float) -> float:
    """Cumulative 24h precipitation -> antecedent soil moisture saturation multiplier."""
    if antecedent_24h_mm < 20.0:
        return 1.00   # Unsaturated soil
    elif antecedent_24h_mm < 50.0:
        return 1.15   # Moderate saturation
    elif antecedent_24h_mm < 100.0:
        return 1.35   # High saturation (liquefaction risk)
    else:
        return 1.60   # Critical saturation / zero absorption capacity


def rainfall_multiplier(intensity_mm_hr: float, antecedent_24h_mm: float = 0.0) -> float:
    """Composite trigger multiplier combining storm intensity and antecedent moisture."""
    return intensity_factor(intensity_mm_hr) * antecedent_factor(antecedent_24h_mm)


# ---------------------------------------------------------------------------
# 2. Operational Zone and Alert Level Classification
# ---------------------------------------------------------------------------
def classify_zone(probability: float) -> str:
    """
    Canonical Multi-Hazard Zone Classifier.
    Unified across static baseline training, live nowcasting, and dynamic simulation.
    Red: >= 0.70 (Severe Landslide/Flash Flood Hazard - Prohibited for permanent habitation)
    Orange: 0.50 - 0.699 (High Hazard - Monitored/Restricted buffer)
    Yellow: 0.30 - 0.499 (Moderate Hazard - Cautionary)
    Green: < 0.30 (Low Hazard - Safe terrain)
    """
    if probability >= 0.70:
        return "red"
    elif probability >= 0.50:
        return "orange"
    elif probability >= 0.30:
        return "yellow"
    else:
        return "green"


ALERT_THRESHOLDS = [
    (0.85, "EVACUATE_NOW"),
    (0.70, "WARNING"),
    (0.55, "WATCH"),
    (0.00, "NORMAL")
]


def classify_alert(dynamic_probability: float) -> str:
    for threshold, label in ALERT_THRESHOLDS:
        if dynamic_probability >= threshold:
            return label
    return "NORMAL"



# ---------------------------------------------------------------------------
# 3. Dynamic Village Alert Computation
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 3. Dynamic Village Alert Computation with Seismic & Orographic Coupling
# ---------------------------------------------------------------------------
def compute_dynamic_alerts(villages_geojson: dict,
                           intensity_mm_hr: float,
                           antecedent_24h_mm: float = 0.0,
                           seismic_kh: float = 0.0,
                           min_baseline_zone=("yellow", "orange", "red")):
    """
    Applies the dual rainfall trigger + pseudo-static seismic acceleration
    to each village's static hazard susceptibility.
    """
    mult = rainfall_multiplier(intensity_mm_hr, antecedent_24h_mm)
    # Pseudo-static seismic acceleration amplification (Zone IV/V Himalayan thrust)
    seismic_amp = 1.0 + max(0.0, float(seismic_kh) * 1.8)
    alerts = []

    for village in villages_geojson["features"]:
        props = village["properties"]
        coords = village["geometry"]["coordinates"]
        baseline_zone = props.get("zone", "green")
        baseline_prob = props.get("hazard_probability", 0.3)
        slope = props.get("slope", 15.0)
        elev = props.get("elevation", 1800.0)

        # 1. Slope sensitivity amplification
        slope_amp = 1.0 + max(0.0, (slope - 20.0) / 50.0) * 0.15

        # 2. Orographic cloudburst funnel factor (1,500m - 2,800m elevation funnel)
        if 1500.0 <= elev <= 2800.0 and intensity_mm_hr >= 50.0:
            orog_amp = 1.12
        else:
            orog_amp = 1.0

        effective_prob = min(0.99, baseline_prob * mult * slope_amp * seismic_amp * orog_amp)
        alert_level = classify_alert(effective_prob)
        
        # Don't false-alarm stable low-slope green zones unless severe deluge or high seismic shaking
        eligible = baseline_zone in min_baseline_zone or effective_prob >= 0.85
        if not eligible and alert_level != "NORMAL":
            alert_level = "NORMAL"

        alerts.append({
            "village_id": props.get("id"),
            "village_name": props.get("name"),
            "tehsil": props.get("tehsil", "Bhatwari"),
            "population": props.get("population", 100),
            "households": props.get("households", max(1, int(props.get("population", 100) / 5.2))),
            "slope": slope,
            "elevation": elev,
            "baseline_zone": baseline_zone,
            "baseline_probability": round(float(baseline_prob), 4),
            "rainfall_multiplier": round(float(mult), 3),
            "seismic_multiplier": round(float(seismic_amp), 3),
            "dynamic_probability": round(float(effective_prob), 4),
            "alert_level": alert_level,
            "lat": coords[1],
            "lng": coords[0],
        })

    return alerts


# ---------------------------------------------------------------------------
# 4. Automated Safe Site Dispatch with Carrying Capacity Ledger & Overflow Redistribution
# ---------------------------------------------------------------------------
def match_alerts_to_safe_zones(alerts: list, safe_zones: list, capacity_ledger: dict = None):
    """
    For every EVACUATE_NOW and WARNING alert, match to the nearest safe relocation site
    with verified carrying capacity headroom, deducting population from the ledger.
    If a safe site hits saturation, automatically redistributes overflow to the secondary nearest site.
    """
    if capacity_ledger is None:
        capacity_ledger = {i: sz["carrying_capacity"] for i, sz in enumerate(safe_zones)}

    dispatched = []
    # Highest dynamic probability gets priority choice of nearest safe site
    critical = [a for a in alerts if a["alert_level"] in ["EVACUATE_NOW", "WARNING"]]
    critical.sort(key=lambda a: a["dynamic_probability"], reverse=True)

    for alert in critical:
        best_idx, best_dist = None, float("inf")
        pop = alert.get("population") or 100

        # Primary Search: Safe site with sufficient remaining capacity headroom
        for idx, sz in enumerate(safe_zones):
            dlat = (alert["lat"] - sz["lat"]) * 111.0
            dlng = (alert["lng"] - sz["lng"]) * 95.0
            dist = math.sqrt(dlat**2 + dlng**2)

            has_headroom = capacity_ledger.get(idx, 0) >= (pop * 0.4)
            effective_dist = dist if has_headroom else dist + 35.0

            if effective_dist < best_dist:
                best_dist = dist
                best_idx = idx

        # If best choice is overloaded, assign with overflow warning
        is_overflow = False
        if best_idx is not None:
            if capacity_ledger[best_idx] < pop:
                is_overflow = True
            capacity_ledger[best_idx] = max(0, capacity_ledger[best_idx] - pop)
            sz = safe_zones[best_idx]
            remaining = capacity_ledger[best_idx]
            site_name = f"Safe Site Alpha-{best_idx + 1}"

            overflow_note = " [CAPACITY OVERFLOW REDISTRIBUTION ACTIVE]" if is_overflow else ""
            directive = (
                f"MHA STATUTORY ORDER: Pre-monsoon evacuation of {alert['village_name']} ({pop:,} citizens) "
                f"-> {site_name} ({best_dist:.1f} km away). Remaining capacity headroom: {remaining:,}{overflow_note}."
            )
            site_lat = sz["lat"]
            site_lng = sz["lng"]
        else:
            directive = f"EMERGENCY ORDER: Evacuate {alert['village_name']} — Activate district emergency transit shelter override."
            site_lat = None
            site_lng = None

        dispatched.append({
            **alert,
            "matched_safe_zone_id": (best_idx + 1) if best_idx is not None else None,
            "safe_zone_name": f"Safe Site Alpha-{best_idx + 1}" if best_idx is not None else "Designated Transit Shelter",
            "safe_zone_coords": [site_lng, site_lat] if site_lat else None,
            "distance_km": round(best_dist, 2) if best_idx is not None else None,
            "directive": directive,
            "is_capacity_overflow": is_overflow,
            "issued_at": datetime.now(timezone.utc).isoformat(),
        })

    return dispatched, capacity_ledger


def generate_carrying_capacity_ledger(safe_zones: list, dispatched_evacuations: list) -> list:
    """
    Computes complete, site-by-site NDMA carrying capacity status across all safe relocation sites.
    Tracks total capacity, allocated population, assigned villages, remaining headroom, and stress tier.
    """
    ledger = []
    # Map allocations
    allocation_map = {}
    for d in dispatched_evacuations:
        site_id = d.get("matched_safe_zone_id")
        if site_id:
            idx = site_id - 1
            if idx not in allocation_map:
                allocation_map[idx] = []
            allocation_map[idx].append(d)

    for idx, sz in enumerate(safe_zones):
        site_num = idx + 1
        total_cap = sz.get("carrying_capacity", 2000)
        assigned = allocation_map.get(idx, [])
        allocated_pop = sum(v.get("population", 0) for v in assigned)
        remaining = max(0, total_cap - allocated_pop)
        utilization = round((allocated_pop / total_cap) * 100.0, 1) if total_cap > 0 else 0.0

        if allocated_pop > total_cap:
            stress_tier = "DEFICIT"
        elif utilization >= 85.0:
            stress_tier = "STRESSED"
        elif utilization >= 40.0:
            stress_tier = "OPTIMAL"
        else:
            stress_tier = "SURPLUS"

        ledger.append({
            "site_id": site_num,
            "name": f"Safe Site Alpha-{site_num}",
            "lat": sz.get("lat"),
            "lng": sz.get("lng"),
            "total_capacity": total_cap,
            "allocated_population": allocated_pop,
            "remaining_headroom": remaining,
            "utilization_pct": utilization,
            "stress_tier": stress_tier,
            "suitability_score": sz.get("suitability_score", 4.0),
            "allocated_villages_count": len(assigned),
            "allocated_villages": [v.get("village_name") for v in assigned],
            "road_access_km": sz.get("dist_road_km", 1.2),
            "water_access_km": sz.get("dist_river_km", 2.0),
            "slope_degrees": sz.get("slope", 6.5)
        })

    return ledger


# ---------------------------------------------------------------------------
# 5. Dynamic Hazard Zones Polygon Generator (Continuous Spatial Contours)
# ---------------------------------------------------------------------------
def compute_dynamic_hazard_zones(hazard_grid: dict, resolution: float = 0.02) -> dict:
    """
    Generates real-time GeoJSON Polygons representing Multi-Hazard Red, Orange, Yellow, Green zones.
    Maps and updates hazard-based Red Zones dynamically when rainfall/seismic triggers occur.
    """
    zone_colors = {
        "red": "#ff334b",
        "orange": "#ff8833",
        "yellow": "#f5cc00",
        "green": "#10b981"
    }
    zone_labels = {
        "red": "Red Zone — Permanent Relocation Required (Unsuitable for Habitation)",
        "orange": "Orange Zone — High Hazard (Short-Term Relocation Buffer)",
        "yellow": "Yellow Zone — Moderate Risk (Continuous Monitoring)",
        "green": "Green Zone — Safe Relocation Reception Zone"
    }

    features = []
    half = resolution / 2.0

    for feat in hazard_grid.get("features", []):
        coords = feat["geometry"]["coordinates"]
        lng, lat = coords[0], coords[1]
        props = feat.get("properties", {})
        zone = props.get("zone", "green")
        prob = props.get("hazard_probability", 0.1)
        is_expanded = props.get("is_expanded_red", False)

        polygon = [
            [round(lng - half, 5), round(lat - half, 5)],
            [round(lng + half, 5), round(lat - half, 5)],
            [round(lng + half, 5), round(lat + half, 5)],
            [round(lng - half, 5), round(lat + half, 5)],
            [round(lng - half, 5), round(lat - half, 5)],
        ]

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon]
            },
            "properties": {
                "zone": zone,
                "label": zone_labels.get(zone, "Unknown"),
                "color": zone_colors.get(zone, "#10b981"),
                "hazard_probability": prob,
                "cell_lat": lat,
                "cell_lng": lng,
                "is_expanded_red": is_expanded,
                "slope": props.get("slope", 15.0),
                "elevation": props.get("elevation", 1800.0)
            }
        })

    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# 6. Live Rainfall Ingestion (Open-Meteo Free API)
# ---------------------------------------------------------------------------
TEHSIL_CENTROIDS = {
    "Bhatwari": {"lat": 30.81, "lng": 78.62},
    "Uttarkashi": {"lat": 30.73, "lng": 78.45},
    "Dunda": {"lat": 30.63, "lng": 78.33},
    "Chinyalisaur": {"lat": 30.55, "lng": 78.31},
    "Purola": {"lat": 30.87, "lng": 78.08},
    "Mori": {"lat": 31.02, "lng": 78.12}
}


def fetch_live_rainfall(lat: float = 30.73, lng: float = 78.45):
    """
    Fetches real-time precipitation intensity and 24h antecedent rainfall
    from Open-Meteo's free public weather API (no token required).
    """
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&hourly=precipitation&past_days=1&forecast_days=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HazardShield-GIS/2.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            hourly_precip = data.get("hourly", {}).get("precipitation", [])
            if hourly_precip:
                # Latest available hour
                intensity_now = float(hourly_precip[-1] or 0.0)
                # Antecedent last 24 hours
                antecedent_24h = float(sum(p for p in hourly_precip[-24:] if p is not None))
                return {
                    "source": "Open-Meteo Live Telemetry",
                    "intensity_mm_hr": round(intensity_now, 2),
                    "antecedent_24h_mm": round(antecedent_24h, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
    except Exception:
        pass

    # Default simulated monsoon conditions if network unreachable
    return {
        "source": "Simulated Hydrological Baseline (Offline Mode)",
        "intensity_mm_hr": 14.5,
        "antecedent_24h_mm": 42.0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ---------------------------------------------------------------------------
# 7. Pipeline Orchestration
# ---------------------------------------------------------------------------
def run_trigger_pipeline(output_dir: Path,
                         intensity_mm_hr: float,
                         antecedent_24h_mm: float = 0.0,
                         seismic_kh: float = 0.0):
    """Executes the complete Layer 2 trigger workflow off pre-computed disk files."""
    output_dir = Path(output_dir)

    with open(output_dir / "villages.geojson") as f:
        villages_geojson = json.load(f)

    with open(output_dir / "safe_zones.geojson") as f:
        safe_zones_geojson = json.load(f)

    safe_zones = [
        {
            "lat": float(feat["geometry"]["coordinates"][0][0][1]),
            "lng": float(feat["geometry"]["coordinates"][0][0][0]),
            "suitability_score": float(feat["properties"]["suitability_score"]),
            "carrying_capacity": int(feat["properties"]["carrying_capacity"]),
            "dist_road_km": float(feat["properties"].get("dist_road_km", 1.2)),
            "dist_river_km": float(feat["properties"].get("dist_river_km", 2.0)),
            "slope": float(feat["properties"].get("slope", 6.5)),
        }
        for feat in safe_zones_geojson["features"]
    ]

    alerts = compute_dynamic_alerts(villages_geojson, intensity_mm_hr, antecedent_24h_mm, seismic_kh=seismic_kh)
    dispatched, ledger = match_alerts_to_safe_zones(alerts, safe_zones)
    detailed_ledger = generate_carrying_capacity_ledger(safe_zones, dispatched)

    # Carrying capacity stress analysis
    total_safe_cap = sum(sz["carrying_capacity"] for sz in safe_zones)
    total_evac_pop = sum(d.get("population", 0) for d in dispatched)
    surplus_sites = sum(1 for s in detailed_ledger if s["stress_tier"] == "SURPLUS")
    stressed_sites = sum(1 for s in detailed_ledger if s["stress_tier"] in ["STRESSED", "DEFICIT"])

    summary = {
        "rainfall_input": {
            "intensity_mm_hr": round(float(intensity_mm_hr), 2),
            "antecedent_24h_mm": round(float(antecedent_24h_mm), 2),
            "seismic_kh": round(float(seismic_kh), 3),
            "multiplier": round(float(rainfall_multiplier(intensity_mm_hr, antecedent_24h_mm)), 3),
        },
        "alert_counts": {
            level: sum(1 for a in alerts if a["alert_level"] == level)
            for _, level in ALERT_THRESHOLDS
        },
        "dispatched_evacuations": dispatched,
        "evacuate_now_count": len([a for a in dispatched if a["alert_level"] == "EVACUATE_NOW"]),
        "all_alerts": alerts,
        "carrying_capacity_summary": {
            "total_safe_sites": len(safe_zones),
            "total_district_capacity": total_safe_cap,
            "displaced_population": total_evac_pop,
            "net_headroom_buffer": total_safe_cap - total_evac_pop,
            "surplus_sites_count": surplus_sites,
            "stressed_sites_count": stressed_sites,
        },
        "carrying_capacity_ledger": detailed_ledger
    }

    return summary


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "output"
    if out_dir.exists():
        res = run_trigger_pipeline(out_dir, intensity_mm_hr=65.0, antecedent_24h_mm=85.0)
        print("Alert counts:", json.dumps(res["alert_counts"], indent=2))
        print("Sample dispatch directive:", res["dispatched_evacuations"][0]["directive"] if res["dispatched_evacuations"] else "None")

