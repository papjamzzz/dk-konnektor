"""
DK Konnektor — Lineup Optimizer
Monte Carlo lineup builder with salary cap + exposure constraints.
"""
import random

SALARY_CAP   = 50000
ROSTER_SIZE  = 6
MAX_ATTEMPTS = 50000


def build_lineups(players, count=20, stack_names=None):
    """
    Build `count` unique DK Classic lineups from scored player pool.

    - Respects $50,000 salary cap
    - Enforces per-player max_exposure (defaults to 60% if not set)
    - Deduplicates lineups
    - Returns list of lineup dicts sorted by total projected score
    """
    pool = [p for p in players if p.get("salary", 0) > 0]
    if len(pool) < ROSTER_SIZE:
        return []

    # Compute max appearances per player
    max_app = {}
    for p in pool:
        cap = p.get("max_exposure", 0.6)
        max_app[p["name"]] = max(1, round(cap * count))

    lineups   = []
    seen      = set()
    attempts  = 0
    app_count = {p["name"]: 0 for p in pool}

    # Bias sampling toward higher edge scores
    weights = [max(p["edge_score"] ** 1.5, 1) for p in pool]
    total_w = sum(weights)
    probs   = [w / total_w for w in weights]

    while len(lineups) < count and attempts < MAX_ATTEMPTS:
        attempts += 1

        # Weighted sample without replacement
        try:
            chosen = _weighted_sample(pool, ROSTER_SIZE, probs)
        except ValueError:
            continue

        # Salary check
        total_sal = sum(p["salary"] for p in chosen)
        if total_sal > SALARY_CAP:
            continue

        # Minimum salary floor (avoid punt-heavy lineups)
        if total_sal < SALARY_CAP * 0.88:
            continue

        # Exposure check
        over = False
        for p in chosen:
            if app_count[p["name"]] >= max_app[p["name"]]:
                over = True
                break
        if over:
            continue

        # Dedup by sorted name tuple
        key = tuple(sorted(p["name"] for p in chosen))
        if key in seen:
            continue

        seen.add(key)
        for p in chosen:
            app_count[p["name"]] += 1

        total_proj = round(sum(p.get("projection", 35) for p in chosen), 1)
        total_edge = round(sum(p["edge_score"] for p in chosen) / ROSTER_SIZE, 1)

        lineup = {
            "players":    [_player_summary(p) for p in chosen],
            "salary":     total_sal,
            "salary_rem": SALARY_CAP - total_sal,
            "total_proj": total_proj,
            "avg_edge":   total_edge,
        }
        lineups.append(lineup)

    lineups.sort(key=lambda x: x["avg_edge"], reverse=True)
    return lineups


def _weighted_sample(pool, k, probs):
    """Sample k items from pool without replacement using given probabilities."""
    selected = []
    remaining = list(zip(probs, pool))

    for _ in range(k):
        if not remaining:
            raise ValueError("Pool exhausted")
        total = sum(w for w, _ in remaining)
        r = random.random() * total
        cumul = 0
        idx = 0
        for i, (w, _) in enumerate(remaining):
            cumul += w
            if r <= cumul:
                idx = i
                break
        _, chosen = remaining.pop(idx)
        selected.append(chosen)

    return selected


def _player_summary(p):
    return {
        "name":       p.get("name"),
        "salary":     p.get("salary"),
        "edge_score": p.get("edge_score"),
        "tier":       p.get("tier"),
        "projection": p.get("projection"),
        "proj_own":   p.get("projected_ownership"),
    }


def lineups_to_dk_csv(lineups, tournament_name="PGA TOUR"):
    """
    Format lineups as DraftKings bulk upload CSV.
    Returns CSV string.
    """
    import csv
    from io import StringIO

    si = StringIO()
    w  = csv.writer(si)
    w.writerow(["Entry ID", "Contest Name", "Contest ID", "Entry Fee",
                "G", "G", "G", "G", "G", "G"])

    for lineup in lineups:
        names = [p["name"] for p in lineup["players"]]
        while len(names) < 6:
            names.append("")
        w.writerow(["", tournament_name, "", ""] + names[:6])

    return si.getvalue()
