"""
Route Recommendation, Optimization & Explainability Engine for Component 2 — Step 7.
Generates, evaluates, optimizes, and ranks complete multi-destination travel routes in Sri Lanka.
Reuses destination-level intelligence evaluated in Steps 1-6.
"""

import math
try:
    from .travel_transport_engine import calculate_distance, estimate_travel_time, DESTINATION_COORDINATES
    from .final_recommendation_engine import classify_decision_level
except ImportError:
    from travel_transport_engine import calculate_distance, estimate_travel_time, DESTINATION_COORDINATES
    from final_recommendation_engine import classify_decision_level


def select_suitable_destinations(evaluated_items, top_n=6):
    """
    Selects top suitable destinations evaluated by Steps 1-6.
    Filters out low-scoring places unless insufficient alternatives exist.
    """
    if not evaluated_items:
        return []

    # Sort evaluated items by overall score descending
    sorted_items = sorted(
        evaluated_items,
        key=lambda item: item.get("score", 0),
        reverse=True
    )

    # Select top N candidates with score >= 50 if available
    suitable = [item for item in sorted_items if item.get("score", 0) >= 50]
    if len(suitable) < 3:
        suitable = sorted_items[:top_n]
    else:
        suitable = suitable[:top_n]

    return suitable


def calculate_segment(from_loc, to_loc, transport_mode="car"):
    """
    Calculates pairwise distance, travel time, and warnings for a single segment (from_loc -> to_loc).
    Fixes the same-distance / same-timing bug by calculating segment independently.
    """
    distance_km, is_estimated = calculate_distance(from_loc, to_loc)
    hours_float, time_str = estimate_travel_time(distance_km, transport_mode)

    warnings = []
    if hours_float >= 4.5:
        warnings.append(f"Long travel segment between {from_loc} and {to_loc} ({time_str}).")
    elif distance_km >= 200:
        warnings.append(f"Significant distance ({distance_km} km) between {from_loc} and {to_loc}.")

    return {
        "from": from_loc,
        "to": to_loc,
        "distance_km": distance_km,
        "estimated_travel_time_hours": hours_float,
        "estimated_travel_time": time_str,
        "is_estimated_distance": is_estimated,
        "warnings": warnings
    }


def calculate_backtracking_penalty(route_nodes):
    """
    Detects unnecessary geographic backtracking along the route sequence.
    Returns penalty score between 0 (no backtracking) and 35 (heavy backtracking).
    """
    if len(route_nodes) <= 2:
        return 0.0

    total_dist = 0
    coords = []
    for node in route_nodes:
        c = DESTINATION_COORDINATES.get(node, (7.0, 80.5))
        coords.append(c)

    # Calculate segment distances
    for i in range(len(route_nodes) - 1):
        d, _ = calculate_distance(route_nodes[i], route_nodes[i + 1])
        total_dist += d

    # Direct distance from origin (first node) to final destination (last node)
    direct_dist, _ = calculate_distance(route_nodes[0], route_nodes[-1])

    # Backtracking ratio comparison
    if direct_dist > 0 and total_dist > 1.5 * direct_dist:
        ratio = total_dist / float(direct_dist)
        penalty = min(35.0, (ratio - 1.3) * 20.0)
        return round(penalty, 2)

    return 0.0


def evaluate_route_feasibility(days, total_travel_time_hours, num_stops):
    """
    Evaluates whether a candidate route is realistically feasible within the requested trip duration.
    """
    max_practical_hours = days * 4.5

    if total_travel_time_hours > max_practical_hours:
        return {
            "feasible": False,
            "feasibility_score": max(20.0, 100.0 - (total_travel_time_hours - max_practical_hours) * 15.0),
            "warning": "This route requires more travel time than is practical for the selected trip duration."
        }
    
    if num_stops > days + 1:
        return {
            "feasible": False,
            "feasibility_score": 50.0,
            "warning": f"Attempting {num_stops} destinations in {days} day(s) may result in rushed travel."
        }

    # Feasible route score calculation
    utilization_ratio = total_travel_time_hours / (days * 3.5) if days > 0 else 1.0
    if utilization_ratio <= 1.0:
        score = 100.0
    else:
        score = max(60.0, 100.0 - (utilization_ratio - 1.0) * 40.0)

    return {
        "feasible": True,
        "feasibility_score": round(score, 1),
        "warning": None
    }


