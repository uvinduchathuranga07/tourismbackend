"""
Route Planner Service for Component 2 — Step 7.
Plans realistic multi-stop Sri Lanka travel routes from the user's own request
(e.g. "I want to go to Matara") instead of chaining every high-scoring destination.
Returns raw validated route plans; route_recommendation_engine formats and scores them.
"""

import json
import math
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

try:
    from .travel_transport_engine import get_coordinates
except ImportError:
    from travel_transport_engine import get_coordinates

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")

PLAN_CACHE_TTL_SECONDS = 900
REQUEST_TIMEOUT_SECONDS = 30
MAX_ROAD_DISTANCE_KM = 550

_client = None
_plan_cache = {}


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is not set")
        _client = OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
    return _client


def _destination_context(evaluated_items):
    """Summarizes Step 1-6 destination intelligence so the planner can respect current conditions."""
    lines = []
    for item in sorted(evaluated_items or [], key=lambda x: x.get("score", 0), reverse=True):
        weather = item.get("weather_suitability", {})
        crowd = item.get("crowd_safety", {})
        lines.append(
            f"- {item.get('place')}: overall score {item.get('score', 'n/a')}, "
            f"weather {weather.get('condition', 'n/a')} ({weather.get('score', 'n/a')}), "
            f"crowd/safety score {crowd.get('overall_score', 'n/a')}"
        )
    return "\n".join(lines) if lines else "- (no destination data available)"


def _build_prompt(user_text, origin, days, transport_mode, evaluated_items, route_count):
    return f"""Plan travel routes in Sri Lanka for this traveller.

Traveller request: "{user_text}"
Default starting point: {origin} (use a different start only if the request clearly says "from <place>")
Trip duration: {days} day(s)
Transport mode: {transport_mode}

Current conditions for popular destinations (higher score = better right now):
{_destination_context(evaluated_items)}

Rules:
- If the traveller names a destination (it may be misspelled, e.g. "mathra" = Matara), every route MUST reach it.
- Every stop MUST be in Sri Lanka. If a named place is outside Sri Lanka, return {{"routes": []}}.
- Destinations are NOT limited to the list above (Matara, Unawatuna, Tangalle, Weligama, Haputale, etc. are allowed).
- Only add stops that lie on the way or are short, worthwhile detours. Never add places just because they score well.
- Avoid backtracking and zig-zagging across the island. Keep total driving realistic (about 4-5 hours per day max).
- Number of stops after the start must fit the trip length: roughly 1-2 stops for 1 day, at most days + 1 overall.
- Use realistic road distances and travel times for {transport_mode} (consider expressways such as the Southern Expressway).
- daily_plan must contain exactly {days} entries, one per day.
- places_to_visit MUST contain one entry for EVERY stop after the start, INCLUDING the final destination,
  each with 3-5 real, well-known sights at or near that stop (e.g. Galle: Galle Fort, Galle Lighthouse, Jungle Beach;
  Matara: Matara Fort, Paravi Duwa Temple, Polhena Beach), with a short description and how long to spend.
- Return between 1 and {route_count} distinct routes, best first.

Reply with JSON only, in this exact shape:
{{
  "routes": [
    {{
      "stops": ["<start>", "<stop 1>", "<stop 2>"],
      "coordinates": {{"<start>": [<lat>, <lng>], "<stop 1>": [<lat>, <lng>]}},
      "segments": [
        {{"from": "<start>", "to": "<stop 1>", "distance_km": <number>, "travel_time_hours": <number>}}
      ],
      "daily_plan": [
        {{"day": 1, "route": "<A> → <B>", "destinations": ["<A>", "<B>"], "travel_time": "<e.g. 2h 30m>",
          "activities": [{{"name": "<activity>", "time": "<HH:MM-HH:MM>"}}]}}
      ],
      "places_to_visit": [
        {{"stop": "<stop 1>", "places": [
          {{"name": "<sight>", "category": "<Heritage|Beach|Nature|Wildlife|Religious|Viewpoint|Food|Other>",
            "description": "<one sentence>", "visit_duration": "<e.g. 1-2h>"}}
        ]}},
        {{"stop": "<stop 2>", "places": [ ... ]}}
      ],
      "why_recommended": ["<short reason>"],
      "tradeoffs": ["<short tradeoff>"],
      "score": <0-100 overall suitability for this traveller>
    }}
  ]
}}"""


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _haversine_km(c1, c2):
    lat1, lon1 = c1
    lat2, lon2 = c2
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _clean_route(raw):
    """Validates one planned route; returns None when it is unusable."""
    if not isinstance(raw, dict):
        return None

    stops = [str(s).strip() for s in raw.get("stops", []) if str(s).strip()]
    if len(stops) < 2:
        return None

    coordinates = {}
    for name, pair in (raw.get("coordinates") or {}).items():
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            lat, lng = _to_float(pair[0]), _to_float(pair[1])
            if lat is None or lng is None:
                continue
            # Reject routes that reach a stop outside Sri Lanka's bounding box
            if not (5.5 <= lat <= 10.0 and 79.4 <= lng <= 82.0):
                return None
            coordinates[str(name).strip()] = (lat, lng)

    raw_segments = raw.get("segments") or []
    segments = []
    for i in range(len(stops) - 1):
        seg = raw_segments[i] if i < len(raw_segments) and isinstance(raw_segments[i], dict) else {}
        distance_km = _to_float(seg.get("distance_km"))
        travel_time_hours = _to_float(seg.get("travel_time_hours"))

        # Sanity-check the stated road distance against the stops' coordinates,
        # preferring our trusted coordinates over the planner's own
        c1 = get_coordinates(stops[i]) or coordinates.get(stops[i])
        c2 = get_coordinates(stops[i + 1]) or coordinates.get(stops[i + 1])
        if c1 and c2:
            straight_km = _haversine_km(c1, c2)
            if distance_km is None or distance_km < straight_km or distance_km > straight_km * 2.5:
                distance_km = round(straight_km * 1.35)
                travel_time_hours = None
        elif distance_km is not None and distance_km > MAX_ROAD_DISTANCE_KM:
            # No way to verify, but no road trip within Sri Lanka is this long
            distance_km = None
            travel_time_hours = None

        # Drop travel times that imply an unrealistic average speed
        if distance_km and travel_time_hours and not (15 <= distance_km / travel_time_hours <= 90):
            travel_time_hours = None

        segments.append({
            "from": stops[i],
            "to": stops[i + 1],
            "distance_km": distance_km,
            "travel_time_hours": travel_time_hours,
        })

    daily_plan = []
    for entry in raw.get("daily_plan") or []:
        if not isinstance(entry, dict):
            continue
        activities = [
            {"name": str(a.get("name", "Local Sightseeing")), "time": str(a.get("time", "10:00-12:00"))}
            for a in entry.get("activities") or [] if isinstance(a, dict)
        ]
        daily_plan.append({
            "day": int(_to_float(entry.get("day"), len(daily_plan) + 1)),
            "route": str(entry.get("route", "")),
            "destinations": [str(d) for d in entry.get("destinations") or []],
            "travel_time": str(entry.get("travel_time", "")),
            "activities": activities,
        })

    places_to_visit = []
    for entry in raw.get("places_to_visit") or []:
        if not isinstance(entry, dict) or not str(entry.get("stop", "")).strip():
            continue
        places = [
            {
                "name": str(p.get("name")).strip(),
                "category": str(p.get("category", "Other")),
                "description": str(p.get("description", "")),
                "visit_duration": str(p.get("visit_duration", "")),
            }
            for p in entry.get("places") or [] if isinstance(p, dict) and str(p.get("name", "")).strip()
        ]
        if places:
            places_to_visit.append({"stop": str(entry["stop"]).strip(), "places": places})

    score = _to_float(raw.get("score"), 80.0)

    return {
        "stops": stops,
        "segments": segments,
        "daily_plan": daily_plan,
        "places_to_visit": places_to_visit,
        "why_recommended": [str(r) for r in raw.get("why_recommended") or []],
        "tradeoffs": [str(t) for t in raw.get("tradeoffs") or []],
        "score": min(100.0, max(0.0, score)),
    }


