"""
Travel & Transportation Availability Engine for Component 2 — Step 3.
Provides deterministic travel time estimation, distance metrics, transport options, and suitability scoring.
"""

ROUTE_DISTANCE_KM = {
    # From Colombo
    ("Colombo", "Ella"): 205,
    ("Colombo", "Galle"): 120,
    ("Colombo", "Sigiriya"): 175,
    ("Colombo", "Kandy"): 115,
    ("Colombo", "Nuwara Eliya"): 170,
    ("Colombo", "Mirissa"): 150,
    ("Colombo", "Bentota"): 65,
    ("Colombo", "Arugam Bay"): 320,
    ("Colombo", "Anuradhapura"): 205,
    ("Colombo", "Polonnaruwa"): 215,
    ("Colombo", "Jaffna"): 395,
    ("Colombo", "Trincomalee"): 265,
    ("Colombo", "Yala"): 260,
    ("Colombo", "Hikkaduwa"): 100,
    ("Colombo", "Dambulla"): 150,

    # Key Inter-City Pairwise Segments
    ("Kandy", "Nuwara Eliya"): 76,
    ("Nuwara Eliya", "Ella"): 55,
    ("Kandy", "Ella"): 135,
    ("Kandy", "Sigiriya"): 90,
    ("Kandy", "Dambulla"): 72,
    ("Kandy", "Polonnaruwa"): 140,
    ("Kandy", "Anuradhapura"): 138,
    ("Sigiriya", "Dambulla"): 25,
    ("Sigiriya", "Polonnaruwa"): 67,
    ("Dambulla", "Anuradhapura"): 65,
    ("Anuradhapura", "Polonnaruwa"): 105,
    ("Anuradhapura", "Jaffna"): 195,
    ("Polonnaruwa", "Trincomalee"): 105,
    ("Dambulla", "Trincomalee"): 108,
    ("Galle", "Mirissa"): 35,
    ("Galle", "Hikkaduwa"): 20,
    ("Bentota", "Hikkaduwa"): 35,
    ("Bentota", "Galle"): 55,
    ("Mirissa", "Yala"): 145,
    ("Ella", "Yala"): 95,
    ("Ella", "Arugam Bay"): 135,
    ("Yala", "Arugam Bay"): 160,
    ("Trincomalee", "Jaffna"): 235
}

TRANSPORT_CONFIG = {
    "car": {
        "average_speed_kmh": 45,
        "availability": "high",
        "label": "Car",
        "icon": "🚗"
    },
    "bus": {
        "average_speed_kmh": 35,
        "availability": "high",
        "label": "Bus",
        "icon": "🚌"
    },
    "train": {
        "average_speed_kmh": 40,
        "availability": "medium",
        "label": "Train",
        "icon": "🚆"
    }
}


import math

DESTINATION_COORDINATES = {
    "Colombo": (6.9271, 79.8612),
    "Ella": (6.8667, 81.0466),
    "Galle": (6.0535, 80.2210),
    "Sigiriya": (7.9570, 80.7603),
    "Kandy": (7.2906, 80.6337),
    "Nuwara Eliya": (6.9497, 80.7891),
    "Mirissa": (5.9483, 80.4716),
    "Bentota": (6.4218, 79.9950),
    "Arugam Bay": (6.8404, 81.8378),
    "Anuradhapura": (8.3114, 80.4037),
    "Polonnaruwa": (7.9403, 81.0188),
    "Jaffna": (9.6615, 80.0255),
    "Trincomalee": (8.5874, 81.2152),
    "Yala": (6.3725, 81.5185),
    "Hikkaduwa": (6.1407, 80.1010),
    "Dambulla": (7.8742, 80.6511)
}


def calculate_distance(origin, destination):
    """Calculates route distance in kilometers from origin to destination."""
    orig = origin.strip().title() if origin else "Colombo"
    dest = destination.strip().title() if destination else "Kandy"

    if orig == dest:
        return 0, False

    dist = ROUTE_DISTANCE_KM.get((orig, dest)) or ROUTE_DISTANCE_KM.get((dest, orig))
    if dist is not None:
        return dist, False

    # Coordinate-based Haversine distance with road winding factor
    c1 = DESTINATION_COORDINATES.get(orig)
    c2 = DESTINATION_COORDINATES.get(dest)
    if c1 and c2:
        lat1, lon1 = c1
        lat2, lon2 = c2
        r = 6371.0  # Earth radius km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        straight_km = r * c
        road_km = int(round(straight_km * 1.35))
        return max(10, road_km), True

    # Benchmark fallback estimation for unlisted destinations
    return 150, True


