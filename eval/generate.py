"""Build the 50 evaluation scenarios: 10 seeded itineraries x 5 events (the kinds of A-E).

    python -m eval.generate --out backend/tests/scenarios/eval50

Same code -> same files. Itineraries come from the property-test generator; the event is
attached here by fixed rules (the generator's own random event is replaced).
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from app.schemas.recovery import RecoveryInput
from app.services.travel_estimate import fill_missing_travel
from tests.engine.generators import DAY_START, HOTEL, random_instance

N_ITINERARIES = 10
MIN_ACTIVITIES = 6
KINDS = ("DELAY", "WEATHER", "CLOSURE", "FATIGUE", "EXTEND")


def itinerary_seeds() -> list[int]:
    seeds, seed = [], 0
    while len(seeds) < N_ITINERARIES:
        if len(random_instance(seed, 8, (4, 12)).activities) >= MIN_ACTIVITIES:
            seeds.append(seed)
        seed += 1
    return seeds


def with_event(base: RecoveryInput, kind: str, seed: int) -> dict:
    rng = random.Random(f"{seed}-{kind}")
    data = base.model_dump(mode="json")
    acts = sorted(base.activities, key=lambda a: (a.planned_start, a.id))
    if kind == "DELAY":
        start = DAY_START + 5 * rng.randint(12, 30)  # 1h to 2.5h late
        data["event"] = {"type": "DELAY", "occurred_at": DAY_START, "start_time": start}
    elif kind == "WEATHER":
        start = 5 * rng.randint(132, 168)  # 11:00 to 14:00
        end = start + 5 * rng.randint(24, 48) if rng.random() < 0.5 else None
        data["event"] = {"type": "WEATHER", "occurred_at": DAY_START, "start_time": start, "end_time": end}
    elif kind == "FATIGUE":
        data["event"] = {"type": "FATIGUE", "occurred_at": DAY_START, "walking_ratio": 0.5}
    elif kind == "EXTEND":
        first = acts[0]
        data["event"] = {
            "type": "EXTEND", "occurred_at": first.planned_start, "location_id": first.id,
            "activity_id": first.id, "extra_minutes": 5 * rng.randint(3, 8),
        }
    else:  # CLOSURE: one activity is closed, two substitute places are offered
        target = rng.choice(acts)
        data["event"] = {"type": "CLOSURE", "occurred_at": DAY_START, "activity_id": target.id}
        subs = [
            {
                "id": f"{target.id}_alt{k}", "replaces": target.id, "title": f"{target.id} alternative {k}",
                "lat": round(35.64 + rng.random() * 0.09, 5), "lng": round(139.68 + rng.random() * 0.10, 5),
                "duration": target.planned_end - target.planned_start, "min_duration": target.min_duration,
                "penalty": rng.choice([0.2, 0.5]),
            }
            for k in (1, 2)
        ]
        points = {"hotel": HOTEL, **{a.id: (a.lat, a.lng) for a in base.activities}}
        points.update({s["id"]: (s["lat"], s["lng"]) for s in subs})
        data["substitutes"] = subs
        data["travel"] = [t.model_dump() for t in fill_missing_travel(points, base.travel)]
    data["expected"] = {"violations": 0}
    return data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("backend/tests/scenarios/eval50"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for n, seed in enumerate(itinerary_seeds()):
        base = random_instance(seed, 8, (4, 12))
        for kind in KINDS:
            data = with_event(base, kind, seed)
            RecoveryInput.model_validate({k: v for k, v in data.items() if k != "expected"})
            path = args.out / f"i{n:02d}_{kind.lower()}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {N_ITINERARIES * len(KINDS)} scenarios to {args.out}")


if __name__ == "__main__":
    main()