LOCATION_CHECK_PROMPT = """A traveller wrote this request for a Sri Lanka trip planner:
"{user_text}"

List every place the traveller names as a start point or destination.
For each one decide whether it is a real place in Sri Lanka. Treat clear misspellings
of Sri Lankan places as valid (e.g. "katharagama" = Kataragama, "mathra" = Matara).
Places outside Sri Lanka (e.g. Paris, Chennai, Maldives) or words that are not
recognisable place names are NOT valid. Ignore generic words like "beach" or "mountains".

Reply with JSON only:
{{"places": [{{"name": "<as written>", "in_sri_lanka": <true|false>}}]}}"""

_location_cache = {}


def find_invalid_locations(user_text):
    """
    Returns the place names in the request that are not in Sri Lanka (or not recognisable).
    Returns an empty list when nothing is wrong or the check is unavailable.
    """
    if not user_text or not isinstance(user_text, str) or not user_text.strip():
        return []

    cache_key = user_text.strip().lower()
    cached = _location_cache.get(cache_key)
    if cached and time.time() - cached[0] < PLAN_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        client = _get_client()
        model = os.environ.get("OPENAI_ROUTE_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a Sri Lanka geography expert. You always reply with strict JSON only.",
                },
                {"role": "user", "content": LOCATION_CHECK_PROMPT.format(user_text=user_text)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        payload = json.loads(completion.choices[0].message.content)
    except Exception as exc:
        print(f"[test_service] Location check unavailable: {exc}")
        return []

    invalid = [
        str(p.get("name")).strip()
        for p in payload.get("places") or []
        if isinstance(p, dict) and str(p.get("name", "")).strip() and p.get("in_sri_lanka") is False
    ]
    _location_cache[cache_key] = (time.time(), invalid)
    return invalid


def plan_routes(user_text,origin="Colombo", days=1, transport_mode="car", evaluated_items=None, route_count=3):
    """
    Plans candidate routes for the user's request.
    Returns a list of cleaned route plans, or None if planning is unavailable or fails
    (callers should then fall back to the deterministic route engine).
    """
    if not user_text or not isinstance(user_text, str) or not user_text.strip():
        return None

    cache_key = (user_text.strip().lower(), origin, days, transport_mode)
    cached = _plan_cache.get(cache_key)
    if cached and time.time() - cached[0] < PLAN_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        client = _get_client()
        model = os.environ.get("OPENAI_ROUTE_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert Sri Lanka travel route planner with detailed knowledge of "
                        "the island's roads and geography. You always reply with strict JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": _build_prompt(user_text, origin, days, transport_mode, evaluated_items, route_count),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        payload = json.loads(completion.choices[0].message.content)
    except Exception as exc:
        print(f"[test_service] Route planning unavailable, using fallback engine: {exc}")
        return None

    routes = [r for r in (_clean_route(raw) for raw in payload.get("routes") or []) if r]
    if not routes:
        return None

    routes = routes[:route_count]
    _plan_cache[cache_key] = (time.time(), routes)
    return routes