def estimate_travel_time(distance_km, transport_mode="car"):
    """
    Estimates travel time in hours (float) and human-readable string (e.g., '2h 34m').
    """
    mode = transport_mode.lower() if transport_mode else "car"
    cfg = TRANSPORT_CONFIG.get(mode, TRANSPORT_CONFIG["car"])
    speed = cfg.get("average_speed_kmh", 45)

    if distance_km <= 0:
        return 0.0, "0m"

    hours_float = round(distance_km / speed, 2)
    total_minutes = int(round(hours_float * 60))
    h = total_minutes // 60
    m = total_minutes % 60

    if h > 0 and m > 0:
        time_str = f"{h}h {m}m"
    elif h > 0:
        time_str = f"{h}h"
    else:
        time_str = f"{m}m"

    return hours_float, time_str


def get_transport_options(origin, destination, distance_km):
    """
    Returns planning-level transportation options for the given origin and destination.
    """
    options = []
    for mode_key, cfg in TRANSPORT_CONFIG.items():
        hours_val, time_str = estimate_travel_time(distance_km, mode_key)
        options.append({
            "mode": mode_key,
            "label": cfg["label"],
            "icon": cfg["icon"],
            "available": True,
            "estimated_time_hours": hours_val,
            "estimated_time": time_str,
            "availability": cfg["availability"]
        })
    return options


def calculate_transport_score(distance_km, travel_time_hours, selected_mode, options):
    """
    Calculates deterministic transport suitability score (0-100).
    """
    # A. Travel Time Score
    if travel_time_hours < 2.0:
        time_score = 100.0
    elif travel_time_hours < 3.5:
        time_score = 85.0
    elif travel_time_hours < 5.0:
        time_score = 65.0
    else:
        time_score = 40.0

    # B. Availability Score
    mode_cfg = TRANSPORT_CONFIG.get(selected_mode.lower(), TRANSPORT_CONFIG["car"])
    avail_level = mode_cfg.get("availability", "high")
    avail_score = 100.0 if avail_level == "high" else 75.0

    # C. Accessibility Score
    avail_count = sum(1 for o in options if o.get("available"))
    access_score = 100.0 if avail_count >= 3 else 75.0 if avail_count == 2 else 50.0

    weighted = (time_score * 0.45) + (avail_score * 0.30) + (access_score * 0.25)
    return int(round(min(100.0, max(0.0, weighted))))


def evaluate_transport_suitability(score):
    """Classifies transport suitability level based on score."""
    if score >= 85:
        return "excellent"
    elif score >= 70:
        return "good"
    elif score >= 50:
        return "moderate"
    else:
        return "difficult"


def build_travel_transport_summary(origin="Colombo", destination="Kandy", transport_mode="car"):
    """
    Builds the complete travel_transport summary object for a destination recommendation.
    """
    orig_str = origin.strip().title() if origin else "Colombo"
    dest_str = destination.strip().title() if destination else "Kandy"
    mode_str = transport_mode.lower() if transport_mode else "car"

    distance_km, is_estimated = calculate_distance(orig_str, dest_str)
    hours_float, time_str = estimate_travel_time(distance_km, mode_str)
    options = get_transport_options(orig_str, dest_str, distance_km)

    score = calculate_transport_score(distance_km, hours_float, mode_str, options)
    suitability = evaluate_transport_suitability(score)

    mode_cfg = TRANSPORT_CONFIG.get(mode_str, TRANSPORT_CONFIG["car"])
    availability_level = mode_cfg.get("availability", "high")

    # Generate warnings & reasons
    warnings = []
    reasons = []

    if hours_float >= 5.0 or distance_km >= 250:
        warnings.append("Travel time is relatively long for a day trip from Colombo.")
        warnings.append("Destination is relatively far from Colombo.")

    if distance_km <= 120:
        reasons.append(f"Short travel time from {orig_str}")
    elif hours_float <= 3.5:
        reasons.append(f"Moderate travel duration from {orig_str}")

    if len(options) >= 3:
        reasons.append("Multiple transportation options available")

    if mode_str == "car":
        reasons.append("Private car provides the shortest estimated travel time")

    return {
        "origin": orig_str,
        "destination": dest_str,
        "distance_km": distance_km,
        "is_estimated_distance": is_estimated,
        "selected_transport_mode": mode_str,
        "estimated_travel_time_hours": hours_float,
        "estimated_travel_time": time_str,
        "transport_score": score,
        "suitability": suitability,
        "availability": availability_level,
        "transport_options": options,
        "warnings": warnings,
        "reasons": reasons
    }
