# DK Konnektor — Project Re-Entry File
*Claude: read this before touching anything.*

---

## What This Is
A DraftKings DFS edge detector for PGA Tour golf.
Dark-theme Flask dashboard on port 5563. Scores players using 4 signals.
Modeled after Kalshi Konnektor — same machine aesthetic, golf-specific data.

## Re-Entry Phrase
> "Re-entry: DK Konnektor"

## Current Status — ✅ BUILT (needs API keys)
- Signal engine: `edge.py` (divergence 35%, value 30%, course fit 25%, ownership 10%)
- Data fetcher: `data_fetcher.py` (Odds API, Polymarket, Kalshi, DataGolf, OpenWeatherMap)
- Lineup optimizer: `optimizer.py` (Monte Carlo, salary cap, exposure constraints)
- Flask server: `app.py` (port 5563, localhost only)
- Dashboard: `templates/index.html` (full dark-theme machine UI)

## File Structure
```
dk-konnektor/
├── app.py              ← Flask server (port 5563)
├── edge.py             ← 4-signal edge scoring engine
├── data_fetcher.py     ← Multi-source data (Odds API, Polymarket, Kalshi, DataGolf, weather)
├── optimizer.py        ← Monte Carlo lineup builder
├── templates/
│   └── index.html      ← Full dashboard UI
├── static/             ← Drop logo.png here
├── data/               ← Auto-generated snapshots
├── requirements.txt
├── launch.command      ← Double-click to run on Mac
├── Makefile
├── .env                ← API keys (never commit)
└── .env.example        ← Safe template
```

## How to Run
```bash
cd ~/dk-konnektor
make setup   # first time only
make run
# open http://localhost:5563
```

## API Keys Needed (for live data)
1. `ODDS_API_KEY` — the-odds-api.com (free tier works, 500 req/mo)
2. `DATAGOLF_API_KEY` — datagolf.com/api-access (paid, ~$30/mo)
3. `WEATHER_API_KEY` — openweathermap.org (free tier works)

Without keys: mock data loads automatically for all sources.

## What's Next
- [ ] Add logo.png to static/
- [ ] Set API keys in .env for live data
- [ ] Create GitHub repo: `gh repo create papjamzzz/dk-konnektor --private`
- [ ] Register in launcher at ~/launcher/templates/index.html (port 5563)
- [ ] Verify DK player names match DraftKings CSV export before uploading lineups
- [ ] Add week-over-week score history chart in detail panel

## Key Technical Decisions
- Same 4-signal architecture as Kalshi Konnektor (divergence/value/fit/ownership)
- Salary cap: $50,000, roster: 6 G slots (Classic format)
- Mock data fallback keeps dashboard live when no API keys present
- Monte Carlo optimizer with exposure caps prevents over-rostering chalk
- 10-min cache prevents API rate-limit hammering

## Signal Weights
- Odds Divergence (35%) — market disagreement = mispricing
- Salary Value (30%) — implied probability vs. salary ratio
- Course Fit (25%) — SG profile × course archetype
- Ownership Leverage (10%) — contrarian GPP positioning

## Course Profiles
bomber | approach | putting | balanced | precision
Set via `course_profile` in `data_fetcher.py` → `get_tournament_info()`

---
*Last updated: 2026-03-25 — initial build*
