"""
Comprehensive Test Suite for HazardShield 2.0 (Python Standard Library Unittest)
Validates:
  1. Trigger Engine (Intensity x Antecedent Saturation proxy).
  2. 3D Flow Simulation (Steepest-Descent D8 trajectory & deposition fan).
  3. Ground-Truth Historical Disaster Hit Rate (Genuine spatial Euclidean distance lookup).
  4. Carrying Capacity Ledger & Evacuation Directives.
  5. In-process FastAPI TestClient integration for REST API endpoints.
"""

import unittest
import json
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.model.trigger_engine import (
    intensity_factor, antecedent_factor, rainfall_multiplier,
    compute_dynamic_alerts, match_alerts_to_safe_zones, run_trigger_pipeline,
    classify_zone
)
from backend.model.flow_simulation import (
    compute_debris_flow_path, compute_flood_inundation, evaluate_historical_disaster_hit_rate,
    compute_dijkstra_evacuation_routes
)
from backend.model.geotech_physics import compute_factor_of_safety

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
client = TestClient(app)


class TestTriggerEngine(unittest.TestCase):
    def test_multipliers(self):
        """Verify IMD rainfall bands and soil saturation multipliers."""
        self.assertEqual(intensity_factor(2.0), 1.00)
        self.assertEqual(intensity_factor(5.0), 1.10)
        self.assertEqual(intensity_factor(25.0), 1.30)
        self.assertEqual(intensity_factor(50.0), 1.65)
        self.assertEqual(intensity_factor(150.0), 2.65)

        self.assertEqual(antecedent_factor(10.0), 1.00)
        self.assertEqual(antecedent_factor(30.0), 1.15)
        self.assertEqual(antecedent_factor(80.0), 1.35)
        self.assertEqual(antecedent_factor(120.0), 1.60)

        mult = rainfall_multiplier(70.0, 90.0)
        self.assertAlmostEqual(mult, 2.10 * 1.35, places=2)

    def test_zone_classification_consistency(self):
        """Verify unified zone thresholds: Red >= 0.70, Orange 0.50-0.70, Yellow 0.30-0.50."""
        self.assertEqual(classify_zone(0.85), "red")
        self.assertEqual(classify_zone(0.70), "red")
        self.assertEqual(classify_zone(0.68), "orange")
        self.assertEqual(classify_zone(0.50), "orange")
        self.assertEqual(classify_zone(0.42), "yellow")
        self.assertEqual(classify_zone(0.30), "yellow")
        self.assertEqual(classify_zone(0.15), "green")

    def test_run_trigger_pipeline(self):
        """Verify operational nowcasting pipeline with capacity ledger."""
        res = run_trigger_pipeline(OUTPUT_DIR, intensity_mm_hr=75.0, antecedent_24h_mm=60.0)
        self.assertIn("rainfall_input", res)
        self.assertIn("alert_counts", res)
        self.assertIn("dispatched_evacuations", res)
        self.assertGreaterEqual(res["alert_counts"]["EVACUATE_NOW"], 0)


class TestFlowSimulation(unittest.TestCase):
    def test_debris_and_flood(self):
        """Verify D8 steepest descent trajectory, fan geometry, and flood surge."""
        with open(OUTPUT_DIR / "terrain_features.json") as f:
            pts = json.load(f)
        with open(OUTPUT_DIR / "rivers.geojson") as f:
            rivers = json.load(f)
        debris = compute_debris_flow_path(pts, 31.023, 78.784, rivers_data=rivers, max_steps=12)
        
        self.assertEqual(debris["type"], "debris_flow")
        self.assertIn("path_geojson", debris)
        self.assertIn("deposition_fan_geojson", debris)
        self.assertGreater(len(debris["path_geojson"]["geometry"]["coordinates"]), 1)
        self.assertGreater(debris["path_geojson"]["properties"]["peak_velocity_mps"], 0)
        self.assertGreater(debris["deposition_fan_geojson"]["properties"]["fan_area_ha"], 0)

        flood = compute_flood_inundation(rivers, intensity_mm_hr=80.0, antecedent_24h_mm=70.0)
        self.assertGreater(len(flood["features"]), 0)

    def test_dijkstra_evacuation_routing(self):
        """Verify Dijkstra least-cost valley evacuation paths with precomputed graph."""
        with open(OUTPUT_DIR / "villages.geojson") as f:
            villages = json.load(f)["features"][:5]
        with open(OUTPUT_DIR / "safe_zones.geojson") as f:
            safe_zones = [
                {"lat": feat["geometry"]["coordinates"][0][0][1], "lng": feat["geometry"]["coordinates"][0][0][0]}
                for feat in json.load(f)["features"]
            ]
        with open(OUTPUT_DIR / "terrain_features.json") as f:
            terrain_features = json.load(f)

        routes = compute_dijkstra_evacuation_routes(villages, safe_zones, terrain_features)
        self.assertGreater(len(routes), 0)
        first_route = routes[0]
        self.assertIn("route_type", first_route["properties"])
        self.assertGreater(len(first_route["geometry"]["coordinates"]), 1)

    def test_mohr_coulomb_factor_of_safety(self):
        """Verify Mohr-Coulomb Factor of Safety physics engine and standard stability tiers."""
        # Dry slope: FS >= 1.5 is standard STABLE
        dry = compute_factor_of_safety(35.0, intensity_mm_hr=0.0, antecedent_24h_mm=0.0)
        self.assertGreaterEqual(dry["factor_of_safety"], 1.5)
        self.assertEqual(dry["stability_tier"], "STABLE")

        # Saturated deluge slope: drops below dry FS
        deluge = compute_factor_of_safety(35.0, intensity_mm_hr=120.0, antecedent_24h_mm=160.0)
        self.assertLess(deluge["factor_of_safety"], dry["factor_of_safety"])
        self.assertGreater(deluge["pore_pressure_kpa"], 0)

    def test_historical_disaster_hit_rate(self):
        """Verify genuine spatial nearest-neighbor intersection across recorded historical disaster coordinates."""
        benchmark = evaluate_historical_disaster_hit_rate(OUTPUT_DIR)
        self.assertGreaterEqual(benchmark["total_historical_events_tested"], 12)
        self.assertGreaterEqual(benchmark["total_hits"], 11)
        self.assertGreaterEqual(benchmark["ground_truth_accuracy_pct"], 90.0)
        
        # Verify genuine spatial coordinate tracking in audit
        first = benchmark["events_audit"][0]
        self.assertIn("event_coordinates", first)
        self.assertIn("nearest_cell_distance_km", first)
        self.assertIn("validation_outcome", first)
        self.assertLessEqual(first["nearest_cell_distance_km"], benchmark["spatial_search_tolerance_km"])


