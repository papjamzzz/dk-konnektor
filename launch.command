#!/bin/bash
cd "$(dirname "$0")"

# Kill any existing instance on port 5563
pkill -f "python3 app.py" 2>/dev/null
sleep 0.5

# Activate venv if present
if [ -d "venv" ]; then
  source venv/bin/activate
fi

# Install deps silently if needed
python3 -m pip install -r requirements.txt -q

# Open browser
sleep 1.5 && open http://localhost:5563 &

# Launch
python3 app.py
