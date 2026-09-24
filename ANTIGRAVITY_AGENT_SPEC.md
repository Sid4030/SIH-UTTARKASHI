# Antigravity Agent Specification & Architecture Guide
## BhuRakshak: Geospatial Multi-Hazard Intelligence & Statutory Relocation Platform
**Target District:** Uttarkashi District, Uttarakhand, India  
**Statutory Framework:** Disaster Management Act, 2005 (Sections 30 & 34)  
**System Specification Version:** 3.2.0 (Boundary-Verified & Real-Time Ready)

---

## 1. Upgraded Antigravity Prompt (Production-Ready)

```text
Context: Disaster-hazard scoring pipeline for Uttarkashi district (SIH problem statement 26191). Backend logic prototyped in Colab: AHP-weighted susceptibility (ahp_weights.json, includes Consistency Ratio CR=0.0106), a gradient-boosted classifier (gbdt_classifier.pkl + feature_list.pkl) validated via spatial cross-validation, and a Mohr-Coulomb Factor-of-Safety physics constraint. Grid data is strictly boundary-verified against the exact Uttarkashi administrative polygon (uttarkashi_terrain_grid_boundary_clipped.csv) — do not regenerate grid points using a bounding box; only points that pass point-in-polygon against the district boundary are valid.

Build a FastAPI service with these endpoints, as pure functions taking explicit arguments — no notebook-global dependencies:

1. POST /hazard-score — single lat/lon. Reject or flag any coordinate outside the Uttarkashi boundary polygon (load the unified GeoJSON boundary used for grid clipping; run the same .within() check server-side, don't trust caller input).
2. POST /assess-habitations — batch scoring, returns per-village: fused hazard score, AHP component, ML probability component, Factor-of-Safety, stability tier, and urgency tier (Immediate / Short-term / Medium-term, banded from hazard score + FoS).
3. POST /relocation-plan — match villages to hazard scores by village ID/name via merge, never by list position (there's a known bug in prototype implementations where sorting broke positional index alignment — don't reproduce it). Enforce a destination carrying-capacity ceiling: a safe cell has a maximum population it can absorb; once full, route to the next-nearest cell.
4. GET /grid-status — returns grid point count, boundary source (GAUL ADM2 / GADM 4.1 Uttarkashi), and last-refreshed timestamp for live-pulled layers, so the frontend can show data freshness.

Real-time data handling:
- GEE auth via service account JSON key (GEE_SERVICE_ACCOUNT_JSON), initialized once at startup — never ee.Authenticate().
- Every response must mark each input feature's data_source as "live" or "default" — never silently substitute a fallback value without flagging it.
- State actual refresh cadence honestly: Sentinel-2 NDVI refreshes on its ~5-day revisit cycle, CHIRPS rainfall refreshes daily. Don't imply sub-second "live" — label it "last satellite pass: [date]."
- Cache GEE responses per grid cell for at least one full revisit cycle; don't re-query GEE per user request.

Precision / boundary requirements:
- All grid points, habitation coordinates, and safe-zone candidates must be validated against the exact Uttarkashi GAUL ADM2 polygon at load time, not assumed correct from the CSV.
- If a habitation record falls outside the boundary, flag it in logs rather than silently including or dropping it — I need to know if my source data has bad coordinates.

Non-negotiables:
- Keep the Factor-of-Safety override (FoS < 1.0 forces a minimum hazard score >= 0.75 RED ZONE) — this is an intentional physics safety floor, not a bug to optimize away.
- Return AHP score, ML probability, and FoS as separate fields in every response — never collapse to just the fused number. This needs to be explainable to a government reviewer, not a black box.
- If the trained neural net (engine_b_nn) isn't part of the fusion formula, don't wire it in silently — tell me explicitly so I decide whether it's in or out.
```

---

## 2. Point-in-Polygon Boundary Verification Audit

### Why the Bounding-Box Rectangular Sweep Fails
A simple bounding-box grid sweep over Uttarkashi:
- Bounding Box: $[30.45^\circ\text{N}, 31.45^\circ\text{N}] \times [77.85^\circ\text{E}, 79.05^\circ\text{E}]$ at $0.02^\circ$ resolution produces **3,111 cells**.
- **Audit Result:** Exactly **1,577 of those points (50.7%) lie OUTSIDE Uttarkashi** — bleeding into Tehri Garhwal, Rudraprayag, Chamoli, Dehradun, Himachal Pradesh, and Tibet.
- **The Fix:** Point-in-polygon (`district_polygon.contains(Point(lng, lat))`) using the unified GADM 4.1 / GAUL ADM2 boundary polygon yields exactly **1,534 authentic cells**.

### Habitation Boundary Audit Log
When testing the 51 statutory Census 2011 habitations against the GADM boundary polygon:
- **46 habitations are strictly inside the boundary.**
- **5 border habitations lie 1.7 to 10.3 km outside the GADM Level 3 line** along the southern boundary (Chinyalisaur, Lakhwar, Jakhol Chinyalisaur, Dharasu, Barethi).
- **Handling Policy:** These 5 border habitations are flagged in the server logs (`boundary_audit_warnings`) with their distance and coordinates, ensuring source data transparency rather than silent inclusion or silent dropping.

---

## 3. Mathematical Foundations

### Component 1: Mohr-Coulomb Geotechnical Physics Constraint
Evaluates the ratio of resisting shear strength ($\tau_f$) to driving shear stress ($\tau_d$):

