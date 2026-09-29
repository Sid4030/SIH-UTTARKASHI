"""
BhuRakshak — AI Region Summarizer Engine
==========================================
Generates structured natural-language hazard summaries for every grid cell,
village, and corridor segment. Each summary connects:
  - THRIVE multi-hazard probability decomposition
  - AHP eigenvector weight attribution
  - Mohr-Coulomb Factor of Safety status
  - Historical disaster proximity & recurrence
  - Live trigger multiplier (rainfall + seismic)
  - Recommended actions (evacuation, monitoring, mitigation)

Used by:
  1. /api/ai/region-summary — per-location on-demand summaries
  2. RAG knowledge base — pre-indexed for chatbot retrieval
  3. Grid descriptions — embedded in hazard-grid GeoJSON properties
"""

import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output"


# ============================================================================
# Terrain Description Templates
# ============================================================================

SLOPE_DESCRIPTIONS = [
    (45, "extremely steep ({val}°) cliff-face terrain prone to rockfall and rapid debris slides"),
    (35, "very steep ({val}°) mountain slope with high translational slide susceptibility"),
    (25, "moderately steep ({val}°) hillside with significant mass movement potential"),
    (15, "gentle-to-moderate ({val}°) slope with limited landslide risk"),
    (8,  "mild ({val}°) gradient suitable for monitored habitation"),
    (0,  "near-flat ({val}°) terrain with negligible slope failure risk"),
]

ELEVATION_BANDS = [
    (3000, "high-altitude alpine zone ({val}m) above the treeline — exposed to frost shattering and periglacial debris flows"),
    (2500, "upper subalpine zone ({val}m) — within the orographic cloudburst funneling corridor (1,500–2,800m)"),
    (1800, "mid-elevation montane zone ({val}m) — moderate monsoon precipitation, mixed forest cover"),
    (1200, "lower valley floor ({val}m) — susceptible to flash flood inundation from upstream catchment runoff"),
    (0,    "low-elevation river terrace ({val}m) — potential safe resettlement terrain if slope < 14°"),
]

ZONE_NARRATIVES = {
    "red": "classified as a **Red Zone** (Multi-Hazard Prohibited Area) — permanent habitation is statutorily prohibited under DM Act 2005 Sec 30/34. Immediate evacuation is mandated.",
    "orange": "classified as an **Orange Zone** (High Hazard Buffer) — under active monitoring with restricted new construction. Short-term relocation planning is underway.",
    "yellow": "classified as a **Yellow Zone** (Moderate Hazard Cautionary) — habitation is permitted with structural mitigation measures (bio-engineering retaining walls, drainage improvements).",
    "green": "classified as a **Green Zone** (Safe Terrain) — geotechnically stable, suitable for permanent habitation and potential resettlement receiving site.",
}

FOS_NARRATIVES = {
    "critical": "The Mohr-Coulomb Factor of Safety is **{val:.2f}** (< 1.0), indicating **active shear failure conditions** — the slope is physically failing and collapse is imminent or ongoing.",
    "marginal": "The Mohr-Coulomb Factor of Safety is **{val:.2f}** (1.0–1.5), indicating **marginally stable conditions** — any increase in pore water pressure or seismic loading will trigger failure.",
    "stable": "The Mohr-Coulomb Factor of Safety is **{val:.2f}** (1.5–2.5), indicating **conditionally stable terrain** under current moisture and seismic conditions.",
    "safe": "The Mohr-Coulomb Factor of Safety is **{val:.2f}** (> 2.5), indicating **geotechnically safe terrain** with substantial shear strength reserve.",
}


def _describe_slope(slope: float) -> str:
    for threshold, template in SLOPE_DESCRIPTIONS:
        if slope > threshold:
            return template.format(val=round(slope, 1))
    return SLOPE_DESCRIPTIONS[-1][1].format(val=round(slope, 1))


