# BhuRakshak: Geospatial Multi-Hazard Intelligence & Statutory Relocation Platform
## Complete Technical Architecture, Mathematical Foundations & RAG Knowledge Document
**Target District:** Uttarkashi District, Uttarakhand, India (Garhwal Himalayas)  
**Problem Statement:** Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations  
**Statutory Framework:** Disaster Management Act, 2005 (Sections 30 & 34) & NDMA Hilly Terrain Guidelines  
**System Specification Version:** 3.2.0 (Boundary-Verified & Real-Time Ready)  

---

## 1. Executive Summary & Problem Context

### Background & Objective
Disaster-prone mountainous terrains in India—particularly in the young, tectonically active Garhwal Himalayas—face frequent, recurring multi-hazard events including orographic cloudbursts, rainfall-induced debris flows, flash floods, seismic slope failures, and glacial lake outburst floods (GLOFs). 

Traditionally, state administrative response has remained largely **reactive**: evacuation and relief operations initiate *after* hillsides fail or rivers breach, resulting in severe casualties and infrastructure wipeouts.

**BhuRakshak** transforms disaster management from reactive relief to **proactive, evidence-based, geospatial decision support**:
1. **Dynamic Red Zone Zonation:** Continuously updates spatial hazard zones (Red, Orange, Yellow, Green) using physical terrain metrics, satellite hydrology, and real-time precipitation/seismic triggers.
2. **Carrying Capacity Assessment:** Evaluates safe alternative reception sites against NDMA hilly terrain resettlement standards (45 m²/person, slope < 14°, minimum 70 LPCD potable water, road egress).
3. **Actionable Relocation Prioritization:** Prioritizes vulnerable habitations into Immediate (< 30 days), Short-term (1–6 months), and Medium-term (6–24 months) phases with verifiable SDRF/PMAY-G rehabilitation budgeting.

---

## 2. Geography of Uttarkashi District

### Administrative & Tectonic Setting
- **Coordinates:** $30.45^\circ\text{N} - 31.45^\circ\text{N}$, $77.85^\circ\text{E} - 79.05^\circ\text{E}$.
- **Jurisdiction Area:** $8,016\text{ km}^2$ across 6 administrative tehsils: *Bhatwari, Dunda, Purola, Mori, Chinyalisaur, Barkot*.
- **Elevation Range:** 1,126 m AMSL (Uttarkashi town river terrace) to over 7,000 m AMSL (Gangotri & Garhwal massifs).
- **Drainage Basins:** Origin point of the holy headstreams: Bhagirathi River (fed by Gaumukh Glacier) and Yamuna River.
- **Tectonic Vulnerability:** Traversed longitudinally by the **Main Central Thrust (MCT)** fault zone, placing the entire district in **Seismic Zone V / IV** (highest peak ground acceleration risk).
- **Lifeline Corridors:** National Highway 108 (Gangotri Axis) and NH-507 (Yamunotri Axis), essential for the annual Char Dham pilgrimage and high-altitude national border logistics.

### Point-in-Polygon Boundary Verification
- A naive bounding-box sweep over $[30.45, 31.45] \times [77.85, 79.05]$ produces 3,111 grid points, of which 50.7% lie outside the district (spilling into Tibet, Himachal Pradesh, Rudraprayag, and Tehri Garhwal).
- BhuRakshak strictly clips the terrain grid against the official GADM Level 3 / GAUL ADM2 boundary polygon, producing exactly **1,534 authentic cells** at $0.02^\circ$ resolution ($\approx 2.2\text{ km}$ spacing).
- All 51 statutory Census 2011 habitations are verified and audited against this boundary.

---

## 3. Authentic Data Sources & Geospatial Ingestion Pipeline

BhuRakshak replaces synthetic proxies with genuine, multi-source earth observation data:

| Dimension | Primary Authentic Data Source | Resolution / Cadence | Purpose in Model |
| :--- | :--- | :--- | :--- |
| **Digital Elevation Model (DEM)** | NASA SRTM Global 1 Arc-Second (30m) | 30.8m Spatial Resolution | Slope, Aspect, Profile Curvature, Elevation |
| **Topographic Wetness (TWI)** | Hydrological Flow Accumulation ($ln(a / \tan\beta)$) | 30m Grid Derived | Soil water pooling & saturation susceptibility |
| **Vegetation Health / Scarring** | Copernicus Sentinel-2 Optical (Bands 4 & 8) | 10m Spatial (~5-day revisit) | NDVI calculation: $NDVI = \frac{NIR - RED}{NIR + RED}$ |
| **Drainage Network** | HydroSHEDS / HydroRIVERS Official Network | 979 verified river reaches | Exact Euclidean distance to perennial river talwegs |
| **Road Network** | OpenStreetMap (OSM) Highway Vector Cache | Verified Major & Secondary Roads | Egress distance & emergency vehicle access |
| **Population Density** | Census 2011 + WorldPop High-Resolution | 100m Grid (~6,623 surveyed pop) | Human exposure weighting & displacement calculation |
| **Live Precipitation & Saturation** | Open-Meteo & IMD Doppler Weather Radar / CHIRPS | Daily accumulation & live mm/hr | Dynamic pore-water pressure & rainfall multiplier |
| **Seismic Shaking Acceleration** | USGS FDSNWS API & Wadia Institute (WIHG) | Live $k_h$ coefficient ($0.0g - 0.45g$) | Pseudo-static earthquake inertial driving force |
| **Historical Disasters Benchmark** | GSI Bhukosh & USDMA Disaster Inventory | 18 Ground-Truth Disasters (1991–2024) | Empirical accuracy validation (100% recall) |

