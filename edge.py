"""
DK Konnektor — Multi-Signal Edge Detection Engine
Combines odds divergence, ownership, course fit, and value signals
to produce a 0–100 edge score per player.
"""
import math

# ── SIGNAL WEIGHTS ─────────────────────────────────────────────────────────────
W_DIVERGENCE = 0.35   # Odds market disagreement (biggest alpha source)
W_VALUE      = 0.30   # Salary value vs. implied probability
W_COURSE_FIT = 0.25   # Course/condition profile match
W_OWNERSHIP  = 0.10   # Contrarian ownership leverage

# ── COURSE PROFILE ARCHETYPES ─────────────────────────────────────────────────
COURSE_PROFILES = {
    "bomber":    {"sg_ott": 0.40, "sg_app": 0.35, "sg_atg": 0.15, "sg_putt": 0.10},
    "approach":  {"sg_ott": 0.20, "sg_app": 0.50, "sg_atg": 0.20, "sg_putt": 0.10},
    "putting":   {"sg_ott": 0.15, "sg_app": 0.30, "sg_atg": 0.20, "sg_putt": 0.35},
    "balanced":  {"sg_ott": 0.25, "sg_app": 0.30, "sg_atg": 0.25, "sg_putt": 0.20},
    "precision": {"sg_ott": 0.15, "sg_app": 0.45, "sg_atg": 0.25, "sg_putt": 0.15},
}

# ── SIGNAL 1: ODDS DIVERGENCE ─────────────────────────────────────────────────
def sig_divergence(player):
    """
    How much do the markets disagree on this player?
    Large divergence = mispricing somewhere = edge.
    Score 0–100: 0 = all markets agree, 100 = massive disagreement.
    """
    odds = {}
    for key in ["implied_dk", "implied_fanduel", "implied_kalshi",
                "implied_polymarket", "implied_vegas", "implied_betmgm"]:
        v = player.get(key)
        if v is not None and v > 0:
            odds[key] = v

    if len(odds) < 2:
        return 50.0  # neutral if only 1 source

    values = list(odds.values())
    spread = max(values) - min(values)
    avg    = sum(values) / len(values)

    # Normalize: 20pp spread = max score, <2pp = near 0
    normalized = min(spread / 20.0, 1.0)

    # Bonus if DK sportsbook is the outlier (direct edge on their platform)
    dk_v = odds.get("implied_dk")
    if dk_v is not None:
        dk_divergence = abs(dk_v - avg) / max(avg, 1)
        dk_bonus = min(dk_divergence * 0.3, 0.25)
    else:
        dk_bonus = 0.0

    return round(min((normalized + dk_bonus) * 100, 100), 1)


# ── SIGNAL 2: SALARY VALUE ────────────────────────────────────────────────────
def sig_value(player, salary_cap=50000, roster_size=6):
    """
    How efficient is the salary relative to implied win probability?
    Overpriced chalk = low score. Underpriced bomber = high score.
    """
    salary  = player.get("salary", 0)
    implied = player.get("implied_consensus", 0)  # avg win probability %
    proj    = player.get("projection", 0)

    if salary <= 0:
        return 0.0

    # Average salary per slot
    avg_sal = salary_cap / roster_size   # $8,333

    # Salary ratio: 1.0 = exactly average price
    sal_ratio = salary / avg_sal

    # Value = implied probability / salary ratio
    # High implied + low salary = high value
    if implied > 0:
        raw_value = (implied / 100) / sal_ratio
    elif proj > 0:
        # Fallback to projection-based value
        raw_value = (proj / 50.0) / sal_ratio  # 50 pts = "average" projection
    else:
        raw_value = 0.5

    # Normalize to 0–100 (0.3 = low value, 1.5 = elite value)
    normalized = (raw_value - 0.3) / (1.5 - 0.3)
    return round(min(max(normalized * 100, 0), 100), 1)


