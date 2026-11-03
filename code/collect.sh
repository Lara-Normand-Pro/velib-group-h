#!/bin/bash
# Vélib' GBFS collector, version 2 (after peer review round 1).
#
# Usage (from cron): collect.sh status | collect.sh info
#
# Change from version 1: the file is checked BEFORE it is archived. Version 1 saved
# whatever the server sent and only logged the HTTP code, so a capture that returned 200
# but was incomplete (e.g. 21.09 22:50 UTC: station codes and bike types missing) looked
# exactly like a good one. Now every capture is opened, parsed and checked, and the result
# goes into the log. Nothing is ever deleted: a capture that fails the check is kept in
# quarantine/ so it can still be inspected.
#
# Log line: timestamp,feed,http_code,bytes,n_stations,check
#   check = ok        all required fields present for every station
#           partial   counts present, but some descriptive fields missing (stationCode, bike types)
#           bad       not JSON, no station list, too few stations, or counts missing
#           error     the check itself could not run (python3 missing...); file kept as is
# Lines written by version 1 have only the first three fields; coverage.py reads both.

BASE="https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole"
FEED=$1
[ "$FEED" = "status" ] && F=station_status || F=station_information
TS=$(date -u +%Y%m%dT%H%M%SZ)
DAY=$(date -u +%Y-%m-%d)
DIR="$HOME/velib/$FEED/$DAY"
QDIR="$HOME/velib/quarantine/$FEED/$DAY"
TMP="$HOME/velib/tmp_${FEED}_${TS}.json"
mkdir -p "$DIR" "$HOME/velib"

CODE=$(curl -s -o "$TMP" -w "%{http_code}" --max-time 60 "$BASE/$F.json")
BYTES=$(stat -c %s "$TMP" 2>/dev/null || echo 0)

# content check: prints "n_stations,check"
RES=$(python3 - "$TMP" "$FEED" <<'PY' 2>/dev/null
import json, sys
path, feed = sys.argv[1], sys.argv[2]
MIN_STATIONS = 1400          # the network has about 1,519; far fewer means a truncated file
try:
    st = json.load(open(path, encoding="utf-8"))["data"]["stations"]
except Exception:
    print("0,bad"); sys.exit()
n = len(st)
if feed == "status":
    core = ("station_id", "num_bikes_available", "num_docks_available",
            "is_installed", "is_renting", "is_returning", "last_reported")
    extra = ("stationCode", "num_bikes_available_types")
else:
    core = ("station_id", "lat", "lon", "capacity")
    extra = ("stationCode", "name")
def present(s, k):
    v = s.get(k)
    return v is not None and v != [] and v != [{}, {}]
if n < MIN_STATIONS or not all(all(present(s, k) for k in core) for s in st):
    print(f"{n},bad")
elif not all(all(present(s, k) for k in extra) for s in st):
    print(f"{n},partial")
else:
    print(f"{n},ok")
PY
)
[ -z "$RES" ] && RES="0,error"
CHECK=${RES#*,}

if [ "$CODE" = "200" ] && { [ "$CHECK" = "ok" ] || [ "$CHECK" = "partial" ] || [ "$CHECK" = "error" ]; }; then
    mv "$TMP" "$DIR/$TS.json" && gzip -f "$DIR/$TS.json"
else
    mkdir -p "$QDIR"
    mv "$TMP" "$QDIR/$TS.json" 2>/dev/null && gzip -f "$QDIR/$TS.json"
fi

echo "$TS,$FEED,$CODE,$BYTES,$RES" >> "$HOME/velib/http_log.csv"