def _describe_elevation(elev: float) -> str:
    for threshold, template in ELEVATION_BANDS:
        if elev > threshold:
            return template.format(val=round(elev))
    return ELEVATION_BANDS[-1][1].format(val=round(elev))


def _describe_fos(fos: float) -> str:
    if fos < 1.0:
        return FOS_NARRATIVES["critical"].format(val=fos)
    elif fos < 1.5:
        return FOS_NARRATIVES["marginal"].format(val=fos)
    elif fos < 2.5:
        return FOS_NARRATIVES["stable"].format(val=fos)
    else:
        return FOS_NARRATIVES["safe"].format(val=fos)


def _describe_zone(zone: str) -> str:
    return ZONE_NARRATIVES.get(zone, ZONE_NARRATIVES["yellow"])


def _describe_river_proximity(dist_km: float) -> str:
    if dist_km < 0.5:
        return f"Extremely close ({dist_km:.1f} km) to a major river channel — direct flash flood and toe-erosion exposure."
    elif dist_km < 2.0:
        return f"Within the active floodplain buffer ({dist_km:.1f} km from nearest river) — elevated inundation risk during monsoon surges."
    elif dist_km < 5.0:
        return f"Moderate distance ({dist_km:.1f} km) from nearest river — indirect flood risk through tributary backflow."
    else:
        return f"Well beyond river influence ({dist_km:.1f} km) — minimal direct flood exposure."


def _describe_rainfall_trigger(intensity: float, antecedent: float) -> str:
    if intensity > 100:
        return f"Under **extreme rainfall** conditions ({intensity:.0f} mm/hr intensity, {antecedent:.0f} mm 24h antecedent) — cloudburst-scale deluge triggering mass wasting across the catchment."
    elif intensity > 50:
        return f"Under **heavy rainfall** conditions ({intensity:.0f} mm/hr, {antecedent:.0f} mm antecedent) — elevated pore water pressure driving slope instability."
    elif intensity > 15:
        return f"Under **moderate rainfall** ({intensity:.0f} mm/hr, {antecedent:.0f} mm antecedent) — soil moisture accumulating but within typical monsoon range."
    else:
        return f"Under **light/dry conditions** ({intensity:.0f} mm/hr, {antecedent:.0f} mm antecedent) — baseline stability maintained."


# ============================================================================
# Contributing Factor Decomposition
# ============================================================================

