"""
One day of raw captures (NDJSON) to a single human-readable CSV.

Input : data/status_YYYY-MM-DD.ndjson.gz   (one line per capture)
Output: data/status_YYYY-MM-DD.csv         (one row per station per capture)

Run from the package root:  python code/ndjson_to_csv.py
Optionally pass a date:     python code/ndjson_to_csv.py 2026-09-21

The CSV is a convenience file for reading the data in Excel. It holds exactly the same
information as the Parquet table, in a format about five times larger.

lr_age_min (called lag_min before 03.11) is the age of last_reported when we read it,
not a delay of the counts: see DATA_DICTIONARY.md.
"""
import csv, datetime as dt, glob, gzip, json, os, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

day = sys.argv[1] if len(sys.argv) > 1 else None
pattern = f"data/status_{day}.ndjson.gz" if day else "data/status_*.ndjson.gz"
hits = sorted(glob.glob(str(ROOT / pattern)))
if not hits:
    sys.exit(f"no file matching {pattern} under {ROOT}")
src = pathlib.Path(hits[-1])
dst = src.with_suffix("").with_suffix(".csv")      # .ndjson.gz -> .csv

COLS = ["fetched_at", "station_id", "stationCode", "num_bikes_available",
        "mechanical", "ebike", "num_docks_available", "is_installed",
        "is_renting", "is_returning", "last_reported", "last_reported_utc", "lr_age_min"]

print(f"source: {src}")
n_rows = n_caps = 0
with gzip.open(src, "rt", encoding="utf-8") as fh, \
     open(dst, "w", newline="", encoding="utf-8") as out:
    w = csv.DictWriter(out, fieldnames=COLS)
    w.writeheader()
    for line in fh:
        cap = json.loads(line)
        ts = cap["fetched_at"]                      # e.g. 2026-09-21T08:20:01Z
        t = dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        n_caps += 1
        for s in cap["stations"]:
            types = {k: v for d in (s.get("num_bikes_available_types") or []) for k, v in d.items()}
            lr = s.get("last_reported")
            lr_utc = dt.datetime.fromtimestamp(lr, dt.timezone.utc) if lr else None
            w.writerow({
                "fetched_at": ts,
                "station_id": s.get("station_id"),
                "stationCode": s.get("stationCode"),
                "num_bikes_available": s.get("num_bikes_available"),
                "mechanical": types.get("mechanical"),
                "ebike": types.get("ebike"),
                "num_docks_available": s.get("num_docks_available"),
                "is_installed": s.get("is_installed"),
                "is_renting": s.get("is_renting"),
                "is_returning": s.get("is_returning"),
                "last_reported": lr,
                "last_reported_utc": lr_utc.strftime("%Y-%m-%dT%H:%M:%SZ") if lr_utc else "",
                "lr_age_min": round((t - lr_utc).total_seconds() / 60, 1) if lr_utc else "",
            })
            n_rows += 1

mb = os.path.getsize(dst) / 1024 / 1024
print(f"{n_caps} captures, {n_rows} rows -> {dst.name}  ({mb:.1f} MB)")