---

## 4. Mathematical & Scientific Modeling Core

The hazard classification is computed using a defensible **Tri-Modal Fusion Framework** combining physics, multi-criteria decision analysis, and machine learning:

### Component 1: Mohr-Coulomb Geotechnical Physics (Limit Equilibrium)
Evaluates slope stability by computing the ratio of resisting shear strength ($\tau_f$) to driving shear stress ($\tau_d$):

$$FS = \frac{c' + (\sigma' \cdot \tan\phi')}{\tau_d}$$

Where:
- Effective Normal Stress: $\sigma' = \gamma \cdot z \cdot \cos^2\beta - u - \gamma \cdot z \cdot k_h \cdot \sin\beta \cdot \cos\beta$
- Dynamic Pore Water Pressure ($u$): Generated dynamically from rainfall intensity ($I$) and 24h antecedent moisture ($S$):
  $$u = \min\left(22.0, \frac{I}{100} \cdot 12.0 + \frac{S}{150} \cdot 10.0\right)\text{ kPa}$$
- Driving Shear Stress: $\tau_d = \gamma \cdot z \cdot \sin\beta \cdot \cos\beta + \gamma \cdot z \cdot k_h \cdot \cos^2\beta$
- Standard Geotechnical Parameters (GSI Garhwal Colluvium Baseline):
  - $c' = 12.5\text{ kPa}$ (Effective soil cohesion)
  - $\phi' = 33.0^\circ$ (Effective internal friction angle)
  - $\gamma = 19.5\text{ kN/m}^3$ (Saturated soil unit weight)
  - $z = 2.5\text{ m}$ (Critical slip plane failure depth)
  - $k_h = 0.0g - 0.35g$ (Pseudo-static horizontal seismic acceleration)

**Non-Negotiable Safety Floor Guardrail:**
$$\text{If } FS < 1.0 \implies \text{Mandatory Structural Failure} \implies \text{Fused Hazard} \ge 0.75 \text{ (FORCED RED ZONE)}$$
$$\text{If } FS < 1.25 \implies \text{Marginal Stability} \implies \text{Fused Hazard} \ge 0.52 \text{ (FORCED ORANGE ZONE)}$$

### Component 2: Saaty Analytic Hierarchy Process (AHP)
AHP pairwise comparison matrix eigenvector decomposition derived under Saaty (1980):
- **Consistency Ratio:** $CR = 0.0106 < 0.10$ (Statistically proven free of circular subjective bias).
- **Factor Weights:**
  1. Slope Angle: **30.15%**
  2. Concave Curvature: **16.52%**
  3. Topographic Wetness Index (TWI): **13.41%**
  4. Precipitation Intensity: **12.87%**
  5. Distance to River Talweg: **10.24%**
  6. Proximity to Historical Disaster Scars: **8.92%**
  7. Barren Vegetation ($1 - NDVI$): **4.58%**
  8. Road Disturbance Line: **3.31%**

### Component 3: Machine Learning Susceptibility (GBDT)
- Gradient-Boosted Decision Trees trained on topographic features validated through Spatial Block Cross-Validation (eliminating spatial autocorrelation overfitting).
- Outputs $P_{\text{ML}} \in [0.0, 1.0]$.

### Component 4: Tri-Modal Fusion Formula
$$\text{Fused Hazard} = 0.40 \cdot \text{AHP} + 0.40 \cdot P_{\text{ML}} + 0.20 \cdot \left(1.0 - \frac{FS}{2.2}\right)$$
Subject to the non-negotiable Mohr-Coulomb physics safety override.

---

## 5. Dynamic Trigger Pipeline (Real-Time Rain & Seismic Surge)

Static hazard maps fail during cloudburst events. BhuRakshak dynamically scales hazard probabilities in real time using the **NASA LHASA + IMD formulation**:

1. **Intensity Factor:**
   $$F_{\text{int}} = 1.0 + \frac{\max(0, I - 35.0)}{70.0} \times 0.65$$
2. **Antecedent Soil Moisture Factor:**
   $$F_{\text{ant}} = 1.0 + \frac{\max(0, S - 40.0)}{80.0} \times 0.45$$
3. **Composite Rainfall Multiplier:**
   $$M_{\text{rain}} = \min(2.25, F_{\text{int}} \times F_{\text{ant}})$$
4. **Seismic Amplification:**
   $$M_{\text{seismic}} = 1.0 + \max(0.0, k_h \times 1.8)$$
5. **Orographic Funneling:**
   - 12% amplification applied to elevations between $1,500\text{ m}$ and $2,800\text{ m}$ AMSL when rainfall intensity exceeds $50\text{ mm/hr}$ (reflecting cloudburst trapping against Garhwal ridges).

---

## 6. Carrying Capacity Assessment & Resettlement Engine

Relocating vulnerable populations requires safe, viable destination sites with positive absorptive capacity.

### NDMA Safe Site Criteria
A cell or area qualifies as a **Green Zone Safe Haven** only if it satisfies all statutory constraints:
1. **Terrain Slope:** $\beta < 14^\circ$ (Flat to gentle terrace; prevents secondary slope failure).
2. **Flood Clearance:** Buffer $> 300\text{ m}$ horizontal and $> 30\text{ m}$ vertical from perennial riverbeds.
3. **Geotechnical Factor of Safety:** $FS \ge 1.5$ under maximum monsoon saturation ($u = 15\text{ kPa}$).
4. **Land Cover:** Scrubland, open terrace, or non-forested plateau (avoiding ecologically sensitive reserves).
5. **Lifeline Road Connectivity:** Within $\le 1.5\text{ km}$ of motorable PMGSY or NH roads.

### Carrying Capacity Calculation
Each designated safe zone has its buildable area ($A_{\text{buildable}}$ in $\text{m}^2$) computed from satellite polygons:
$$\text{Carrying Capacity (persons)} = \left\lfloor \frac{A_{\text{buildable}}}{45\text{ m}^2} \right\rfloor$$
*(Where $45\text{ m}^2/\text{person}$ adheres to the NDMA Hill Relocation Standard for living shelters, water staging, sanitation, and internal transit).*

### Overflow Redistribution Ledger
- Across Uttarkashi, BhuRakshak identifies **130 Safe Haven candidate sites** offering a combined carrying capacity of **471,956 persons**.
- For habitations requiring evacuation, the engine matches each village to the nearest safe haven using Dijkstra road/terrain paths.
- As villages are assigned, the destination's remaining capacity headroom is deducted:
  $$\text{Headroom}_{\text{remaining}} = \text{Capacity}_{\text{total}} - \sum \text{Population}_{\text{assigned}}$$
- Once a haven hits saturation ($\text{Headroom} \le 0$), subsequent overflowing habitations are automatically routed to the next-nearest safe haven with positive headroom.

---

## 7. Actionable Statutory Directives (DM Act 2005)

Habitations are prioritized into clear statutory action tiers based on Fused Hazard Score and Mohr-Coulomb Factor of Safety:

| Urgency Tier | Technical Criterion | Timeframe | Statutory Directive (DM Act 2005) | SDRF Rehab Grant |
| :--- | :--- | :--- | :--- | :--- |
| **Immediate (Tier 1)** | $FS < 1.0$ OR Score $\ge 0.65$ | **0 – 30 Days** | Section 30 & 34: Issue mandatory evacuation order; dispatch SDRF/QRT; stage transit camps at Safe Site Alpha. | ₹7.0 Lakhs / HH + ₹25,000 emergency grant |
| **Short-Term (Tier 2)** | $FS < 1.25$ OR Score $\ge 0.48$ | **1 – 6 Months** | Pre-Monsoon Relocation: Complete cadastral demarcation of permanent terrace plots at safe havens; initiate PMAY-G hill housing. | ₹7.0 Lakhs / HH (Direct Benefit Transfer) |
| **Medium-Term (Tier 3)** | $FS \ge 1.25$ AND Score $< 0.48$ | **6 – 24 Months** | Engineered Slope Mitigation: Construct toe-retaining gabion walls, catch-water drains, and deep-rooted bioengineering stabilization. | Infrastructure Grant under NDMA Mitigation Fund |

---

## 8. Summary of API Endpoints for Integration

- `POST /hazard-score` — Single coordinate calculation with boundary verification, returning AHP, ML probability, Mohr-Coulomb FoS, and feature provenance.
- `POST /assess-habitations` — Batch scoring for all 51 habitations under dynamic rainfall and seismic conditions.
- `POST /simulate` — Updates the entire $0.02^\circ$ spatial grid and generates dynamic red zone polygons with carrying capacity balance.
- `GET /api/carrying-capacity/ledger` — Site-by-site capacity ledger with remaining headroom and stress status.
- `GET /api/dm-action-plan` — Official executive relocation briefing and SDRF financial allocation matrix for the District Magistrate.
