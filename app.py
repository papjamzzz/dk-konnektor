"""
DK Konnektor — Flask Dashboard Server
DraftKings DFS edge detector for PGA Tour golf
Run:  python3 app.py
Open: http://localhost:5563
"""

import json
import os
import time
from datetime import datetime

from flask import Flask, jsonify, render_template, request

from data_fetcher import fetch_all, get_tournament_info
from edge import compute_edge_score, kelly_label, tier_label

app = Flask(__name__)

# ── In-memory cache ───────────────────────────────────────────────────────────
_cache = {
    "players":   None,
    "meta":      None,
    "timestamp": 0,
    "ttl":       600,    # 10 min
    "fetching":  False,
}


def refresh_cache(force=False):
    now = time.time()
    age = now - _cache["timestamp"]

    if not force and _cache["players"] is not None and age < _cache["ttl"]:
        return _cache["players"]

    if _cache["fetching"]:
        return _cache["players"] or []

    _cache["fetching"] = True
    try:
        meta, players_raw = fetch_all()
        course_profile = meta.get("course_profile", "balanced")
        wind_mph       = meta.get("wind_mph", 0)

        players = []
        for p in players_raw:
            scored = compute_edge_score(dict(p), course_profile=course_profile, wind_mph=wind_mph)
            scored["kelly"]  = kelly_label(scored["edge_score"])
            scored["tier"]   = tier_label(scored["edge_score"])
            players.append(scored)

        players.sort(key=lambda x: x["edge_score"], reverse=True)

        _cache["players"]   = players
        _cache["meta"]      = meta
        _cache["timestamp"] = time.time()

        _save_snapshot(players, meta)
        return players

    except Exception as e:
        print(f"  ⚠ Fetch error (returning stale): {e}")
        return _cache["players"] or []
    finally:
        _cache["fetching"] = False


def _save_snapshot(players, meta):
    os.makedirs("data", exist_ok=True)
    snap = {
        "timestamp": datetime.now().isoformat(),
        "meta":      meta,
        "players":   players,
    }
    fname = f"data/snap_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(fname, "w") as f:
        json.dump(snap, f)


def _load_snapshots(limit=60):
    data_dir = "data"
    if not os.path.exists(data_dir):
        return []
    files = sorted(
        f for f in os.listdir(data_dir)
        if f.startswith("snap_") and f.endswith(".json")
    )[-limit:]
    snaps = []
    for fname in files:
        try:
            with open(os.path.join(data_dir, fname)) as f:
                snaps.append(json.load(f))
        except Exception:
            pass
    return snaps


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/players")
def api_players():
    force   = request.args.get("refresh") == "1"
    players = refresh_cache(force=force)
    meta    = _cache["meta"] or {}
    cache_age = round(time.time() - _cache["timestamp"]) if _cache["timestamp"] else None

    tiers = {t: 0 for t in ["ELITE", "STRONG", "LEAN", "WEAK", "FADE"]}
    for p in players:
        tiers[p.get("tier", "FADE")] = tiers.get(p.get("tier", "FADE"), 0) + 1

    return jsonify({
        "players":    players,
        "total":      len(players),
        "meta":       meta,
        "tiers":      tiers,
        "timestamp":  datetime.fromtimestamp(_cache["timestamp"]).isoformat()
                      if _cache["timestamp"] else None,
        "cache_age":  cache_age,
        "top_score":  players[0]["edge_score"] if players else 0,
        "avg_score":  round(sum(p["edge_score"] for p in players) / len(players), 1)
                      if players else 0,
    })


@app.route("/api/player/<name>")
def api_player(name):
    """Return full signal breakdown for a specific player."""
    players = _cache["players"] or []
    for p in players:
        if p.get("name", "").lower() == name.lower():
            return jsonify(p)
    return jsonify({"error": "not found"}), 404


@app.route("/api/movers")
def api_movers():
    """Top edge score movers vs. previous snapshot."""
    snaps = _load_snapshots(limit=2)
    if len(snaps) < 2:
        return jsonify([])

    prev = {p["name"]: p["edge_score"] for p in snaps[-2].get("players", [])}
    curr = snaps[-1].get("players", [])

    movers = []
    for p in curr:
        n = p["name"]
        if n in prev:
            delta = round(p["edge_score"] - prev[n], 1)
            if abs(delta) >= 1.0:
                movers.append({**p, "delta": delta})

    movers.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return jsonify(movers[:15])


@app.route("/api/lineups", methods=["POST"])
def api_lineups():
    """Generate optimized DK lineups from current player pool."""
    from optimizer import build_lineups
    players = _cache["players"] or []
    if not players:
        return jsonify({"error": "No player data loaded yet"}), 400

    count  = int(request.json.get("count", 20))
    stacks = request.json.get("stacks", [])
    lineups = build_lineups(players, count=count, stack_names=stacks)

    return jsonify({"lineups": lineups, "count": len(lineups)})


@app.route("/api/export/csv")
def api_export_csv():
    """Export current edge scores as CSV."""
    from io import StringIO
    import csv
    from flask import Response

    players = _cache["players"] or []
    si = StringIO()
    w  = csv.writer(si)
    w.writerow(["Name", "Salary", "Edge Score", "Tier", "Kelly",
                "Divergence", "Value", "Course Fit", "Ownership",
                "Implied Consensus", "Projected Own"])
    for p in players:
        w.writerow([
            p.get("name"),
            p.get("salary"),
            p.get("edge_score"),
            p.get("tier"),
            p.get("kelly"),
            p.get("sig_divergence"),
            p.get("sig_value"),
            p.get("sig_course_fit"),
            p.get("sig_ownership"),
            p.get("implied_consensus"),
            p.get("projected_ownership"),
        ])

    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=dk_edge.csv"},
    )


@app.route("/api/stats")
def api_stats():
    players = _cache["players"] or []
    if not players:
        return jsonify({})

    return jsonify({
        "total":       len(players),
        "top_score":   players[0]["edge_score"] if players else 0,
        "avg_score":   round(sum(p["edge_score"] for p in players) / len(players), 1),
        "elite_count": sum(1 for p in players if p.get("tier") == "ELITE"),
        "strong_count":sum(1 for p in players if p.get("tier") == "STRONG"),
        "fade_count":  sum(1 for p in players if p.get("tier") == "FADE"),
        "avg_salary":  round(sum(p.get("salary", 0) for p in players) / len(players)),
        "course_profile": (_cache["meta"] or {}).get("course_profile", "balanced"),
        "wind_mph":    (_cache["meta"] or {}).get("wind_mph", 0),
        "tournament":  (_cache["meta"] or {}).get("tournament", "Unknown"),
    })


# ── Startup ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import threading

    def background_load():
        print("  Fetching player data in background...")
        refresh_cache(force=True)
        print(f"  ✓ Loaded {len(_cache['players'] or [])} players\n")

    print("\n" + "=" * 55)
    print("  ⚡ DK KONNEKTOR — DRAFTKINGS EDGE DETECTOR")
    print("=" * 55)
    print("  Open: http://localhost:5563")
    print("  Data loading in background — page is live now")
    print("=" * 55 + "\n")

    t = threading.Thread(target=background_load, daemon=True)
    t.start()

    app.run(debug=False, port=5563, host="127.0.0.1")
