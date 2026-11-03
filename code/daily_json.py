"""
Group every capture of a day into one compressed NDJSON file (one line = one capture).

Input : the full raw archive (snapshot_2909/raw/status/<date>/*.json.gz)
Output: data/daily_json/status_<date>.ndjson.gz

NOT runnable on the submitted package: the raw archive is not included.
See README.md. Works from any working directory.
"""
import gzip, json, re, sys
from _paths import RAW_STATUS, FULL_DAY, DATA_OUT, NO_FULL, FULL_DAY_NOTE

if RAW_STATUS is None and FULL_DAY is None:
    sys.exit(NO_FULL)
OUT = DATA_OUT / "daily_json"
OUT.mkdir(parents=True, exist_ok=True)

def ts_from(path):
    d = re.sub(r"\D", "", path.name.replace(".json.gz", ""))
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}T{d[8:10]}:{d[10:12]}:{d[12:14]}Z"

if RAW_STATUS is not None:
    day_dirs = sorted(p for p in RAW_STATUS.iterdir() if p.is_dir())
    print(f"source: {RAW_STATUS}")
else:
    day_dirs = [FULL_DAY]
    print(f"source: {FULL_DAY}")
    print(FULL_DAY_NOTE)

for day_dir in day_dirs:
    day = day_dir.name.replace("full_day_", "")
    out_path = OUT / f"status_{day}.ndjson.gz"
    n = 0
    with gzip.open(out_path, "wt", encoding="utf-8") as out:
        for f in sorted(day_dir.glob("*.json.gz")):
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                pay = json.load(fh)
            out.write(json.dumps({
                "fetched_at": ts_from(f),
                "lastUpdatedOther": pay.get("lastUpdatedOther"),
                "ttl": pay.get("ttl"),
                "n_stations": len(pay["data"]["stations"]),
                "stations": pay["data"]["stations"],
            }, ensure_ascii=False) + "\n")
            n += 1
    mb = out_path.stat().st_size / 1024 / 1024
    print(f"{day}  {n:>3} captures  ->  {out_path.name}  {mb:.1f} MB")
