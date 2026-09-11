"""Spatial hazard exposure and disaster-aware route optimization service for NIDARS.

Associates sampled road route coordinates with genuine NIDARS meteorological hazard
stations within a 50 km spatial radius, computes exposure metrics, and calculates
disaster-aware route safety costs.

IMPORTANT:
- Reuses existing trained Flood and Landslide model predictions from GIS processing.
- Uses strict 50 km radius: points outside the radius are marked 'uncovered' without fabricated risk.
- Does NOT claim official disaster routing authorization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from config import Config
from gis.processing import get_spatial_risk_engine, load_station_latest_observations
from gis.risk_zones import calculate_combined_risk
from services.routing_service import haversine_distance_km


def classify_risk_level(score: Optional[float]) -> str:
    """Return qualitative disaster risk tier from numeric probability."""
    if score is None:
        return "UNKNOWN"
    if score < 0.25:
        return "LOW"
    if score < 0.50:
        return "MODERATE"
    if score < 0.75:
        return "HIGH"
    return "CRITICAL"


class RouteRiskAnalyzer:
    """Performs spatial hazard association and safety scoring for road routes."""

    def __init__(self, stations_df: Optional[pd.DataFrame] = None):
        self._engine = get_spatial_risk_engine()
        if stations_df is None:
            self._stations_df = load_station_latest_observations()
        else:
            self._stations_df = stations_df

        # Pre-score stations to have fast in-memory lookups
        self._scored_stations = self._engine.score_station_records(
            self._stations_df,
            flood_weight=getattr(Config, "GIS_FLOOD_WEIGHT", 0.50),
            landslide_weight=getattr(Config, "GIS_LANDSLIDE_WEIGHT", 0.50),
        )

    def analyze_sampled_points(
        self,
        sampled_points: List[Dict[str, Any]],
        station_radius_km: float = 50.0,
        flood_weight: float = 0.50,
        landslide_weight: float = 0.50,
    ) -> List[Dict[str, Any]]:
        """Associate each sampled route point with the nearest NIDARS station within radius."""
        analyzed_points: List[Dict[str, Any]] = []

        for pt in sampled_points:
            pt_lat = float(pt["latitude"])
            pt_lon = float(pt["longitude"])
            cum_dist = float(pt.get("cumulative_distance_km", 0.0))

            nearest_st = None
            min_dist = float("inf")

            for st in self._scored_stations:
                dist = haversine_distance_km(pt_lat, pt_lon, st["latitude"], st["longitude"])
                if dist < min_dist:
                    min_dist = dist
                    nearest_st = st

            is_covered = (min_dist <= station_radius_km) and (nearest_st is not None)

            if is_covered and nearest_st is not None:
                f_prob = float(nearest_st["flood_probability"])
                l_prob = float(nearest_st["landslide_probability"])
                c_risk = calculate_combined_risk(
                    flood_prob=f_prob,
                    landslide_prob=l_prob,
                    flood_weight=flood_weight,
                    landslide_weight=landslide_weight,
                )
                analyzed_points.append({
                    "latitude": pt_lat,
                    "longitude": pt_lon,
                    "cumulative_distance_km": cum_dist,
                    "is_covered": True,
                    "distance_to_station_km": round(min_dist, 2),
                    "nearest_station": nearest_st["station_name"],
                    "station_district": nearest_st["district"],
                    "station_state": nearest_st["state"],
                    "flood_probability": round(f_prob, 4),
                    "landslide_probability": round(l_prob, 4),
                    "combined_risk": round(c_risk, 4),
                })
            else:
                analyzed_points.append({
                    "latitude": pt_lat,
                    "longitude": pt_lon,
                    "cumulative_distance_km": cum_dist,
                    "is_covered": False,
                    "distance_to_station_km": round(min_dist, 2) if nearest_st else None,
                    "nearest_station": nearest_st["station_name"] if nearest_st else None,
                    "station_district": nearest_st["district"] if nearest_st else None,
                    "station_state": nearest_st["state"] if nearest_st else None,
                    "flood_probability": None,
                    "landslide_probability": None,
                    "combined_risk": None,
                })

        return analyzed_points

    def calculate_route_metrics(
        self,
        raw_route: Dict[str, Any],
        analyzed_points: List[Dict[str, Any]],
        penalty_factor: float = 10.0,
    ) -> Dict[str, Any]:
        """Compute aggregate risk metrics, safety score, and disaster-aware route costs."""
        distance_meters = float(raw_route.get("distance", 0.0))
        duration_seconds = float(raw_route.get("duration", 0.0))

        distance_km = round(distance_meters / 1000.0, 2)
        duration_minutes = round(duration_seconds / 60.0, 1)

        total_points = len(analyzed_points)
        covered_points = [p for p in analyzed_points if p["is_covered"]]
        covered_count = len(covered_points)
        uncovered_count = total_points - covered_count

        coverage_pct = round((covered_count / total_points) * 100.0, 1) if total_points > 0 else 0.0

        if covered_count > 0:
            flood_probs = [p["flood_probability"] for p in covered_points if p["flood_probability"] is not None]
            landslide_probs = [p["landslide_probability"] for p in covered_points if p["landslide_probability"] is not None]
            combined_risks = [p["combined_risk"] for p in covered_points if p["combined_risk"] is not None]

            avg_flood = round(sum(flood_probs) / len(flood_probs), 4) if flood_probs else 0.0
            max_flood = round(max(flood_probs), 4) if flood_probs else 0.0

            avg_landslide = round(sum(landslide_probs) / len(landslide_probs), 4) if landslide_probs else 0.0
            max_landslide = round(max(landslide_probs), 4) if landslide_probs else 0.0

            avg_combined = round(sum(combined_risks) / len(combined_risks), 4) if combined_risks else 0.0
            max_combined = round(max(combined_risks), 4) if combined_risks else 0.0

            high_risk_pts = sum(1 for r in combined_risks if r >= 0.50)
            critical_risk_pts = sum(1 for r in combined_risks if r >= 0.75)
        else:
            avg_flood = 0.0
            max_flood = 0.0
            avg_landslide = 0.0
            max_landslide = 0.0
            avg_combined = 0.0
            max_combined = 0.0
            high_risk_pts = 0
            critical_risk_pts = 0

        # Safety score: 0 to 100 scale (100 = safe / 0 risk, 0 = extreme hazard)
        safety_score = round(max(0.0, min(100.0, (1.0 - avg_combined) * 100.0)), 1)

        # Route cost formula: distance_km + (distance_km * penalty_factor * avg_combined_risk)
        risk_penalty = round(distance_km * penalty_factor * avg_combined, 3)
        route_cost = round(distance_km + risk_penalty, 3)

        # Balanced cost formula: balances raw travel distance and disaster safety penalty (50% penalty weight)
        balanced_penalty = round(distance_km * (penalty_factor * 0.5) * avg_combined, 3)
        balanced_cost = round(distance_km + balanced_penalty, 3)

        return {
            "distance_km": distance_km,
            "duration_minutes": duration_minutes,
            "total_points": total_points,
            "covered_points": covered_count,
            "uncovered_points": uncovered_count,
            "risk_coverage_percent": coverage_pct,
            "safety_score": safety_score,
            "risk_level": classify_risk_level(avg_combined),
            "flood_risk_level": classify_risk_level(avg_flood),
            "landslide_risk_level": classify_risk_level(avg_landslide),
            "average_flood_risk": avg_flood,
            "maximum_flood_risk": max_flood,
            "average_landslide_risk": avg_landslide,
            "maximum_landslide_risk": max_landslide,
            "average_combined_risk": avg_combined,
            "maximum_combined_risk": max_combined,
            "high_risk_exposure_points": high_risk_pts,
            "critical_risk_exposure_points": critical_risk_pts,
            "risk_penalty": risk_penalty,
            "route_cost": route_cost,
            "balanced_cost": balanced_cost,
        }

    def evaluate_routes(
        self,
        raw_routes: List[Dict[str, Any]],
        sample_interval_km: float = 1.0,
        station_radius_km: float = 50.0,
        flood_weight: float = 0.50,
        landslide_weight: float = 0.50,
        penalty_factor: float = 10.0,
        min_confidence_coverage: float = 30.0,
        mode: str = "safest",
    ) -> Dict[str, Any]:
        """Evaluate and compare all candidate OSRM routes."""
        from services.routing_service import sample_route_geometry

        evaluated_routes = []

        for idx, route in enumerate(raw_routes):
            geom = route.get("geometry", {})
            coords = geom.get("coordinates", []) if isinstance(geom, dict) else []

            sampled = sample_route_geometry(coords, sample_interval_km=sample_interval_km)
            analyzed_pts = self.analyze_sampled_points(
                sampled_points=sampled,
                station_radius_km=station_radius_km,
                flood_weight=flood_weight,
                landslide_weight=landslide_weight,
            )
            metrics = self.calculate_route_metrics(
                raw_route=route,
                analyzed_points=analyzed_pts,
                penalty_factor=penalty_factor,
            )

            evaluated_routes.append({
                "route_index": idx,
                "summary": route.get("summary", f"Route {idx + 1}"),
                "geometry": geom,
                "metrics": metrics,
                "sampled_points": analyzed_pts,
            })

        if not evaluated_routes:
            raise ValueError("No valid routes to evaluate.")

        # Identify shortest route (minimum distance)
        shortest_idx = min(range(len(evaluated_routes)), key=lambda i: evaluated_routes[i]["metrics"]["distance_km"])

        # Identify safest route (minimum disaster-aware route cost)
        safest_idx = min(range(len(evaluated_routes)), key=lambda i: evaluated_routes[i]["metrics"]["route_cost"])

        # Identify balanced route (minimum balanced cost)
        balanced_idx = min(range(len(evaluated_routes)), key=lambda i: evaluated_routes[i]["metrics"]["balanced_cost"])

        # Determine recommendation according to selected mode
        mode_normalized = (mode or "safest").lower().strip()
        if mode_normalized == "shortest":
            rec_idx = shortest_idx
        elif mode_normalized == "balanced":
            rec_idx = balanced_idx
        else:
            rec_idx = safest_idx
            mode_normalized = "safest"

        rec_coverage = evaluated_routes[rec_idx]["metrics"]["risk_coverage_percent"]
        is_confident = rec_coverage >= min_confidence_coverage

        if not is_confident:
            rec_note = (
                f"Recommendation has limited hazard confidence because route coverage is {rec_coverage}%. "
                f"Remaining {round(100.0 - rec_coverage, 1)}% of the corridor is beyond the {station_radius_km} km station radius."
            )
        elif mode_normalized == "shortest":
            rec_note = (
                f"Recommended based on shortest driving distance ({evaluated_routes[rec_idx]['metrics']['distance_km']} km) "
                f"with {rec_coverage}% hazard coverage."
            )
        elif mode_normalized == "balanced":
            rec_note = (
                f"Recommended based on balanced multi-objective optimization (combining travel distance and hazard risk) "
                f"with {rec_coverage}% station hazard coverage."
            )
        else:
            rec_note = (
                f"Recommended based on disaster-aware cost optimization (Distance + Risk Penalty) "
                f"with {rec_coverage}% station hazard coverage."
            )

        # Label route categories
        for i, r in enumerate(evaluated_routes):
            tags = []
            if i == rec_idx:
                tags.append("RECOMMENDED")
            if i == safest_idx and "SAFEST" not in tags:
                tags.append("SAFEST")
            if i == shortest_idx and "SHORTEST" not in tags:
                tags.append("SHORTEST")
            if i == balanced_idx and "BALANCED" not in tags:
                tags.append("BALANCED")
            if not tags:
                tags.append("ALTERNATIVE")
            r["category_tags"] = tags

        return {
            "routes": evaluated_routes,
            "shortest_route_index": shortest_idx,
            "safest_route_index": safest_idx,
            "balanced_route_index": balanced_idx,
            "recommended_route_index": rec_idx,
            "active_mode": mode_normalized,
            "recommendation_note": rec_note,
            "recommendation_confidence": "HIGH" if is_confident else "LIMITED",
        }


# Singleton instance
_analyzer_instance: Optional[RouteRiskAnalyzer] = None


def get_route_risk_analyzer() -> RouteRiskAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = RouteRiskAnalyzer()
    return _analyzer_instance