def generate_candidate_sequences(origin, days, suitable_destinations):
    """
    Generates at least 3 distinct route candidate node lists starting from origin.
    Does NOT use random selection. Uses deterministic ordering algorithms.
    """
    dest_names = [item["place"] for item in suitable_destinations if item["place"] != origin]

    if not dest_names:
        dest_names = ["Kandy", "Nuwara Eliya", "Ella"]

    # Limit maximum route stops according to trip duration (days)
    max_dest_count = min(len(dest_names), max(1, min(days + 1, 4)))

    candidates = []

    # Strategy 1: Geographically Nearest Neighbor Sequence (Minimizes travel time)
    curr = origin
    unvisited = list(dest_names)
    seq1 = [origin]
    while unvisited and len(seq1) - 1 < max_dest_count:
        nearest = min(unvisited, key=lambda d: calculate_distance(curr, d)[0])
        seq1.append(nearest)
        unvisited.remove(nearest)
        curr = nearest
    candidates.append(seq1)

    # Strategy 2: Highest Scored Destinations Ordered Geographically
    top_by_score = sorted(suitable_destinations, key=lambda x: x.get("score", 0), reverse=True)
    top_names = [x["place"] for x in top_by_score if x["place"] != origin][:max_dest_count]
    
    # Sort top_names by distance from origin
    top_names_sorted = sorted(top_names, key=lambda d: calculate_distance(origin, d)[0])
    seq2 = [origin] + top_names_sorted
    if seq2 not in candidates:
        candidates.append(seq2)

    # Strategy 3: Alternative Circuit Sequence (Alternative subset of destinations)
    if len(dest_names) >= 2:
        alt_names = dest_names[1:] + [dest_names[0]]
        alt_names_cut = alt_names[:max_dest_count]
        alt_sorted = sorted(alt_names_cut, key=lambda d: calculate_distance(origin, d)[0])
        seq3 = [origin] + alt_sorted
        if seq3 not in candidates:
            candidates.append(seq3)

    # Fallback to ensure at least 3 candidates when sufficient places exist
    if len(candidates) < 3 and len(dest_names) >= 2:
        # Swap last two destinations of candidate 1 if possible
        if len(candidates[0]) >= 3:
            seq4 = list(candidates[0])
            seq4[-1], seq4[-2] = seq4[-2], seq4[-1]
            if seq4 not in candidates:
                candidates.append(seq4)

    return candidates


def generate_daily_route_plan(days, route_nodes, segments, evaluated_map):
    """
    Maps route segments and activities into a day-by-day travel plan.
    Reuses Step 5 activities and Step 6 timing information.
    """
    daily_plan = []
    num_segments = len(segments)

    if num_segments == 0:
        return daily_plan

    for d in range(1, days + 1):
        if d <= num_segments:
            seg = segments[d - 1]
            dest_name = seg["to"]
            route_str = f"{seg['from']} → {seg['to']}"
            dest_list = [seg["from"], seg["to"]]
            travel_time_str = seg["estimated_travel_time"]
        else:
            # Multi-day stay at final destination
            last_seg = segments[-1]
            dest_name = last_seg["to"]
            route_str = f"Explore {dest_name}"
            dest_list = [dest_name]
            travel_time_str = "0m (Local Stay)"

        dest_eval = evaluated_map.get(dest_name, {})
        acts_rec = dest_eval.get("activity_recommendations", {}).get("recommended_activities", [])

        activities = []
        for a in acts_rec[:2]:
            act_obj = {
                "name": a.get("name", "Local Sightseeing"),
                "time": a.get("time_window", "10:00-12:00")
            }
            activities.append(act_obj)

        if not activities:
            activities = [{"name": f"Explore {dest_name} highlights", "time": "09:00-12:00"}]

        daily_plan.append({
            "day": d,
            "route": route_str,
            "destinations": dest_list,
            "travel_time": travel_time_str,
            "activities": activities
        })

    return daily_plan


def generate_route_explanations(route_nodes, overall_score, feasibility_info, backtracking_penalty, evaluated_map):
    """
    Generates factor-backed 'why_recommended' explanations and practical 'tradeoffs'.
    """
    why = []
    tradeoffs = []

    # Evaluate preference & weather alignment across route stops
    matched_prefs = set()
    weather_suitable_count = 0

    for node in route_nodes[1:]:
        item = evaluated_map.get(node, {})
        matched = item.get("preference_match", {}).get("matched", [])
        matched_prefs.update(matched)

        w_cond = item.get("weather_suitability", {}).get("condition", "Good")
        if w_cond in ("Good", "Low", "Excellent"):
            weather_suitable_count += 1

    if "quiet" in matched_prefs or "low_crowd" in matched_prefs:
        why.append("Strong match for quiet and low-crowd preferences")
    if "cool_weather" in matched_prefs or "mountains" in matched_prefs:
        why.append("Matches cool-weather & highland mountain preferences")
    if "nature" in matched_prefs or "beach" in matched_prefs or "heritage" in matched_prefs:
        why.append(f"Covering key interests ({', '.join(list(matched_prefs)[:2])})")

    if backtracking_penalty < 10.0:
        why.append("Route minimizes unnecessary backtracking")
        why.append("Destination sequence is geographically efficient")

    if weather_suitable_count >= len(route_nodes) - 1:
        why.append("Weather conditions are suitable across the entire route")

    if feasibility_info["feasible"]:
        why.append("Travel time is feasible within the selected trip duration")

    if not why:
        why.append("Optimized multi-destination Sri Lanka route sequence")

    # Generate Tradeoffs
    if backtracking_penalty >= 10.0:
        tradeoffs.append("Route includes some geographic backtracking between destinations")

    if not feasibility_info["feasible"]:
        tradeoffs.append(feasibility_info["warning"])

    has_long_segment = False
    for node in route_nodes[1:]:
        item = evaluated_map.get(node, {})
        t_hours = item.get("travel_transport", {}).get("estimated_travel_time_hours", 0)
        if t_hours >= 3.5:
            has_long_segment = True
            break

    if has_long_segment:
        tradeoffs.append("Some route segments require relatively long travel time")

    if not tradeoffs:
        tradeoffs.append("Pace requires timely departures between consecutive destinations")

    return why, tradeoffs


