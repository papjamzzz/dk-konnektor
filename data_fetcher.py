"""
DK Konnektor — Multi-Source Data Fetcher
Pulls from: The Odds API (DK/FD/Vegas), Polymarket, Kalshi, Weather
"""
import os, time, json, math, hmac, hashlib, requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

ODDS_API_KEY      = os.getenv("ODDS_API_KEY", "")        # the-odds-api.com
KALSHI_API_KEY    = os.getenv("KALSHI_API_KEY", "")
KALSHI_KEY_ID     = os.getenv("KALSHI_KEY_ID", "")
WEATHER_API_KEY   = os.getenv("OPENWEATHER_API_KEY", "")
DATAGOLF_API_KEY  = os.getenv("DATAGOLF_API_KEY", "")

ODDS_API_BASE  = "https://api.the-odds-api.com/v4"
KALSHI_BASE    = "https://trading-api.kalshi.com/trade-api/v2"
POLY_BASE      = "https://gamma-api.polymarket.com"
DATAGOLF_BASE  = "https://feeds.datagolf.com"
WEATHER_BASE   = "https://api.openweathermap.org/data/2.5"

_cache = {}
CACHE_TTL = 600  # 10 minutes

def _cached(key, fn, ttl=CACHE_TTL):
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < ttl:
        return _cache[key]["data"]
    result = fn()
    _cache[key] = {"ts": now, "data": result}
    return result


# ── THE ODDS API — DK/FD/Vegas/BetMGM ────────────────────────────────────────
def fetch_odds(sport="golf_pga_championship_winner"):
    """Pull win odds from all sportsbooks via the-odds-api.com"""
    if not ODDS_API_KEY:
        return _mock_odds()

    def _fetch():
        try:
            url = f"{ODDS_API_BASE}/sports/{sport}/odds"
            r = requests.get(url, params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "h2h",
                "oddsFormat": "american",
            }, timeout=10)
            if r.status_code == 200:
                return _parse_odds_api(r.json())
        except Exception as e:
            print(f"[ODDS API] {e}")
        return _mock_odds()

    return _cached("odds", _fetch)


def _parse_odds_api(data):
    """Parse the-odds-api response into {player_name: {dk, fanduel, vegas, betmgm}} implied probs"""
    result = {}
    BOOK_MAP = {
        "draftkings": "dk",
        "fanduel": "fanduel",
        "betmgm": "betmgm",
        "bovada": "vegas",
        "williamhill_us": "vegas",
        "pointsbetus": "vegas",
    }
    for event in data:
        for bm in event.get("bookmakers", []):
            book_key = bm.get("key", "")
            label = BOOK_MAP.get(book_key)
            if not label:
                continue
            for market in bm.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    name  = outcome.get("name", "")
                    price = outcome.get("price", 0)
                    impl  = american_to_implied(price)
                    if name not in result:
                        result[name] = {}
                    # Keep best (lowest) implied prob per book (multiple events)
                    if label not in result[name] or impl < result[name][label]:
                        result[name][label] = round(impl, 3)
    return result


def american_to_implied(american):
    """Convert American odds to implied probability %"""
    if american > 0:
        return 100 / (american + 100) * 100
    elif american < 0:
        return (-american) / (-american + 100) * 100
    return 50.0


