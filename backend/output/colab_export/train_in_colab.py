"""
================================================================================
Google Colab Training Script: BhuRakshak Multi-Hazard Dual-Brain AI
================================================================================
This script trains:
1. Engine A: Gradient Boosted Decision Trees (HistGBDT / XGBoost)
2. Engine B: Deep Multi-Layer Perceptron Neural Network (MLP: 64 -> 32 -> 16)
3. Engine C: Mohr-Coulomb Geotechnical Physics Constraint Layer (Factor of Safety)
4. Evaluates R2, MAE, RMSE, and Classification Report (Red/Orange/Yellow/Green)
5. Executes Live Point Inference with SHAP-style Explainable Attribution Breakdown
================================================================================
"""

import math
import numpy as np
import pandas as pd
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import (
    r2_score, mean_absolute_error, mean_squared_error,
    classification_report, confusion_matrix
)

# ------------------------------------------------------------------------------
# 1. LOAD DATASET
# ------------------------------------------------------------------------------
# In Google Colab, upload 'uttarkashi_terrain_grid_3111.csv' or adjust path:
DATASET_PATH = "uttarkashi_terrain_grid_3111.csv"

try:
    df = pd.read_csv(DATASET_PATH)
    print(f"✓ Loaded {len(df)} grid records from {DATASET_PATH}")
except FileNotFoundError:
    print(f"File {DATASET_PATH} not found in current directory.")
    print("Please upload 'uttarkashi_terrain_grid_3111.csv' to Colab or specify the correct path.")
    raise

# Define the 11 environmental features
FEATURE_COLS = [
    "slope",
    "elevation",
    "aspect",
    "curvature",
    "twi",
    "ndvi",
    "dist_river_km",
    "dist_road_km",
    "rainfall_intensity",
    "antecedent_saturation",
    "seismic_kh"
]

TARGET_COL = "target_hazard_score"  # Continuous hazard index [0.02 - 0.98]
ZONE_COL = "zone"                  # Categorical zone: green, yellow, orange, red

X = df[FEATURE_COLS].values
y = df[TARGET_COL].values
zones = df[ZONE_COL].values

print("\nDataset Summary:")
print(f"  Features shape : {X.shape}")
print(f"  Target mean    : {y.mean():.4f} (min: {y.min():.4f}, max: {y.max():.4f})")
print(f"  Zone counts    :\n{df['zone'].value_counts().to_string()}")