# ── SIGNAL 3: COURSE FIT ──────────────────────────────────────────────────────
def sig_course_fit(player, course_profile="balanced", wind_mph=0):
    """
    How well does this player's SG profile match the course archetype?
    Bombers at bomber tracks, approach artists at precision courses, etc.
    """
    profile = COURSE_PROFILES.get(course_profile, COURSE_PROFILES["balanced"])

    # Wind adjustment: high wind boosts bomber penalty (accuracy matters more)
    wind_factor = 1.0
    if wind_mph >= 20:
        # Shift weight from OTT to approach/ATG in high wind
        wind_factor = 0.85
    elif wind_mph >= 12:
        wind_factor = 0.93

    # Player SG stats (normalized to Tour average = 0, elite = +2.0)
    sg_ott  = player.get("sg_ott",  0.0)
    sg_app  = player.get("sg_app",  0.0)
    sg_atg  = player.get("sg_atg",  0.0)
    sg_putt = player.get("sg_putt", 0.0)

    # Weighted score vs. course demands
    fit = (
        sg_ott  * profile["sg_ott"]  * wind_factor +
        sg_app  * profile["sg_app"] +
        sg_atg  * profile["sg_atg"] +
        sg_putt * profile["sg_putt"]
    )

    # Course history bonus
    hist_bonus = player.get("course_history_score", 0.0) * 0.15

    # Total SG on tour normalizes well: -1.0 = bad, 0 = avg, +2.5 = elite
    # Map to 0–100: -1.0 → 20, 0 → 50, +2.5 → 100
    normalized = (fit + hist_bonus + 1.0) / 3.5
    return round(min(max(normalized * 100, 0), 100), 1)


# ── SIGNAL 4: OWNERSHIP LEVERAGE ─────────────────────────────────────────────
def sig_ownership(player):
    """
    Contrarian ownership signal.
    Low projected ownership + high upside = GPP leverage.
    High ownership + mediocre upside = chalk trap.
    """
    proj_own  = player.get("projected_ownership", 20.0)   # % of lineups
    ceiling   = player.get("ceiling", player.get("projection", 40.0))
    implied   = player.get("implied_consensus", 5.0)

    # Leverage ratio: (upside / ownership) — higher is better for GPP
    if proj_own <= 0:
        leverage = 2.0
    else:
        leverage = (ceiling / max(proj_own, 1)) * (implied / max(proj_own * 0.3, 1))

    # Normalize: leverage of 3+ = elite contrarian, <0.5 = chalk trap
    normalized = (leverage - 0.5) / (3.0 - 0.5)
    return round(min(max(normalized * 100, 0), 100), 1)


# ── MASTER EDGE SCORE ─────────────────────────────────────────────────────────
def compute_edge_score(player, course_profile="balanced", wind_mph=0):
    """Combine all 4 signals into a single 0–100 edge score."""
    s1 = sig_divergence(player)
    s2 = sig_value(player)
    s3 = sig_course_fit(player, course_profile, wind_mph)
    s4 = sig_ownership(player)

    raw = (
        s1 * W_DIVERGENCE +
        s2 * W_VALUE +
        s3 * W_COURSE_FIT +
        s4 * W_OWNERSHIP
    )

    # Narrative bonus — injury concern, Masters bubble, defending champ etc.
    narrative_mod = player.get("narrative_mod", 1.0)  # 0.7–1.3
    final = min(raw * narrative_mod, 100)

    player["sig_divergence"] = s1
    player["sig_value"]      = s2
    player["sig_course_fit"] = s3
    player["sig_ownership"]  = s4
    player["edge_score"]     = round(final, 1)
    return player


# ── KELLY SIZING ──────────────────────────────────────────────────────────────
def kelly_label(edge_score):
    if edge_score >= 80: return "3–5%"
    if edge_score >= 65: return "2–3%"
    if edge_score >= 50: return "1–2%"
    if edge_score >= 35: return "0.5–1%"
    return "Pass"


# ── TIER LABEL ────────────────────────────────────────────────────────────────
def tier_label(edge_score):
    if edge_score >= 80: return "ELITE"
    if edge_score >= 65: return "STRONG"
    if edge_score >= 50: return "LEAN"
    if edge_score >= 35: return "WEAK"
    return "FADE"