$$FS = \frac{c' + (\gamma \cdot z \cdot \cos^2\beta - u - \gamma \cdot z \cdot k_h \cdot \sin\beta \cdot \cos\beta) \cdot \tan\phi'}{\gamma \cdot z \cdot \sin\beta \cdot \cos\beta + \gamma \cdot z \cdot k_h \cdot \cos^2\beta}$$

Where:
- $c' = 12.5\text{ kPa}$ (Effective soil cohesion for Garhwal colluvium)
- $\phi' = 33^\circ$ (Internal friction angle)
- $\gamma = 19.5\text{ kN/m}^3$ (Saturated unit weight)
- $z = 2.5\text{ m}$ (Regolith slip plane failure depth)
- $u$ = Dynamic pore water pressure (rises during heavy monsoon rain)
- $k_h$ = Pseudo-static horizontal seismic acceleration coefficient ($0.0g$ to $0.35g$)

**The Non-Negotiable Safety Floor:**
If $FS < 1.0$, shear failure is mathematically guaranteed. Even if the ML model outputs a low probability, the safety floor forces the fused hazard score to **$\ge 0.75$ (RED ZONE)**.

### Component 2: Analytic Hierarchy Process (Saaty, 1980)
- Derived via principal eigenvector decomposition of pairwise comparison matrices.
- **Consistency Ratio:** $CR = 0.0106 < 0.10$ (Mathematically valid, free of circular bias).
- **Factor Weights:**
  - Slope: $30.15\%$
  - Concave Curvature: $16.52\%$
  - Topographic Wetness Index (TWI): $13.41\%$
  - Precipitation Intensity: $12.87\%$
  - River Proximity: $10.24\%$
  - Historical Disaster Proximity: $8.92\%$
  - Barren / Degraded Vegetation (1 - NDVI): $4.58\%$
  - Road Disturbance Proximity: $3.31\%$

### Component 3: Tri-Modal Fusion Formula
$$\text{Fused Hazard} = 0.40 \cdot \text{AHP} + 0.40 \cdot P_{\text{ML}} + 0.20 \cdot \left(1.0 - \frac{FS}{2.2}\right)$$
Subject to:
$$\text{If } FS < 1.0 \implies \text{Fused Hazard} \leftarrow \max(\text{Fused Hazard}, 0.75) \quad [\text{RED ZONE}]$$
$$\text{If } FS < 1.25 \implies \text{Fused Hazard} \leftarrow \max(\text{Fused Hazard}, 0.52) \quad [\text{ORANGE ZONE}]$$

---

## 4. Complete API Endpoint Specification

### `POST /hazard-score`
**Input:**
```json
{
  "latitude": 30.727,
  "longitude": 78.445,
  "slope": 28.5,
  "rainfall_intensity": 75.0,
  "antecedent_saturation": 60.0,
  "seismic_kh": 0.05
}
```
**Output (Sample):**
```json
{
  "status": "SUCCESS",
  "coordinates": { "latitude": 30.727, "longitude": 78.445 },
  "is_within_boundary": true,
  "hazard_score": 0.599,
  "zone": "orange",
  "statutory_directive": "HIGH RISK / PRE-MONSOON STAGING (ORANGE ZONE)",
  "physics_override_active": false,
  "breakdown": {
    "ahp_score": 0.5666,
    "ahp_consistency_ratio": 0.0106,
    "ml_probability": 0.7479,
    "ml_model_status": "GBDT_INFERENCE_SUCCESS",
    "factor_of_safety": 1.395,
    "stability_tier": "STABLE",
    "pore_pressure_kpa": 13.0
  },
  "feature_data_sources": {
    "slope": "user_input",
    "elevation": "srtm_30m_dem",
    "rainfall_intensity": "user_input",
    "ndvi": "sentinel2_optical"
  }
}
```

### `POST /assess-habitations`
- Scores habitations in batch.
- Returns `urgency_tier`: `"Immediate"` ($FS < 1.0$ or Score $\ge 0.65$), `"Short-term"` ($FS < 1.25$ or Score $\ge 0.48$), `"Medium-term"`.
- Logs any coordinates outside the boundary polygon.

### `POST /relocation-plan`
- **Non-positional matching:** Merges by `village_id` and `name` — never by array index.
- **Carrying-Capacity Ceilings:** Deducts each village's population from safe havens; once a haven is saturated, dynamically routes to the next nearest safe haven with remaining capacity headroom.

### `GET /grid-status`
- Reports verified grid point count ($1,534$ points), boundary source, and data freshness timestamps.
- States actual satellite cadences: Sentinel-2 (~5-day pass) and CHIRPS/IMD (daily accumulation).

---

## 5. Artifact Directory

All production files are exported and available in:
```
backend/output/colab_export/
├── gbdt_classifier.pkl                     # Trained GBDT Scikit-Learn Model
├── feature_list.pkl                        # Feature Names (11 Inputs)
├── ahp_weights.json                        # Saaty AHP Weights & Consistency Ratio
├── uttarkashi_terrain_grid_boundary_clipped.csv # 1,534 boundary-verified grid points
├── uttarkashi_historical_disasters_18.csv  # 18 verified ground-truth disaster events
├── uttarkashi_habitations_census2011_51.csv# 51 official Census habitations
└── uttarkashi_hazard_scoring_colab.ipynb   # Complete Colab Training Notebook
```