def _mock_odds():
    """Demo data when no API key is set"""
    return {
        "Min Woo Lee":           {"dk": 7.1, "fanduel": 7.1, "betmgm": 7.7, "vegas": 7.4},
        "Chris Gotterup":        {"dk": 5.9, "fanduel": 5.9, "betmgm": 6.2, "vegas": 6.1},
        "Jake Knapp":            {"dk": 4.8, "fanduel": 4.8, "betmgm": 5.1, "vegas": 4.9},
        "Brooks Koepka":         {"dk": 4.3, "fanduel": 4.5, "betmgm": 4.3, "vegas": 4.4},
        "Sam Burns":             {"dk": 4.3, "fanduel": 4.3, "betmgm": 4.2, "vegas": 4.3},
        "Michael Thorbjornsen":  {"dk": 3.8, "fanduel": 4.0, "betmgm": 3.9, "vegas": 3.9},
        "Wyndham Clark":         {"dk": 2.7, "fanduel": 2.8, "betmgm": 2.6, "vegas": 2.7},
        "Nicolai Hojgaard":      {"dk": 3.8, "fanduel": 3.9, "betmgm": 3.8, "vegas": 3.8},
        "Sahith Theegala":       {"dk": 2.4, "fanduel": 2.4, "betmgm": 2.3, "vegas": 2.4},
        "Ryan Gerard":           {"dk": 3.2, "fanduel": 3.1, "betmgm": 3.4, "vegas": 3.2},
        "Tony Finau":            {"dk": 1.8, "fanduel": 1.8, "betmgm": 1.9, "vegas": 1.8},
        "Pierceson Coody":       {"dk": 2.4, "fanduel": 2.4, "betmgm": 2.3, "vegas": 2.4},
        "Stephan Jaeger":        {"dk": 1.8, "fanduel": 1.8, "betmgm": 1.7, "vegas": 1.8},
        "Taylor Pendrith":       {"dk": 2.2, "fanduel": 2.2, "betmgm": 2.1, "vegas": 2.2},
        "Jordan Smith":          {"dk": 2.2, "fanduel": 2.3, "betmgm": 2.1, "vegas": 2.2},
        "Aaron Rai":             {"dk": 1.9, "fanduel": 1.9, "betmgm": 2.0, "vegas": 1.9},
        "Marco Penge":           {"dk": 3.6, "fanduel": 3.5, "betmgm": 3.7, "vegas": 3.6},
        "Ben Griffin":           {"dk": 2.8, "fanduel": 2.7, "betmgm": 2.9, "vegas": 2.8},
        "Rasmus Hojgaard":       {"dk": 2.8, "fanduel": 2.8, "betmgm": 2.7, "vegas": 2.8},
        "Rickie Fowler":         {"dk": 2.9, "fanduel": 3.0, "betmgm": 3.0, "vegas": 3.0},
        "Harry Hall":            {"dk": 2.4, "fanduel": 2.4, "betmgm": 2.3, "vegas": 2.4},
        "Gary Woodland":         {"dk": 0.7, "fanduel": 0.8, "betmgm": 0.7, "vegas": 0.7},
        "J.T. Poston":           {"dk": 0.8, "fanduel": 0.7, "betmgm": 0.8, "vegas": 0.8},
    }


# ── POLYMARKET ────────────────────────────────────────────────────────────────
def fetch_polymarket_golf():
    """Pull active golf markets from Polymarket gamma API"""
    def _fetch():
        try:
            r = requests.get(f"{POLY_BASE}/markets", params={
                "tag": "golf", "active": "true", "limit": 50
            }, timeout=8)
            if r.status_code == 200:
                return _parse_polymarket(r.json())
        except Exception as e:
            print(f"[POLYMARKET] {e}")
        return {}

    return _cached("polymarket", _fetch)


def _parse_polymarket(data):
    """Extract player name → implied prob from Polymarket markets"""
    result = {}
    markets = data if isinstance(data, list) else data.get("markets", [])
    for m in markets:
        question = m.get("question", "")
        price = m.get("outcomePrices", [])
        if price and len(price) >= 1:
            try:
                impl = float(price[0]) * 100
                # Extract player name from question (rough heuristic)
                for word in question.replace("?", "").split():
                    if len(word) > 4 and word[0].isupper():
                        result[question] = round(impl, 2)
                        break
            except Exception:
                pass
    return result


# ── KALSHI GOLF MARKETS ───────────────────────────────────────────────────────
def fetch_kalshi_golf():
    """Pull golf-related Kalshi markets"""
    def _fetch():
        try:
            r = requests.get(f"{KALSHI_BASE}/events", params={
                "series_ticker": "GOLF", "limit": 50
            }, timeout=8)
            if r.status_code == 200:
                return _parse_kalshi(r.json())
        except Exception as e:
            print(f"[KALSHI] {e}")
        return {}

    return _cached("kalshi_golf", _fetch)


def _parse_kalshi(data):
    result = {}
    for event in data.get("events", []):
        for market in event.get("markets", []):
            title  = market.get("title", "")
            yes_ask = market.get("yes_ask", 50)
            result[title] = round(yes_ask, 2)
    return result


# ── WEATHER ───────────────────────────────────────────────────────────────────
def fetch_weather(city="Houston,US"):
    """Current weather for tournament location"""
    def _fetch():
        if not WEATHER_API_KEY:
            return _mock_weather()
        try:
            r = requests.get(f"{WEATHER_BASE}/weather", params={
                "q": city, "appid": WEATHER_API_KEY, "units": "imperial"
            }, timeout=6)
            if r.status_code == 200:
                d = r.json()
                return {
                    "temp_f":      round(d["main"]["temp"]),
                    "wind_mph":    round(d["wind"]["speed"]),
                    "wind_dir":    d["wind"].get("deg", 0),
                    "description": d["weather"][0]["description"],
                    "humidity":    d["main"]["humidity"],
                    "city":        city,
                }
        except Exception as e:
            print(f"[WEATHER] {e}")
        return _mock_weather()

    return _cached("weather", _fetch, ttl=1800)