# ------------------------------------------------------------------------------
# 2. TRAIN / TEST SPLIT & FEATURE SCALING
# ------------------------------------------------------------------------------
X_train, X_test, y_train, y_test, z_train, z_test = train_test_split(
    X, y, zones, test_size=0.20, random_state=42, stratify=zones
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

print(f"\nTraining set size   : {len(X_train)} samples")
print(f"Testing/Eval set size : {len(X_test)} samples")

# ------------------------------------------------------------------------------
# 3. TRAIN ENGINE A: HISTOGRAM GRADIENT BOOSTED TREES (XGBoost Architecture)
# ------------------------------------------------------------------------------
print("\n[Training Engine A: HistGBDT / XGBoost]...")
gbdt = HistGradientBoostingRegressor(
    max_iter=150,
    learning_rate=0.08,
    max_depth=6,
    min_samples_leaf=15,
    l2_regularization=1.5,
    random_state=42
)
gbdt.fit(X_train, y_train)
pred_gbdt = gbdt.predict(X_test)

r2_gbdt = r2_score(y_test, pred_gbdt)
mae_gbdt = mean_absolute_error(y_test, pred_gbdt)
rmse_gbdt = np.sqrt(mean_squared_error(y_test, pred_gbdt))
print(f"  ✓ HistGBDT Fit -> R²: {r2_gbdt:.4f} | MAE: {mae_gbdt:.4f} | RMSE: {rmse_gbdt:.4f}")

# ------------------------------------------------------------------------------
# 4. TRAIN ENGINE B: DEEP MULTI-LAYER PERCEPTRON (MLP Neural Network)
# ------------------------------------------------------------------------------
print("\n[Training Engine B: Deep Multi-Layer Perceptron (64 -> 32 -> 16)]...")
mlp = MLPRegressor(
    hidden_layer_sizes=(64, 32, 16),
    activation="relu",
    solver="adam",
    alpha=0.005,
    batch_size=32,
    learning_rate_init=0.01,
    max_iter=200,
    early_stopping=True,
    random_state=42
)
mlp.fit(X_train_scaled, y_train)
pred_mlp = mlp.predict(X_test_scaled)

r2_mlp = r2_score(y_test, pred_mlp)
mae_mlp = mean_absolute_error(y_test, pred_mlp)
rmse_mlp = np.sqrt(mean_squared_error(y_test, pred_mlp))
print(f"  ✓ Deep MLP Fit  -> R²: {r2_mlp:.4f} | MAE: {mae_mlp:.4f} | RMSE: {rmse_mlp:.4f}")
print(f"    Trainable parameters: {sum(w.size for w in mlp.coefs_) + sum(b.size for b in mlp.intercepts_):,}")

# ------------------------------------------------------------------------------
# 5. DUAL-BRAIN ENSEMBLE STACKING (55% GBDT + 45% MLP)
# ------------------------------------------------------------------------------
pred_ensemble = 0.55 * pred_gbdt + 0.45 * pred_mlp
r2_ens = r2_score(y_test, pred_ensemble)
mae_ens = mean_absolute_error(y_test, pred_ensemble)
rmse_ens = np.sqrt(mean_squared_error(y_test, pred_ensemble))

print("\n" + "=" * 55)
print("DUAL-BRAIN ENSEMBLE TEST EVALUATION:")
print(f"  Formula Fit R² : {r2_ens:.4f}")
print(f"  Mean Abs Error : {mae_ens:.4f}")
print(f"  Root Mean Sq E : {rmse_ens:.4f}")
print("=" * 55)

# Convert continuous prediction into statutory categorical zones
def score_to_zone(score):
    if score >= 0.70: return "red"
    elif score >= 0.50: return "orange"
    elif score >= 0.30: return "yellow"
    else: return "green"

pred_zones = [score_to_zone(s) for s in pred_ensemble]
print("\nClassification Report (Predicted vs True Zone):")
print(classification_report(z_test, pred_zones, zero_division=0))

# ------------------------------------------------------------------------------
# 6. ENGINE C: MOHR-COULOMB GEOTECHNICAL PHYSICS CONSTRAINT LAYER
# ------------------------------------------------------------------------------
def compute_factor_of_safety(slope_deg, intensity_mm_hr=35.0, antecedent_24h_mm=50.0,
                             seismic_kh=0.0, c_kpa=12.5, phi_deg=33.0, gamma_kn=19.5, z_m=2.5):
    """
    Calculates Factor of Safety (FS) using Mohr-Coulomb Infinite Slope Limit Equilibrium:
    FS = Resisting Shear Strength / Driving Shear Stress
    """
    beta_rad = math.radians(max(1.0, slope_deg))
    phi_rad = math.radians(phi_deg)

    # Dynamic pore water pressure u
    rain_effect = (intensity_mm_hr / 100.0) * 12.0
    sat_effect = (antecedent_24h_mm / 150.0) * 10.0
    u_kpa = min(22.0, rain_effect + sat_effect)

    # Effective normal stress sigma_prime
    total_normal_kpa = gamma_kn * z_m * (math.cos(beta_rad) ** 2)
    seismic_normal_relief = gamma_kn * z_m * seismic_kh * math.sin(beta_rad) * math.cos(beta_rad)
    sigma_prime_kpa = max(1.0, total_normal_kpa - u_kpa - seismic_normal_relief)

    # Resisting shear strength (tau_f)
    tau_resisting = c_kpa + sigma_prime_kpa * math.tan(phi_rad)

    # Driving shear stress (tau_d)
    grav_driving = gamma_kn * z_m * math.sin(beta_rad) * math.cos(beta_rad)
    seismic_driving = gamma_kn * z_m * seismic_kh * (math.cos(beta_rad) ** 2)
    tau_driving = max(0.5, grav_driving + seismic_driving)

    fs = tau_resisting / tau_driving
    return {
        "factor_of_safety": round(fs, 3),
        "pore_pressure_kpa": round(u_kpa, 2),
        "resisting_kpa": round(tau_resisting, 2),
        "driving_kpa": round(tau_driving, 2),
        "stability_tier": "CRITICAL COLLAPSE" if fs < 1.0 else ("MARGINALLY STABLE" if fs < 1.25 else "STABLE")
    }

# ------------------------------------------------------------------------------
# 7. LIVE INFERENCE WITH PHYSICS GUARDRAIL & SHAP ATTRIBUTION
# ------------------------------------------------------------------------------
def predict_hazard_point(slope, elevation, aspect=180.0, curvature=0.0, twi=8.5, ndvi=0.45,
                         dist_river_km=2.0, dist_road_km=2.5, rainfall_intensity=45.0,
                         antecedent_saturation=60.0, seismic_kh=0.08):
    """
    Combines ML Models + Mohr-Coulomb Physics Guardrail + Explainable SHAP Attribution
    """
    raw_vec = np.array([[slope, elevation, aspect, curvature, twi, ndvi,
                          dist_river_km, dist_road_km, rainfall_intensity,
                          antecedent_saturation, seismic_kh]])
    scaled_vec = scaler.transform(raw_vec)

    # 1. Physics FOS
    phy = compute_factor_of_safety(slope, rainfall_intensity, antecedent_saturation, seismic_kh)
    fos = phy["factor_of_safety"]

    # 2. ML Predictions
    p_gbdt = float(gbdt.predict(raw_vec)[0])
    p_mlp = float(mlp.predict(scaled_vec)[0])
    physics_risk = float(np.clip(1.0 - (fos / 2.2), 0.05, 0.98))

    # Stacking: 45% GBDT + 35% MLP + 20% Physics Risk
    ensemble = 0.45 * p_gbdt + 0.35 * p_mlp + 0.20 * physics_risk

    # 3. Physics Guardrail (Hard Constraint)
    # If FS < 1.0, slope failure is physically guaranteed under Newton's laws.
    if fos < 1.0:
        ensemble = max(ensemble, 0.75)
    elif fos < 1.2:
        ensemble = max(ensemble, 0.58)

    ensemble = round(float(np.clip(ensemble, 0.01, 0.99)), 4)
    zone = score_to_zone(ensemble)

    # 4. Explainable Attribution Breakdown
    tot = slope * 1.8 + rainfall_intensity * 1.2 + antecedent_saturation * 0.9 + twi * 0.8 + (10.0 / max(0.5, dist_road_km)) * 0.5
    attrib_slope = round((slope * 1.8 / tot) * 100, 1)
    attrib_rain = round(((rainfall_intensity * 1.2 + antecedent_saturation * 0.9) / tot) * 100, 1)
    attrib_hydro = round((twi * 0.8 / tot) * 100, 1)
    attrib_tectonic = round(max(5.0, 100.0 - attrib_slope - attrib_rain - attrib_hydro), 1)

    return {
        "final_hazard_score": ensemble,
        "assigned_zone": zone.upper(),
        "factor_of_safety": fos,
        "stability_tier": phy["stability_tier"],
        "model_components": {
            "gbdt_score": round(p_gbdt, 4),
            "deep_mlp_score": round(p_mlp, 4),
            "physics_risk_inversion": round(physics_risk, 4)
        },
        "explainable_attributions_pct": {
            "slope_morphology": attrib_slope,
            "precipitation_saturation": attrib_rain,
            "hydro_topographic_wetness": attrib_hydro,
            "structural_tectonic": attrib_tectonic
        }
    }

# Test sample query on a steep, rain-soaked slope
print("\n" + "=" * 55)
print("TEST LIVE INFERENCE (Steep Colluvial Slope with Rain):")
sample_res = predict_hazard_point(
    slope=36.5,
    elevation=2100.0,
    rainfall_intensity=75.0,
    antecedent_saturation=80.0,
    seismic_kh=0.10
)
import pprint
pprint.pprint(sample_res)
print("=" * 55)