class TestApiEndpointsWithTestClient(unittest.TestCase):
    def test_summary_api(self):
        res = client.get("/api/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("zone_statistics", data)

    def test_simulate_api(self):
        res = client.post("/api/simulate?intensity_mm_hr=60&antecedent_24h_mm=50")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("alert_counts", data)
        self.assertIn("dispatched_evacuations", data)

    def test_simulate_flow_api(self):
        res = client.get("/api/simulate/flow?lat=31.023&lng=78.784&intensity_mm_hr=65&antecedent_24h_mm=50")
        self.assertEqual(res.status_code, 200)
        flow = res.json()
        self.assertIn("debris_flow", flow)
        self.assertIn("flood_inundation", flow)

    def test_model_validation_api(self):
        res = client.get("/api/model-validation")
        self.assertEqual(res.status_code, 200)
        val = res.json()
        self.assertGreaterEqual(val["ground_truth_accuracy_pct"], 90.0)
        self.assertGreaterEqual(val["total_hits"], 11)

    def test_live_weather_api(self):
        res = client.get("/api/live-weather?lat=30.73&lng=78.45")
        self.assertEqual(res.status_code, 200)
        weather = res.json()
        self.assertIn("intensity_mm_hr", weather)
        self.assertIn("antecedent_24h_mm", weather)

    def test_dm_action_plan_api(self):
        res = client.get("/api/dm-action-plan")
        self.assertEqual(res.status_code, 200)
        plan = res.json()
        self.assertIn("priorities_matrix", plan)
        self.assertIn("executive_summary", plan)
        self.assertIn("estimated_sdrf_rehab_package_cr", plan["executive_summary"])
        self.assertIn("tier_population_breakdown", plan["executive_summary"])
        self.assertGreater(plan["executive_summary"]["estimated_sdrf_rehab_package_cr"], 0)

    def test_carrying_capacity_ledger_api(self):
        res = client.get("/api/carrying-capacity/ledger?intensity_mm_hr=45&antecedent_24h_mm=30")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("summary", data)
        self.assertIn("sites", data)
        self.assertGreater(len(data["sites"]), 0)
        first_site = data["sites"][0]
        self.assertIn("total_capacity", first_site)
        self.assertIn("remaining_headroom", first_site)
        self.assertIn("stress_tier", first_site)

    def test_dynamic_hazard_zones_api(self):
        res = client.get("/api/hazard-zones/dynamic?intensity_mm_hr=75&antecedent_24h_mm=60")
        self.assertEqual(res.status_code, 200)
        zones = res.json()
        self.assertEqual(zones["type"], "FeatureCollection")
        self.assertGreater(len(zones["features"]), 0)
        first_feat = zones["features"][0]
        self.assertEqual(first_feat["geometry"]["type"], "Polygon")
        self.assertIn("zone", first_feat["properties"])
        self.assertIn("hazard_probability", first_feat["properties"])

    def test_disaster_simulations_api(self):
        res = client.get("/api/disaster-simulations")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(len(data["scenarios"]), 3)
        # Verify dynamic calculation fields exist
        s0 = data["scenarios"][0]["hazardshield_proactive"]
        self.assertIn("alert_lead_time_hours", s0)
        self.assertIn("red_zone_expansion_cells", s0)
        self.assertIn("pre_disaster_evacuated_pop", s0)

    def test_tectonic_faults_api(self):
        res = client.get("/api/tectonic-faults")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("type"), "FeatureCollection")
        self.assertGreater(len(data.get("features", [])), 0)
        # Verify Main Central Thrust exists
        fault_names = [f["properties"].get("fault_name", "") for f in data["features"]]
        self.assertTrue(any("Main Central Thrust" in name for name in fault_names))

    def test_evacuation_routes_api(self):
        payload = {
            "villages": [
                {
                    "village_id": 101,
                    "village_name": "Bhatwari Test",
                    "lat": 30.82,
                    "lng": 78.60,
                    "population": 350
                }
            ]
        }
        res = client.post("/api/simulate/evacuation-routes", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("features", data)
        self.assertGreaterEqual(len(data["features"]), 1)
        self.assertEqual(data["features"][0]["geometry"]["type"], "LineString")


if __name__ == "__main__":
    unittest.main()