def decompose_hazard_factors(
    slope: float,
    elevation: float,
    twi: float = 7.0,
    ndvi: float = 0.4,
    dist_river_km: float = 5.0,
    dist_disaster_km: float = 10.0,
    curvature: float = 0.0,
    rainfall_mm: float = 100.0,
    hazard_probability: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Decompose hazard probability into ranked contributing factors
    with human-readable severity labels.
    """
    factors = []

    # 1. Slope
    slope_contrib = min(0.35, max(0.01, (slope - 5) / 55))
    severity = "CRITICAL" if slope > 35 else "HIGH" if slope > 25 else "MODERATE" if slope > 15 else "LOW"
    factors.append({
        "factor": "Slope Steepness",
        "value": f"{slope:.1f}°",
        "contribution": round(slope_contrib, 3),
        "severity": severity,
        "explanation": _describe_slope(slope)
    })

    # 2. River Proximity
    river_contrib = max(0.0, min(0.20, (5.0 - dist_river_km) / 5.0 * 0.20))
    severity = "CRITICAL" if dist_river_km < 0.8 else "HIGH" if dist_river_km < 2 else "MODERATE" if dist_river_km < 4 else "LOW"
    factors.append({
        "factor": "River Proximity",
        "value": f"{dist_river_km:.1f} km",
        "contribution": round(river_contrib, 3),
        "severity": severity,
        "explanation": _describe_river_proximity(dist_river_km)
    })

    # 3. Historical Disaster Proximity
    disaster_contrib = max(0.0, min(0.22, (8.0 - dist_disaster_km) / 8.0 * 0.22))
    severity = "CRITICAL" if dist_disaster_km < 2 else "HIGH" if dist_disaster_km < 4.5 else "MODERATE" if dist_disaster_km < 8 else "LOW"
    factors.append({
        "factor": "Historical Disaster Proximity",
        "value": f"{dist_disaster_km:.1f} km",
        "contribution": round(disaster_contrib, 3),
        "severity": severity,
        "explanation": f"{'Within' if dist_disaster_km < 2 else 'Near'} verified disaster scar corridor — {'high' if dist_disaster_km < 4 else 'moderate'} recurrence probability."
    })

    # 4. TWI (Soil Saturation)
    twi_contrib = max(0.0, min(0.12, (twi - 5) / 10.0 * 0.12))
    severity = "HIGH" if twi > 11 else "MODERATE" if twi > 8 else "LOW"
    factors.append({
        "factor": "Topographic Wetness (TWI)",
        "value": f"{twi:.1f}",
        "contribution": round(twi_contrib, 3),
        "severity": severity,
        "explanation": f"TWI {twi:.1f} — {'high' if twi > 10 else 'moderate' if twi > 7 else 'low'} soil saturation accumulation potential."
    })

    # 5. Vegetation Cover (NDVI)
    ndvi_contrib = max(0.0, min(0.10, (0.5 - ndvi) / 0.5 * 0.10))
    severity = "HIGH" if ndvi < 0.2 else "MODERATE" if ndvi < 0.4 else "LOW"
    factors.append({
        "factor": "Vegetation Cover (NDVI)",
        "value": f"{ndvi:.2f}",
        "contribution": round(ndvi_contrib, 3),
        "severity": severity,
        "explanation": f"NDVI {ndvi:.2f} — {'barren/degraded' if ndvi < 0.2 else 'sparse' if ndvi < 0.4 else 'dense'} vegetation cover providing {'minimal' if ndvi < 0.2 else 'moderate' if ndvi < 0.4 else 'strong'} root cohesion."
    })

    # 6. Curvature
    curv_contrib = max(0.0, min(0.08, (-curvature - 0.1) / 1.5 * 0.08)) if curvature < -0.1 else 0.0
    severity = "HIGH" if curvature < -0.5 else "MODERATE" if curvature < -0.1 else "LOW"
    factors.append({
        "factor": "Slope Curvature",
        "value": f"{curvature:.2f}",
        "contribution": round(curv_contrib, 3),
        "severity": severity,
        "explanation": f"{'Concave' if curvature < -0.1 else 'Convex' if curvature > 0.1 else 'Planar'} slope geometry — {'concentrates' if curvature < -0.1 else 'sheds' if curvature > 0.1 else 'neutral'} subsurface water flow."
    })

    # Sort by contribution descending
    factors.sort(key=lambda f: f["contribution"], reverse=True)
    return factors


# ============================================================================
# Main Summary Generator
# ============================================================================

def generate_region_summary(
    grid_id: str = "G-0000",
    lat: float = 30.73,
    lng: float = 78.45,
    location_name: Optional[str] = None,
    slope: float = 24.0,
    elevation: float = 1850.0,
    curvature: float = -0.2,
    twi: float = 7.5,
    ndvi: float = 0.35,
    dist_river_km: float = 3.0,
    dist_disaster_km: float = 6.0,
    rainfall_intensity: float = 35.0,
    antecedent_24h_mm: float = 50.0,
    seismic_kh: float = 0.0,
    hazard_probability: float = 0.5,
    zone: str = "yellow",
    factor_of_safety: float = 1.8,
    ahp_score: float = 0.5,
    nearest_village: Optional[str] = None,
    nearest_safe_site: Optional[str] = None,
    population_at_risk: int = 0,
    families_at_risk: int = 0,
) -> Dict[str, Any]:
    """
    Generate a comprehensive structured AI summary for a region/grid cell.
    Returns a JSON-serializable dictionary with narrative text and metadata.
    """
    name = location_name or f"Grid Cell {grid_id}"

    # Build terrain narrative
    terrain_desc = _describe_slope(slope)
    elev_desc = _describe_elevation(elevation)
    zone_desc = _describe_zone(zone)
    fos_desc = _describe_fos(factor_of_safety)
    rain_desc = _describe_rainfall_trigger(rainfall_intensity, antecedent_24h_mm)

    # Decompose contributing factors
    factors = decompose_hazard_factors(
        slope=slope, elevation=elevation, twi=twi, ndvi=ndvi,
        dist_river_km=dist_river_km, dist_disaster_km=dist_disaster_km,
        curvature=curvature, rainfall_mm=rainfall_intensity,
        hazard_probability=hazard_probability
    )

    # Build top drivers string
    top_drivers = ", ".join([
        f"{f['factor']} ({f['severity']})" for f in factors[:3]
    ])

    # Compose full narrative
    paragraphs = []

    # Para 1: Location & Terrain
    paragraphs.append(
        f"**{name}** is located at coordinates ({lat:.4f}°N, {lng:.4f}°E) at {elevation:.0f}m elevation "
        f"in the {elev_desc.split('—')[0].strip()}. "
        f"The terrain features {terrain_desc}."
    )

    # Para 2: Zone Classification & Hazard Score
    paragraphs.append(
        f"With a multi-hazard THRIVE probability of **{hazard_probability:.2f}** "
        f"(AHP composite score: {ahp_score:.2f}), this location is {zone_desc}"
    )

    # Para 3: Geotechnical Stability
    paragraphs.append(fos_desc)

    # Para 4: Live Conditions
    paragraphs.append(rain_desc)

    # Para 5: Key Drivers
    paragraphs.append(
        f"The primary hazard drivers are: {top_drivers}."
    )

    # Para 6: Recommended Actions
    actions = _generate_actions(
        zone=zone, factor_of_safety=factor_of_safety,
        hazard_probability=hazard_probability,
        population_at_risk=population_at_risk,
        families_at_risk=families_at_risk,
        nearest_safe_site=nearest_safe_site,
        name=name
    )

    full_summary = " ".join(paragraphs)

    return {
        "grid_id": grid_id,
        "location_name": name,
        "coordinates": [round(lng, 5), round(lat, 5)],
        "elevation_m": round(elevation),
        "slope_deg": round(slope, 1),
        "hazard_score": round(hazard_probability, 4),
        "ahp_score": round(ahp_score, 4),
        "zone": zone,
        "factor_of_safety": round(factor_of_safety, 3),
        "fos_status": "ACTIVE_SHEAR_FAILURE" if factor_of_safety < 1.0 else
                      "MARGINALLY_STABLE" if factor_of_safety < 1.5 else
                      "CONDITIONALLY_STABLE" if factor_of_safety < 2.5 else "SAFE",
        "live_conditions": {
            "rainfall_intensity_mm_hr": rainfall_intensity,
            "antecedent_24h_mm": antecedent_24h_mm,
            "seismic_kh": seismic_kh,
        },
        "summary": full_summary,
        "contributing_factors": factors,
        "recommended_actions": actions,
        "population_at_risk": population_at_risk,
        "families_at_risk": families_at_risk,
        "nearest_safe_site": nearest_safe_site,
        "generated_utc": datetime.utcnow().isoformat() + "Z",
    }


def _generate_actions(
    zone: str, factor_of_safety: float, hazard_probability: float,
    population_at_risk: int, families_at_risk: int,
    nearest_safe_site: Optional[str], name: str
) -> List[str]:
    """Generate prioritized recommended actions based on hazard state."""
    actions = []

    if zone == "red":
        safe_label = nearest_safe_site or "nearest verified Alpha-site"
        if families_at_risk > 0:
            actions.append(
                f"IMMEDIATE (< 30 days): Evacuate {families_at_risk} families "
                f"({population_at_risk} citizens) from {name} to {safe_label} "
                f"under DM Act 2005 Sec 34(b)."
            )
        else:
            actions.append(
                f"IMMEDIATE: Prohibit all permanent habitation in this zone. "
                f"Relocate any remaining occupants to {safe_label}."
            )
        actions.append("Deploy automated IoT rain gauges and soil moisture sensors for 24/7 monitoring.")
        actions.append("Commission emergency geotechnical slope survey by GSI/WIHG team.")

    elif zone == "orange":
        actions.append(
            f"SHORT-TERM (1–6 months): Initiate topographical cadastral survey "
            f"for relocation terrace plots near {nearest_safe_site or 'nearest Green Zone'}."
        )
        actions.append("Restrict new construction permits. Existing structures require seismic retrofit assessment.")
        actions.append("Install at least 2 automated rain gauges at critical elevation bands.")

    elif zone == "yellow":
        actions.append("MEDIUM-TERM (6–24 months): Commission bio-engineering slope stabilization (gabion walls, jute geotextiles, vetiver grass planting).")
        actions.append("Upgrade drainage channels to prevent waterlogging-induced slope saturation.")
        actions.append("Conduct annual monsoon preparedness drills with local communities.")

    else:  # green
        actions.append("No immediate action required. Terrain is geotechnically stable for permanent habitation.")
        actions.append("Assess carrying capacity for potential resettlement receiving — verify 70 LPCD water, < 14° slope, PMGSY road access.")

    if factor_of_safety < 1.0:
        actions.insert(0, f"⚠️ CRITICAL: Factor of Safety {factor_of_safety:.2f} indicates active slope failure. Emergency evacuation protocol activated.")

    return actions


# ============================================================================
# Batch Summary Generator (for RAG knowledge base pre-computation)
# ============================================================================

def generate_all_village_summaries(villages_geojson_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Reads the villages GeoJSON and generates summaries for all habitations.
    Output is used to build the RAG vector index.
    """
    path = villages_geojson_path or (OUTPUT_DIR / "villages.geojson")
    if not path.exists():
        return []

    with open(path, "r") as f:
        villages_data = json.load(f)

    summaries = []
    for feature in villages_data.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [78.45, 30.73])

        summary = generate_region_summary(
            grid_id=props.get("id", "V-unknown"),
            lat=coords[1] if len(coords) >= 2 else 30.73,
            lng=coords[0] if len(coords) >= 2 else 78.45,
            location_name=props.get("name", "Unknown Village"),
            slope=props.get("slope", 20),
            elevation=props.get("elevation", 1500),
            curvature=props.get("curvature", 0),
            twi=props.get("twi", 7),
            ndvi=props.get("ndvi", 0.4),
            dist_river_km=props.get("dist_river_km", 5),
            dist_disaster_km=props.get("dist_disaster_km", 10),
            rainfall_intensity=props.get("rainfall_mm", 35),
            antecedent_24h_mm=50.0,
            seismic_kh=0.0,
            hazard_probability=props.get("hazard_probability", 0.3),
            zone=props.get("zone", "yellow"),
            factor_of_safety=props.get("factor_of_safety", 2.0),
            ahp_score=props.get("ahp_score", 0.4),
            nearest_village=props.get("name"),
            nearest_safe_site=props.get("safe_site_name"),
            population_at_risk=props.get("population", 0),
            families_at_risk=props.get("households", 0),
        )
        summaries.append(summary)

    return summaries


def save_summaries_for_rag(output_path: Optional[Path] = None) -> Path:
    """Generate and save all village summaries as a JSON file for RAG indexing."""
    summaries = generate_all_village_summaries()
    path = output_path or (OUTPUT_DIR / "region_summaries.json")
    with open(path, "w") as f:
        json.dump(summaries, f, indent=2)
    return path
