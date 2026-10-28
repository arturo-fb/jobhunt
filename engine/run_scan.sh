#!/bin/bash
# Daily JobHunt scan wrapper — used by launchd/cron.
# Resolves the project dir from its own location, finds a python3, runs the scan.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR" || exit 1

# Run at most once per day. On macOS launchd pokes this script every 15 min (see the plist template),
# so most invocations should exit instantly here. If today's scan already
# succeeded (last_scan.json holds today's date), do nothing.
TODAY=$(date +%F)
if grep -q "\"$TODAY\"" data/last_scan.json 2>/dev/null; then
    exit 0
fi

# Don't run before this hour (local time). Keeps the 15-min catch-up poke from
# firing at midnight; earliest daily run is EARLIEST_HOUR:00, matching the plist.
EARLIEST_HOUR="${JOBHUNT_EARLIEST_HOUR:-6}"   # set by install_schedule.sh --hour
HOUR=$((10#$(date +%H)))
if [ "$HOUR" -lt "$EARLIEST_HOUR" ]; then
    exit 0
fi

# Pick a python3: env override first, then common conda locations, then system.
PY=""
for CAND in "$JOBHUNT_PYTHON" \
            "$HOME/anaconda3/bin/python3" \
            "$HOME/miniconda3/bin/python3" \
            "$HOME/opt/anaconda3/bin/python3" \
            "/opt/anaconda3/bin/python3" \
            "$(command -v python3)"; do
    if [ -n "$CAND" ] && [ -x "$CAND" ]; then PY="$CAND"; break; fi
done

if [ -z "$PY" ]; then
    echo "$(date): no python3 found" >> data/run_log.txt
    exit 1
fi

"$PY" engine/jobhunt.py >> data/run_log.txt 2>&1
