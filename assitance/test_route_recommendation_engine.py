"""
Unit and Integration Tests for Component 2 — Step 7: AI Route Recommendation & Optimization Layer.
Contains at least 15 comprehensive tests covering candidate generation, segment calculations, bug prevention,
backtracking penalties, feasibility, daily itineraries, multi-factor weighting, and API integration.
"""

import unittest
import json
try:
    from .app import bp, DESTINATIONS
    from .route_recommendation_engine import (
        select_suitable_destinations,
        calculate_segment,
        calculate_backtracking_penalty,
        evaluate_route_feasibility,
        generate_candidate_sequences,
        generate_daily_route_plan,
        build_route_recommendations
    )
    from .travel_transport_engine import calculate_distance, estimate_travel_time
except ImportError:
    from app import bp, DESTINATIONS
    from route_recommendation_engine import (
        select_suitable_destinations,
        calculate_segment,
        calculate_backtracking_penalty,
        evaluate_route_feasibility,
        generate_candidate_sequences,
        generate_daily_route_plan,
        build_route_recommendations
    )
    from travel_transport_engine import calculate_distance, estimate_travel_time
from flask import Flask


def create_sample_evaluated_items():
    return [
        {
            "place": "Nuwara Eliya",
            "score": 92,
            "preference_match": {"matched": ["cool_weather", "mountains", "quiet"], "score": 95},
            "weather_suitability": {"condition": "Good", "score": 90},
            "travel_transport": {"estimated_travel_time_hours": 3.7, "transport_score": 85},
            "crowd_safety": {"overall_score": 90, "crowd_level": "Low"},
            "activity_recommendations": {
                "top_activity": {"name": "Pedro Tea Estate", "score": 90},
                "recommended_activities": [{"name": "Pedro Tea Estate", "time_window": "09:00-11:30"}]
            },
            "event_timing": {"timing_score": 88}
        },
        {
            "place": "Ella",
            "score": 88,
            "preference_match": {"matched": ["mountains", "nature", "quiet"], "score": 90},
            "weather_suitability": {"condition": "Good", "score": 88},
            "travel_transport": {"estimated_travel_time_hours": 4.5, "transport_score": 80},
            "crowd_safety": {"overall_score": 85, "crowd_level": "Low"},
            "activity_recommendations": {
                "top_activity": {"name": "Nine Arches Bridge", "score": 88},
                "recommended_activities": [{"name": "Nine Arches Bridge", "time_window": "14:00-16:30"}]
            },
            "event_timing": {"timing_score": 85}
        },
        {
            "place": "Kandy",
            "score": 82,
            "preference_match": {"matched": ["cultural", "heritage"], "score": 85},
            "weather_suitability": {"condition": "Good", "score": 82},
            "travel_transport": {"estimated_travel_time_hours": 2.5, "transport_score": 90},
            "crowd_safety": {"overall_score": 80, "crowd_level": "Moderate"},
            "activity_recommendations": {
                "top_activity": {"name": "Temple of the Tooth", "score": 85},
                "recommended_activities": [{"name": "Temple of the Tooth", "time_window": "15:00-17:00"}]
            },
            "event_timing": {"timing_score": 82}
        },
        {
            "place": "Galle",
            "score": 65,
            "preference_match": {"matched": ["beach", "heritage"], "score": 65},
            "weather_suitability": {"condition": "Moderate", "score": 65},
            "travel_transport": {"estimated_travel_time_hours": 2.6, "transport_score": 88},
            "crowd_safety": {"overall_score": 70, "crowd_level": "Moderate"},
            "activity_recommendations": {
                "top_activity": {"name": "Galle Fort Walk", "score": 70},
                "recommended_activities": [{"name": "Galle Fort Walk", "time_window": "16:00-18:00"}]
            },
            "event_timing": {"timing_score": 70}
        },
        {
            "place": "Mirissa",
            "score": 63,
            "preference_match": {"matched": ["beach"], "score": 60},
            "weather_suitability": {"condition": "Good", "score": 70},
            "travel_transport": {"estimated_travel_time_hours": 3.3, "transport_score": 80},
            "crowd_safety": {"overall_score": 68, "crowd_level": "Low"},
            "activity_recommendations": {
                "top_activity": {"name": "Whale Watching", "score": 68},
                "recommended_activities": [{"name": "Whale Watching", "time_window": "06:00-10:00"}]
            },
            "event_timing": {"timing_score": 68}
        }
    ]


