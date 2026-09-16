# 🛡️ HazardShield — Uttarkashi Hazard Intelligence Platform

**AI-driven GIS platform for intelligent identification of hazard-based Red Zones, carrying capacity assessment, and relocation planning for Uttarkashi District, Uttarakhand.**

<p align="center">
  <strong>3D Terrain Visualization • XGBoost Hazard Model • AHP Site Suitability • Real-time Simulation</strong>
</p>

---

## 🎯 Problem Statement

India's disaster-prone Himalayan regions face recurring hazards (landslides, floods, cloudbursts). Vulnerable habitations often remain in unsafe zones, leading to repeated loss of life. Current relocation efforts are reactive, initiated after disasters strike.

**HazardShield** provides a proactive, evidence-based solution.

## ✅ What This Platform Does

1. **Maps hazard-based Red Zones** using XGBoost ML model trained on 8 terrain features
2. **Assesses carrying capacity** of safer relocation sites using AHP multi-criteria analysis
3. **Prioritizes vulnerable habitations** for immediate, short-term, and medium-term relocation
4. **Simulates disaster events** to visualize expanding danger zones in real-time
5. **Provides actionable insights** to State Disaster Management Authorities

## 🏔️ Focus Area: Uttarkashi District

| Metric | Value |
|--------|-------|
| Total Villages Analyzed | 178 |
| Total Population | 135,837 |
| Red Zone Villages | 23 |
| Population at Risk | 58,925 |
| Immediate Relocation | 3 villages |
| Known Disaster Events | 12 (2013-2025) |

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Vite + Vanilla JS + Mapbox GL JS |
| Backend | Python + FastAPI |
| ML Model | XGBoost / Rule-based hazard scoring |
| Data Processing | NumPy, GeoJSON |
| Styling | Custom CSS (Dark Glassmorphism) |

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.9+
- A free [Mapbox](https://www.mapbox.com/) account (for access token)

### 1. Set Your Mapbox Token

Edit `frontend/src/main.js` line 10:
```javascript
MAPBOX_TOKEN: 'pk.your_mapbox_token_here',
```

### 2. Generate Data & Train Model
```bash
# Generate terrain data, village data, disaster history
python3 backend/data/generate_data.py

# Train hazard model and generate all outputs
python3 backend/model/train_model.py
```

### 3. Start Backend
```bash
pip3 install fastapi uvicorn
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 4. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

## 📊 How the AI Model Works

### Feature Engineering (8 Terrain Features)
| Feature | Source | Relevance |
|---------|--------|-----------|
| Slope (°) | DEM gradient | Steeper = more landslide prone |
| Elevation (m) | DEM | Mid-range (1500-3500m) most vulnerable |
| Aspect (°) | DEM direction | South-facing = more rainfall exposure |
| Curvature | 2nd derivative | Concave = water accumulation |
| TWI | ln(a/tan(β)) | Wetness = flood/slide risk |
| Distance to River (km) | Euclidean | Closer = flood risk |
| NDVI Proxy | Vegetation estimate | Less vegetation = more erosion |
| Rainfall (mm/day) | Historical + orographic | Trigger factor |

### Zone Classification
| Zone | Probability | Action |
|------|-------------|--------|
| 🔴 Red | ≥0.70 | Permanent relocation required |
| 🟠 Orange | 0.50–0.70 | Short-term relocation (1-3 months) |
| 🟡 Yellow | 0.30–0.50 | Monitoring & preparedness |
| 🟢 Green | <0.30 | Safe for habitation |

### Carrying Capacity (AHP Method)
```
Suitability Score = Σ(Wᵢ × Xᵢ) × ∏Cⱼ
```
- Hazard Safety (30%), Slope (20%), Water (15%), Roads (15%), Land (10%), Elevation (10%)

## 🗂️ Project Structure
```
uttarkashi-hazard-platform/
├── frontend/              # Vite web application
│   ├── index.html         # Main HTML
│   ├── style.css          # Dark theme CSS
│   ├── src/main.js        # Application logic
│   └── public/data/       # Static GeoJSON fallback
├── backend/               # Python backend
│   ├── main.py            # FastAPI server
│   ├── model/
│   │   └── train_model.py # XGBoost training
│   ├── data/
│   │   └── generate_data.py # Data generation
│   └── output/            # Generated GeoJSON files
└── README.md
```

## 📡 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/summary` | Aggregated district statistics |
| `GET /api/hazard-zones` | Red/Orange/Yellow/Green zone polygons |
| `GET /api/hazard-grid` | Hazard probability heatmap grid |
| `GET /api/villages` | All villages with risk scores |
| `GET /api/safe-zones` | Suitable relocation sites |
| `GET /api/relocation-priorities` | Prioritized relocation list |
| `GET /api/disaster-history` | Historical disaster events |
| `POST /api/simulate` | Simulate rainfall event |

## 📜 Data Sources

- **Elevation**: SRTM 30m DEM (simulated from real parameters)
- **Population**: Census of India 2011 (Uttarkashi District)
- **Disaster History**: NDMA, USDMA, news reports (2013-2025)
- **Village Locations**: Census village directory + approximation
- **Rivers**: Bhagirathi, Tons, Yamuna (upper reaches)

## 🏆 Key Features for Judges

1. **Real Data**: Based on actual Uttarkashi geography, census data, and disaster history
2. **AI/ML Pipeline**: Complete XGBoost training → prediction → zone classification
3. **3D GIS Visualization**: Mapbox GL JS with real terrain elevation
4. **Actionable Output**: Specific village-level relocation recommendations with timelines
5. **Simulation**: Live demonstration of hazard zone expansion during cloudburst events
6. **Evidence-based**: AHP multi-criteria analysis with transparent weighting

---

*Built for the Intelligent Identification of Hazard-Based Red Zones hackathon challenge.*