def _mock_weather():
    return {
        "temp_f": 83, "wind_mph": 13, "wind_dir": 180,
        "description": "Partly cloudy", "humidity": 58,
        "city": "Houston, TX"
    }


# ── DATAGOLF SG STATS ─────────────────────────────────────────────────────────
def fetch_sg_stats():
    """Pull strokes gained stats from DataGolf (free tier)"""
    def _fetch():
        if not DATAGOLF_API_KEY:
            return _mock_sg_stats()
        try:
            r = requests.get(f"{DATAGOLF_BASE}/preds/pre-tournament-archive", params={
                "tour": "pga", "event_id": "current",
                "file_format": "json", "key": DATAGOLF_API_KEY
            }, timeout=10)
            if r.status_code == 200:
                return _parse_sg(r.json())
        except Exception as e:
            print(f"[DATAGOLF] {e}")
        return _mock_sg_stats()

    return _cached("sg_stats", _fetch)


def _parse_sg(data):
    result = {}
    for player in data.get("players", []):
        name = player.get("player_name", "")
        result[name] = {
            "sg_ott":  round(player.get("sg_ott",  0.0), 2),
            "sg_app":  round(player.get("sg_app",  0.0), 2),
            "sg_atg":  round(player.get("sg_atg",  0.0), 2),
            "sg_putt": round(player.get("sg_putt", 0.0), 2),
            "sg_total":round(player.get("sg_total",0.0), 2),
        }
    return result


# ── TOURNAMENT META ───────────────────────────────────────────────────────────
def get_tournament_info():
    """Return current tournament context for edge scoring."""
    weather = fetch_weather()
    return {
        "tournament":      "Texas Children's Houston Open",
        "course":          "Memorial Park Golf Course",
        "course_profile":  "bomber",   # long, tree-lined, rewards distance
        "location":        "Houston, TX",
        "wind_mph":        weather.get("wind_mph", 0),
        "conditions":      weather.get("conditions", "Unknown"),
        "temp_f":          weather.get("temp_f", 70),
    }


# ── MASTER FETCH ──────────────────────────────────────────────────────────────
def fetch_all():
    """
    Pull all data sources and merge into (meta, players) tuple.
    Returns:
        meta    — dict with tournament/course/weather context
        players — list of player dicts ready for edge scoring
    """
    meta      = get_tournament_info()
    odds_data = _cached("odds", lambda: fetch_odds() if ODDS_API_KEY else _mock_odds())
    poly_data = fetch_polymarket_golf()
    kals_data = fetch_kalshi_golf()
    sg_data   = fetch_sg_stats()

    # DK salaries + projections (Houston Open field)
    salaries = _dk_salaries()

    # Build player list
    players = []
    all_names = set(salaries.keys()) | set(odds_data.keys()) | set(sg_data.keys())

    for name in all_names:
        sal_info  = salaries.get(name, {})
        sal       = sal_info.get("salary", 0)
        if sal == 0:
            continue  # not in DK pool this week

        o = odds_data.get(name, {})
        s = sg_data.get(name, {})

        # Implied probabilities from each book
        imp_dk      = o.get("dk", 0)
        imp_fd      = o.get("fanduel", 0)
        imp_vegas   = o.get("vegas", 0)
        imp_betmgm  = o.get("betmgm", 0)
        imp_poly    = poly_data.get(name, 0)
        imp_kalshi  = kals_data.get(name, 0)

        # Consensus = average of available sources
        avail = [v for v in [imp_dk, imp_fd, imp_vegas, imp_betmgm, imp_poly, imp_kalshi] if v > 0]
        consensus = round(sum(avail) / len(avail), 3) if avail else 0

        players.append({
            "name":                 name,
            "salary":               sal,
            "projection":           sal_info.get("projection", 38.0),
            "ceiling":              sal_info.get("ceiling",    55.0),
            "projected_ownership":  sal_info.get("ownership",  15.0),
            "max_exposure":         sal_info.get("max_exp",    0.60),
            "course_history_score": sal_info.get("course_hist",0.0),
            "narrative_mod":        sal_info.get("narrative",  1.0),
            # Odds signals
            "implied_dk":           imp_dk,
            "implied_fanduel":      imp_fd,
            "implied_vegas":        imp_vegas,
            "implied_betmgm":       imp_betmgm,
            "implied_polymarket":   imp_poly,
            "implied_kalshi":       imp_kalshi,
            "implied_consensus":    consensus,
            # SG stats
            "sg_ott":               s.get("sg_ott",  0.0),
            "sg_app":               s.get("sg_app",  0.0),
            "sg_atg":               s.get("sg_atg",  0.0),
            "sg_putt":              s.get("sg_putt", 0.0),
        })

    return meta, players


