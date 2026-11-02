"""Seeded random itineraries for property tests. Same seed -> same instance."""

import random

from app.schemas.enums import Category
from app.schemas.models import HOTEL_ID
from app.schemas.recovery import RecoveryInput
from app.services.travel_estimate import fill_missing_travel

HOTEL = (35.6896, 139.7006)
DAY_START = 540  # 09:00
DAY_END = 1320  # 22:00


def random_instance(
    seed: int, max_activities: int = 6, length_units: tuple[int, int] = (6, 24)
) -> RecoveryInput:
    rng = random.Random(seed)
    n = max_activities if length_units[1] < 8 else rng.randint(2, max_activities)
    points = {HOTEL_ID: HOTEL}
    for i in range(n):
        points[f"a{i}"] = (35.64 + rng.random() * 0.09, 139.68 + rng.random() * 0.10)
    travel = fill_missing_travel(points)
    minutes = {frozenset((t.a, t.b)): t.minutes for t in travel}

    # Build an original plan that is feasible: gaps are at least the travel time.
    plan: list[tuple[str, int, int]] = []
    prev, t = HOTEL_ID, DAY_START
    for i in range(n):
        aid = f"a{i}"
        start = t + minutes[frozenset((prev, aid))] + 5 * rng.randint(0, 6)
        end = start + 5 * rng.randint(*length_units)
        if end + minutes[frozenset((aid, HOTEL_ID))] > DAY_END:
            break
        plan.append((aid, start, end))
        prev, t = aid, end
    if len(plan) < 2:
        return random_instance(seed + 10_000, max_activities, length_units)

    activities, preferences = [], []
    for aid, start, end in plan:
        length = end - start
        reserved = rng.random() < 0.2
        min_duration = length if reserved else max(5, 5 * round(length * rng.uniform(0.3, 1) / 5))
        window = rng.random() < 0.2
        activities.append(
            {
                "id": aid,
                "title": aid,
                "category": rng.choice(list(Category)).value,
                "lat": points[aid][0],
                "lng": points[aid][1],
                "planned_start": start,
                "planned_end": end,
                "min_duration": min(min_duration, length),
                "intent_tags": rng.sample(["x", "y", "z"], rng.randint(0, 2)),
                "outdoor": rng.choice([True, False, None]),
                "walking": rng.choice([True, False, None]),
                "open_at": start - 5 * rng.randint(0, 12) if window else None,
                "close_at": end + 5 * rng.randint(0, 12) if window else None,
                "reservation_time": start if reserved else None,
            }
        )
        preferences.append(
            {
                "activity_id": aid,
                "tier": rng.choice(["must", "nice", "nice", "optional", "optional"]),
                "substitutability": round(rng.random(), 2),
                "time_rigidity": "reserved" if reserved else "flexible",
            }
        )

    used = {HOTEL_ID} | {aid for aid, _, _ in plan}
    travel = tuple(t for t in travel if t.a in used and t.b in used)

    first_id, first_start, first_end = plan[0]
    kind = rng.choice(["DELAY", "WEATHER", "EXTEND", "FATIGUE"])
    if kind == "DELAY":
        event = {"type": "DELAY", "occurred_at": DAY_START,
                 "start_time": DAY_START + 5 * rng.randint(0, 36)}
    elif kind == "WEATHER":
        event = {"type": "WEATHER", "occurred_at": DAY_START,
                 "start_time": 5 * rng.randint(108, 216)}
    elif kind == "FATIGUE":
        event = {"type": "FATIGUE", "occurred_at": DAY_START,
                 "walking_ratio": rng.choice([0.5, 0.7])}
    else:  # the user is inside the first activity and wants more time there
        event = {"type": "EXTEND", "occurred_at": first_start + 5 * rng.randint(0, (first_end - first_start) // 5 - 1),
                 "location_id": first_id, "activity_id": first_id,
                 "extra_minutes": 5 * rng.randint(3, 12)}

    return RecoveryInput.model_validate(
        {
            "day": {"id": "d", "start_time": DAY_START, "end_deadline": DAY_END,
                    "end_lat": HOTEL[0], "end_lng": HOTEL[1]},
            "activities": activities,
            "preferences": preferences,
            "travel": [t.model_dump() for t in travel],
            "event": event,
        }
    )