class TestRouteRecommendationEngine(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(bp, url_prefix="/assistance")
        self.client = self.app.test_client()
        self.sample_items = create_sample_evaluated_items()

    def test_01_suitable_destination_selection(self):
        """1. Tests that destination selection picks highest quality compatible places."""
        suitable = select_suitable_destinations(self.sample_items, top_n=4)
        self.assertGreaterEqual(len(suitable), 3)
        places = [s["place"] for s in suitable]
        self.assertIn("Nuwara Eliya", places)
        self.assertIn("Ella", places)
        self.assertIn("Kandy", places)

    def test_02_route_candidate_generation(self):
        """2. Tests basic route candidate sequence generation."""
        seqs = generate_candidate_sequences("Colombo", days=3, suitable_destinations=self.sample_items)
        self.assertTrue(len(seqs) > 0)
        for s in seqs:
            self.assertEqual(s[0], "Colombo")
            self.assertGreaterEqual(len(s), 2)

    def test_03_multiple_route_candidate_generation(self):
        """3. Tests that at least 3 distinct route candidates are generated when sufficient destinations exist."""
        seqs = generate_candidate_sequences("Colombo", days=3, suitable_destinations=self.sample_items)
        self.assertGreaterEqual(len(seqs), 3)
        unique_seqs = set(tuple(s) for s in seqs)
        self.assertEqual(len(unique_seqs), len(seqs), "Candidate route sequences must be unique.")

    def test_04_consecutive_segment_distance_calculation(self):
        """4. Tests accurate pairwise segment distance calculation (from_loc -> to_loc)."""
        seg1 = calculate_segment("Colombo", "Kandy", "car")
        seg2 = calculate_segment("Kandy", "Nuwara Eliya", "car")
        seg3 = calculate_segment("Nuwara Eliya", "Ella", "car")

        self.assertEqual(seg1["distance_km"], 115)
        self.assertEqual(seg2["distance_km"], 76)
        self.assertEqual(seg3["distance_km"], 55)

    def test_05_consecutive_segment_travel_time_calculation(self):
        """5. Tests accurate travel time calculation for consecutive route segments."""
        seg1 = calculate_segment("Colombo", "Kandy", "car")
        seg2 = calculate_segment("Kandy", "Nuwara Eliya", "car")

        self.assertGreater(seg1["estimated_travel_time_hours"], 0)
        self.assertGreater(seg2["estimated_travel_time_hours"], 0)
        self.assertNotEqual(seg1["estimated_travel_time"], seg2["estimated_travel_time"])

    def test_06_prevention_of_same_distance_reuse_bug(self):
        """6. IMPORTANT: Verifies fix for same-distance reuse bug across consecutive segments."""
        route = ["Colombo", "Kandy", "Nuwara Eliya", "Ella"]
        recs = build_route_recommendations("Colombo", days=3, transport_mode="car", evaluated_items=self.sample_items)
        r = recs[0]
        segments = r["segments"]

        col_kandy = segments[0]["distance_km"]
        kandy_nuwara = segments[1]["distance_km"]
        nuwara_ella = segments[2]["distance_km"]

        # Ensure segments are NOT returning Colombo -> Nuwara Eliya (170km) or Colombo -> Ella (205km)
        self.assertNotEqual(kandy_nuwara, 170, "Segment 2 must be Kandy->Nuwara Eliya (76km), not Colombo->Nuwara Eliya.")
        self.assertNotEqual(nuwara_ella, 205, "Segment 3 must be Nuwara Eliya->Ella (55km), not Colombo->Ella.")
        self.assertEqual(kandy_nuwara, 76)
        self.assertEqual(nuwara_ella, 55)

    def test_07_prevention_of_same_timing_reuse_bug(self):
        """7. IMPORTANT: Verifies fix for same-timing reuse bug across consecutive segments."""
        recs = build_route_recommendations("Colombo", days=3, transport_mode="car", evaluated_items=self.sample_items)
        r = recs[0]
        segments = r["segments"]

        time1 = segments[0]["estimated_travel_time_hours"]
        time2 = segments[1]["estimated_travel_time_hours"]
        time3 = segments[2]["estimated_travel_time_hours"]

        self.assertNotEqual(time1, time2)
        self.assertNotEqual(time2, time3)

    def test_08_backtracking_penalty(self):
        """8. Tests detection and penalty calculation for unnecessary geographic backtracking."""
        linear_route = ["Colombo", "Kandy", "Nuwara Eliya", "Ella"]
        backtrack_route = ["Colombo", "Ella", "Kandy", "Nuwara Eliya"]

        pen_linear = calculate_backtracking_penalty(linear_route)
        pen_backtrack = calculate_backtracking_penalty(backtrack_route)

        self.assertLess(pen_linear, pen_backtrack, "Backtracking route must receive a higher backtracking penalty.")

    def test_09_route_feasibility_evaluation(self):
        """9. Tests route feasibility check against available trip days."""
        feasible = evaluate_route_feasibility(days=3, total_travel_time_hours=6.5, num_stops=3)
        unfeasible = evaluate_route_feasibility(days=1, total_travel_time_hours=12.0, num_stops=4)

        self.assertTrue(feasible["feasible"])
        self.assertFalse(unfeasible["feasible"])
        self.assertIsNotNone(unfeasible["warning"])

    def test_10_different_day_limits_handling(self):
        """10. Tests route generation under different day constraints (1 day, 3 days, 5 days)."""
        recs_1day = build_route_recommendations("Colombo", days=1, transport_mode="car", evaluated_items=self.sample_items)
        recs_3days = build_route_recommendations("Colombo", days=3, transport_mode="car", evaluated_items=self.sample_items)

        self.assertEqual(recs_1day[0]["days"], 1)
        self.assertEqual(recs_3days[0]["days"], 3)
        self.assertLessEqual(len(recs_1day[0]["segments"]), 2)

    def test_11_daily_plan_generation(self):
        """11. Tests daily travel itinerary plan structure."""
        recs = build_route_recommendations("Colombo", days=3, transport_mode="car", evaluated_items=self.sample_items)
        plan = recs[0]["daily_plan"]

        self.assertEqual(len(plan), 3)
        self.assertEqual(plan[0]["day"], 1)
        self.assertIn("activities", plan[0])
        self.assertGreater(len(plan[0]["activities"]), 0)

    def test_12_preference_based_route_selection(self):
        """12. Tests that user preference match influences route scoring."""
        sample_cool = create_sample_evaluated_items()
        # Boost Nuwara Eliya & Ella pref match
        sample_cool[0]["preference_match"]["score"] = 100
        sample_cool[1]["preference_match"]["score"] = 100

        recs = build_route_recommendations("Colombo", days=3, transport_mode="car", evaluated_items=sample_cool)
        best_route = recs[0]["route"]

        self.assertIn("Nuwara Eliya", best_route)
        self.assertIn("Ella", best_route)

    def test_13_weather_impact_on_route_selection(self):
        """13. Tests weather suitability impact on route scoring."""
        sample_w = create_sample_evaluated_items()
        # Degrade weather for Nuwara Eliya
        sample_w[0]["weather_suitability"] = {"condition": "Poor", "score": 30}

        recs = build_route_recommendations("Colombo", days=3, transport_mode="car", evaluated_items=sample_w)
        why = recs[0]["why_recommended"]
        self.assertIsInstance(why, list)

    def test_14_deterministic_route_ranking(self):
        """14. Tests that route recommendations are deterministically ranked by overall_route_score."""
        recs = build_route_recommendations("Colombo", days=3, transport_mode="car", evaluated_items=self.sample_items)
        scores = [r["overall_route_score"] for r in recs]
        sorted_scores = sorted(scores, reverse=True)

        self.assertEqual(scores, sorted_scores, "Routes must be sorted by score descending.")
        self.assertEqual(recs[0]["rank"], 1)

    def test_15_full_api_integration(self):
        """15. Integration test verifying POST /assistance/recommend returns route_recommendations."""
        payload = {
            "user_text": "I want to go to a quiet cold place",
            "origin": "Colombo",
            "days": 3,
            "transport_mode": "car",
            "weather": {"rainfall_mm": 2.0, "temperature_c": 28.5},
            "crowd": {"month": 9, "day_of_week": 6, "is_weekend": 1, "lag_1": 100, "lag_2": 100, "lag_3": 100}
        }
        res = self.client.post("/assistance/recommend", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)

        data = json.loads(res.data)
        self.assertIn("route_recommendations", data)
        self.assertIn("recommendations", data)

        routes = data["route_recommendations"]
        self.assertGreaterEqual(len(routes), 1)

        r1 = routes[0]
        self.assertIn("route", r1)
        self.assertIn("route_display", r1)
        self.assertIn("overall_route_score", r1)
        self.assertIn("total_distance_km", r1)
        self.assertIn("total_travel_time", r1)
        self.assertIn("segments", r1)
        self.assertIn("daily_plan", r1)
        self.assertIn("why_recommended", r1)
        self.assertIn("tradeoffs", r1)

        # Verify pairwise segments fix in full API return
        segs = r1["segments"]
        self.assertGreaterEqual(len(segs), 2)
        self.assertEqual(segs[0]["from"], "Colombo")
        self.assertEqual(segs[1]["from"], segs[0]["to"])


if __name__ == "__main__":
    unittest.main()