def build_route_recommendations(origin="Colombo", days=1, transport_mode="car", evaluated_items=None):
    """
    Main Route Recommendation Engine pipeline.
    Builds, optimizes, scores, and ranks candidate travel routes.
    """
    if not evaluated_items:
        return []

    evaluated_map = {item["place"]: item for item in evaluated_items}
    suitable_dests = select_suitable_destinations(evaluated_items, top_n=6)

    candidate_sequences = generate_candidate_sequences(origin, days, suitable_dests)
    route_results = []

    for seq in candidate_sequences:
        # Build consecutive segment details independently (Fix Same Distance Bug)
        segments = []
        total_distance_km = 0
        total_travel_time_hours = 0.0

        for i in range(len(seq) - 1):
            from_loc = seq[i]
            to_loc = seq[i + 1]
            seg_info = calculate_segment(from_loc, to_loc, transport_mode)
            segments.append(seg_info)
            total_distance_km += seg_info["distance_km"]
            total_travel_time_hours += seg_info["estimated_travel_time_hours"]

        total_hours = round(total_travel_time_hours, 2)
        tot_h = int(total_hours)
        tot_m = int(round((total_hours - tot_h) * 60))
        total_time_str = f"{tot_h}h {tot_m}m" if tot_h > 0 else f"{tot_m}m"

        # Calculate Sub-component Scores for Route Scoring Formula
        dest_scores = [evaluated_map.get(node, {}).get("score", 75) for node in seq[1:]]
        avg_dest_quality = sum(dest_scores) / float(len(dest_scores)) if dest_scores else 75.0

        backtracking_pen = calculate_backtracking_penalty(seq)
        travel_efficiency = max(0.0, 100.0 - (total_distance_km / float(days * 120)) * 20.0 - backtracking_pen)
        travel_efficiency = min(100.0, max(0.0, travel_efficiency))

        feasibility_info = evaluate_route_feasibility(days, total_hours, len(seq))
        feasibility_score = feasibility_info["feasibility_score"]

        pref_scores = [evaluated_map.get(node, {}).get("preference_match", {}).get("score", 75) for node in seq[1:]]
        pref_alignment = sum(pref_scores) / float(len(pref_scores)) if pref_scores else 75.0

        w_scores = [evaluated_map.get(node, {}).get("weather_suitability", {}).get("score", 75) for node in seq[1:]]
        cs_scores = [evaluated_map.get(node, {}).get("crowd_safety", {}).get("overall_score", 75) for node in seq[1:]]
        w_cs_safety = (sum(w_scores) + sum(cs_scores)) / float(len(w_scores) + len(cs_scores)) if (w_scores and cs_scores) else 75.0

        # Exact Deterministic Route Score Formula:
        # Route Score = Destination Quality * 0.30 + Travel Efficiency * 0.25 + Route Feasibility * 0.20 + Preference Alignment * 0.15 + Weather+Crowd+Safety * 0.10
        overall_route_score = (
            (avg_dest_quality * 0.30) +
            (travel_efficiency * 0.25) +
            (feasibility_score * 0.20) +
            (pref_alignment * 0.15) +
            (w_cs_safety * 0.10)
        )
        overall_route_score = int(round(min(100.0, max(0.0, overall_route_score))))

        decision = classify_decision_level(overall_route_score)
        daily_plan = generate_daily_route_plan(days, seq, segments, evaluated_map)
        why_rec, tradeoffs = generate_route_explanations(seq, overall_route_score, feasibility_info, backtracking_pen, evaluated_map)

        route_display_str = " → ".join(seq)

        route_results.append({
            "route": seq,
            "route_display": route_display_str,
            "overall_route_score": overall_route_score,
            "decision": decision,
            "total_distance_km": total_distance_km,
            "total_travel_time_hours": total_hours,
            "total_travel_time": total_time_str,
            "days": days,
            "feasible": feasibility_info["feasible"],
            "segments": segments,
            "daily_plan": daily_plan,
            "why_recommended": why_rec,
            "tradeoffs": tradeoffs
        })

    # Sort deterministically by overall route score descending
    ranked_routes = sorted(route_results, key=lambda x: x["overall_route_score"], reverse=True)

    # Assign rank index
    for idx, r in enumerate(ranked_routes):
        r["rank"] = idx + 1

    return ranked_routes
