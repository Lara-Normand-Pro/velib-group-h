"""
Content check of every archived status capture: the check the collector did not do
before 03.11, applied afterwards to the files it saved.

Why: a request can return 200 and a file can open while its content is incomplete.
21.09 at 22:50 UTC is the example found by Group I: 1,518 stations, bike and dock counts
present, but stationCode and the mechanical/electric split missing everywhere. The HTTP
log cannot show this, and "the file opens" cannot either.

Same rules as the check now built into collect.sh:
  ok       every station has the core fields and the descriptive ones
  partial  core fields (counts, flags, last_reported) complete; descriptive fields missing
  bad      not readable, fewer than 1,400 stations, or core fields missing

Input : raw status captures (full archive, else raw_sample/full_day_*, else raw_sample/)
Output: data/capture_quality.csv (one row per capture)

Runs on the submitted package. Works from any working directory.
"""
import gzip, json, re, sys
import pandas as pd
from _paths import RAW_STATUS, FULL_DAY, SAMPLE_STATUS, DATA_OUT, NO_RAW

MIN_STATIONS = 1400
CORE = ("station_id", "num_bikes_available", "num_docks_available",
        "is_installed", "is_renting", "is_returning", "last_reported")
EXTRA = ("stationCode", "num_bikes_available_types")

def present(s, k):
    v = s.get(k)
    return v is not None and v != [] and v != [{}, {}]

def check(path):
    row = {"file": path.name, "bytes": path.stat().st_size}
    d = re.sub(r"\D", "", path.name)[:14]
    row["fetched_at"] = pd.to_datetime(d, format="%Y%m%d%H%M%S", utc=True)
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            st = json.load(fh)["data"]["stations"]
    except Exception as e:
        return {**row, "n_stations": 0, "check": "bad", "problem": f"unreadable: {e}"[:80]}
    row["n_stations"] = len(st)
    miss = {k: sum(not present(s, k) for s in st) for k in CORE + EXTRA}
    row.update({f"missing_{k}": v for k, v in miss.items()})
    core_miss = [k for k in CORE if miss[k]]
    extra_miss = [k for k in EXTRA if miss[k]]
    if len(st) < MIN_STATIONS or core_miss:
        row.update(check="bad", problem=f"{len(st)} stations; missing {core_miss}")
    elif extra_miss:
        row.update(check="partial", problem=f"missing {extra_miss}")
    else:
        row.update(check="ok", problem="")
    return row

if RAW_STATUS is not None:
    files = sorted(RAW_STATUS.glob("*/*.json.gz"))
elif FULL_DAY is not None:
    files = sorted(FULL_DAY.glob("*.json.gz")) + list(SAMPLE_STATUS)
else:
    files = list(SAMPLE_STATUS)
if not files:
    sys.exit(NO_RAW)

DATA_OUT.mkdir(parents=True, exist_ok=True)
q = pd.DataFrame([check(f) for f in files]).sort_values("fetched_at")
q = q.drop_duplicates("fetched_at")          # sample files duplicate full-day ones
q.to_csv(DATA_OUT / "capture_quality.csv", index=False)

print(f"{len(q)} captures checked")
print(q["check"].value_counts().to_string(), "\n")
print("size (KB):", (q["bytes"] / 1024).describe()[["min", "50%", "max"]].round(1).to_dict())
print("stations per capture:", q["n_stations"].value_counts().sort_index().to_dict(), "\n")
odd = q[q["check"] != "ok"]
if len(odd):
    print("captures that are not ok:")
    print(odd[["fetched_at", "bytes", "n_stations", "check", "problem"]].to_string(index=False))
print(f"\nwritten to {DATA_OUT / 'capture_quality.csv'}")