# ── DK SALARY POOL ────────────────────────────────────────────────────────────
def _dk_salaries():
    """Houston Open DK salary pool. Update weekly from DK CSV export."""
    return {
        "Min Woo Lee":          {"salary": 10500, "projection": 43, "ceiling": 62, "ownership": 18, "max_exp": 0.55, "course_hist": 0.3, "narrative": 1.1},
        "Chris Gotterup":       {"salary": 9800,  "projection": 41, "ceiling": 60, "ownership": 16, "max_exp": 0.60, "course_hist": 0.2, "narrative": 1.1},
        "Jake Knapp":           {"salary": 8200,  "projection": 38, "ceiling": 56, "ownership": 10, "max_exp": 0.60, "course_hist": 0.1, "narrative": 1.05},
        "Brooks Koepka":        {"salary": 9200,  "projection": 39, "ceiling": 58, "ownership": 14, "max_exp": 0.50, "course_hist": 0.0, "narrative": 1.0},
        "Sam Burns":            {"salary": 9000,  "projection": 40, "ceiling": 58, "ownership": 15, "max_exp": 0.55, "course_hist": 0.5, "narrative": 1.05},
        "Michael Thorbjornsen": {"salary": 7800,  "projection": 36, "ceiling": 52, "ownership": 8,  "max_exp": 0.55, "course_hist": 0.1, "narrative": 1.0},
        "Wyndham Clark":        {"salary": 8800,  "projection": 37, "ceiling": 55, "ownership": 11, "max_exp": 0.55, "course_hist": 0.1, "narrative": 0.9},
        "Nicolai Hojgaard":     {"salary": 8600,  "projection": 38, "ceiling": 56, "ownership": 12, "max_exp": 0.60, "course_hist": 0.0, "narrative": 1.0},
        "Sahith Theegala":      {"salary": 8400,  "projection": 38, "ceiling": 56, "ownership": 13, "max_exp": 0.55, "course_hist": 0.2, "narrative": 1.0},
        "Ryan Gerard":          {"salary": 7400,  "projection": 35, "ceiling": 51, "ownership": 7,  "max_exp": 0.55, "course_hist": 0.0, "narrative": 1.0},
        "Tony Finau":           {"salary": 8600,  "projection": 37, "ceiling": 54, "ownership": 12, "max_exp": 0.50, "course_hist": 0.3, "narrative": 0.95},
        "Pierceson Coody":      {"salary": 7600,  "projection": 35, "ceiling": 51, "ownership": 9,  "max_exp": 0.55, "course_hist": 0.2, "narrative": 1.0},
        "Stephan Jaeger":       {"salary": 7400,  "projection": 35, "ceiling": 51, "ownership": 8,  "max_exp": 0.55, "course_hist": 0.0, "narrative": 1.0},
        "Taylor Pendrith":      {"salary": 7800,  "projection": 36, "ceiling": 52, "ownership": 9,  "max_exp": 0.55, "course_hist": 0.0, "narrative": 1.0},
        "Jordan Smith":         {"salary": 6800,  "projection": 33, "ceiling": 48, "ownership": 6,  "max_exp": 0.55, "course_hist": 0.0, "narrative": 1.0},
        "Aaron Rai":            {"salary": 7200,  "projection": 34, "ceiling": 50, "ownership": 7,  "max_exp": 0.55, "course_hist": 0.0, "narrative": 1.0},
        "Marco Penge":          {"salary": 6800,  "projection": 33, "ceiling": 48, "ownership": 6,  "max_exp": 0.55, "course_hist": 0.0, "narrative": 1.0},
        "Ben Griffin":          {"salary": 7600,  "projection": 35, "ceiling": 51, "ownership": 9,  "max_exp": 0.55, "course_hist": 0.0, "narrative": 1.0},
        "Rasmus Hojgaard":      {"salary": 7400,  "projection": 35, "ceiling": 51, "ownership": 8,  "max_exp": 0.55, "course_hist": 0.0, "narrative": 1.0},
        "Rickie Fowler":        {"salary": 8000,  "projection": 36, "ceiling": 53, "ownership": 11, "max_exp": 0.50, "course_hist": 0.2, "narrative": 0.95},
        "Harry Hall":           {"salary": 6800,  "projection": 33, "ceiling": 49, "ownership": 7,  "max_exp": 0.55, "course_hist": 0.0, "narrative": 1.0},
        "Gary Woodland":        {"salary": 6200,  "projection": 30, "ceiling": 44, "ownership": 5,  "max_exp": 0.40, "course_hist": 0.1, "narrative": 0.9},
        "J.T. Poston":          {"salary": 6800,  "projection": 33, "ceiling": 49, "ownership": 7,  "max_exp": 0.50, "course_hist": 0.2, "narrative": 1.0},
    }


