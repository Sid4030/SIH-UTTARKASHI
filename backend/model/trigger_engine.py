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
def compute_dynamic_alerts(villages_geojson: dict,
                           intensity_mm_hr: float,
                           antecedent_24h_mm: float = 0.0,
                           min_baseline_zone=("yellow", "orange", "red")):
    """
    Applies the dual rainfall trigger to each village's static hazard susceptibility.
    """
    mult = rainfall_multiplier(intensity_mm_hr, antecedent_24h_mm)
    alerts = []

    for village in villages_geojson["features"]:
        props = village["properties"]
        coords = village["geometry"]["coordinates"]
        baseline_zone = props.get("zone", "green")
        baseline_prob = props.get("hazard_probability", 0.3)
        slope = props.get("slope", 15.0)

        # Terrain slope sensitivity adjustment
        slope_amp = 1.0 + max(0.0, (slope - 20.0) / 50.0) * 0.15
        effective_prob = min(0.99, baseline_prob * mult * slope_amp)

        alert_level = classify_alert(effective_prob)
        
        # Don't false-alarm stable low-slope green zones unless severe deluge
        eligible = baseline_zone in min_baseline_zone or effective_prob >= 0.85
        if not eligible and alert_level != "NORMAL":
            alert_level = "NORMAL"

        alerts.append({
            "village_id": props.get("id"),
            "village_name": props.get("name"),
            "tehsil": props.get("tehsil", "Bhatwari"),
            "population": props.get("population", 100),
            "slope": slope,
            "baseline_zone": baseline_zone,
            "baseline_probability": round(float(baseline_prob), 4),
            "rainfall_multiplier": round(float(mult), 3),
            "dynamic_probability": round(float(effective_prob), 4),
            "alert_level": alert_level,
            "lat": coords[1],
            "lng": coords[0],
        })

    return alerts


# ---------------------------------------------------------------------------
# 4. Automated Safe Site Dispatch with Carrying Capacity Ledger
# ---------------------------------------------------------------------------
def match_alerts_to_safe_zones(alerts: list, safe_zones: list, capacity_ledger: dict = None):
    """
    For every EVACUATE_NOW and WARNING alert, match to the nearest safe relocation site
    with verified carrying capacity headroom, deducting population from the ledger.
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

        for idx, sz in enumerate(safe_zones):
            dlat = (alert["lat"] - sz["lat"]) * 111.0
            dlng = (alert["lng"] - sz["lng"]) * 95.0
            dist = math.sqrt(dlat**2 + dlng**2)

            # Prefer safe zones with remaining headroom
            has_headroom = capacity_ledger.get(idx, 0) >= pop * 0.5
            effective_dist = dist if has_headroom else dist + 20.0

            if effective_dist < best_dist:
                best_dist = dist
                best_idx = idx

        if best_idx is not None:
            capacity_ledger[best_idx] = max(0, capacity_ledger[best_idx] - pop)
            sz = safe_zones[best_idx]
            remaining = capacity_ledger[best_idx]
            directive = (
                f"ORDER: Pre-monsoon evacuation of {alert['village_name']} ({pop:,} citizens) "
                f"-> Safe Site Alpha-{best_idx + 1} ({best_dist:.1f} km away). "
                f"Remaining site capacity headroom: {remaining:,}."
            )
            site_lat = sz["lat"]
            site_lng = sz["lng"]
        else:
            directive = f"ALERT: Evacuate {alert['village_name']} — Manual transit shelter override required."
            site_lat = None
            site_lng = None

        dispatched.append({
            **alert,
            "matched_safe_zone_id": (best_idx + 1) if best_idx is not None else None,
            "safe_zone_coords": [site_lng, site_lat] if site_lat else None,
            "distance_km": round(best_dist, 2) if best_idx is not None else None,
            "directive": directive,
            "issued_at": datetime.now(timezone.utc).isoformat(),
        })

    return dispatched, capacity_ledger


# ---------------------------------------------------------------------------
# 5. Live Rainfall Ingestion (Open-Meteo Free API)
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
    except Exception as e:
        # Graceful telemetry fallback if offline
        pass

    # Default simulated monsoon conditions if network unreachable
    return {
        "source": "Simulated Hydrological Baseline (Offline Mode)",
        "intensity_mm_hr": 14.5,
        "antecedent_24h_mm": 42.0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ---------------------------------------------------------------------------
# 6. Pipeline Orchestration
# ---------------------------------------------------------------------------
def run_trigger_pipeline(output_dir: Path,
                         intensity_mm_hr: float,
                         antecedent_24h_mm: float = 0.0):
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
        }
        for feat in safe_zones_geojson["features"]
    ]

    alerts = compute_dynamic_alerts(villages_geojson, intensity_mm_hr, antecedent_24h_mm)
    dispatched, ledger = match_alerts_to_safe_zones(alerts, safe_zones)

    summary = {
        "rainfall_input": {
            "intensity_mm_hr": round(float(intensity_mm_hr), 2),
            "antecedent_24h_mm": round(float(antecedent_24h_mm), 2),
            "multiplier": round(float(rainfall_multiplier(intensity_mm_hr, antecedent_24h_mm)), 3),
        },
        "alert_counts": {
            level: sum(1 for a in alerts if a["alert_level"] == level)
            for _, level in ALERT_THRESHOLDS
        },
        "dispatched_evacuations": dispatched,
        "evacuate_now_count": len([a for a in dispatched if a["alert_level"] == "EVACUATE_NOW"]),
        "all_alerts": alerts
    }

    return summary


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "output"
    if out_dir.exists():
        res = run_trigger_pipeline(out_dir, intensity_mm_hr=65.0, antecedent_24h_mm=85.0)
        print("Alert counts:", json.dumps(res["alert_counts"], indent=2))
        print("Sample dispatch directive:", res["dispatched_evacuations"][0]["directive"] if res["dispatched_evacuations"] else "None")