def _mock_sg_stats():
    return {
        "Min Woo Lee":          {"sg_ott": 0.8, "sg_app": 1.1, "sg_atg": 0.6, "sg_putt": 0.4, "sg_total": 2.9},
        "Chris Gotterup":       {"sg_ott": 1.4, "sg_app": 1.2, "sg_atg": 0.3, "sg_putt": 0.1, "sg_total": 3.0},
        "Jake Knapp":           {"sg_ott": 1.2, "sg_app": 0.9, "sg_atg": 0.5, "sg_putt": 0.6, "sg_total": 3.2},
        "Brooks Koepka":        {"sg_ott": 0.9, "sg_app": 1.4, "sg_atg": 0.2, "sg_putt": -0.1,"sg_total": 2.4},
        "Sam Burns":            {"sg_ott": 0.5, "sg_app": 0.8, "sg_atg": 0.7, "sg_putt": 0.5, "sg_total": 2.5},
        "Michael Thorbjornsen": {"sg_ott": 1.1, "sg_app": 0.8, "sg_atg": 0.4, "sg_putt": 0.2, "sg_total": 2.5},
        "Wyndham Clark":        {"sg_ott": 1.3, "sg_app": 0.7, "sg_atg": 0.3, "sg_putt": 0.1, "sg_total": 2.4},
        "Nicolai Hojgaard":     {"sg_ott": 0.9, "sg_app": 1.0, "sg_atg": 0.5, "sg_putt": 0.3, "sg_total": 2.7},
        "Sahith Theegala":      {"sg_ott": 1.0, "sg_app": 0.9, "sg_atg": 0.6, "sg_putt": 0.2, "sg_total": 2.7},
        "Ryan Gerard":          {"sg_ott": 0.7, "sg_app": 1.3, "sg_atg": 0.4, "sg_putt": 0.1, "sg_total": 2.5},
        "Tony Finau":           {"sg_ott": 1.1, "sg_app": 0.6, "sg_atg": 0.5, "sg_putt": 0.3, "sg_total": 2.5},
        "Pierceson Coody":      {"sg_ott": 1.2, "sg_app": 0.7, "sg_atg": 0.3, "sg_putt": 0.1, "sg_total": 2.3},
        "Stephan Jaeger":       {"sg_ott": 0.8, "sg_app": 1.0, "sg_atg": 0.5, "sg_putt": 0.4, "sg_total": 2.7},
        "Taylor Pendrith":      {"sg_ott": 1.5, "sg_app": 0.6, "sg_atg": 0.2, "sg_putt": -0.1,"sg_total": 2.2},
        "Jordan Smith":         {"sg_ott": 1.3, "sg_app": 0.5, "sg_atg": 0.3, "sg_putt": 0.2, "sg_total": 2.3},
        "Aaron Rai":            {"sg_ott": 0.6, "sg_app": 0.9, "sg_atg": 0.4, "sg_putt": 0.2, "sg_total": 2.1},
        "Marco Penge":          {"sg_ott": 0.7, "sg_app": 0.8, "sg_atg": 0.3, "sg_putt": 0.1, "sg_total": 1.9},
        "Ben Griffin":          {"sg_ott": 1.0, "sg_app": 0.6, "sg_atg": 0.4, "sg_putt": 0.3, "sg_total": 2.3},
        "Rasmus Hojgaard":      {"sg_ott": 0.8, "sg_app": 0.9, "sg_atg": 0.4, "sg_putt": 0.2, "sg_total": 2.3},
        "Harry Hall":           {"sg_ott": 0.5, "sg_app": 0.7, "sg_atg": 0.5, "sg_putt": 0.4, "sg_total": 2.1},
        "Tony Finau":           {"sg_ott": 1.1, "sg_app": 0.8, "sg_atg": 0.4, "sg_putt": 0.1, "sg_total": 2.4},
        "Gary Woodland":        {"sg_ott": 0.9, "sg_app": 0.3, "sg_atg": 0.1, "sg_putt": -0.1,"sg_total": 1.2},
        "J.T. Poston":          {"sg_ott": 0.2, "sg_app": 0.5, "sg_atg": 0.4, "sg_putt": 0.7, "sg_total": 1.8},
    }
