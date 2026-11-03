"""
Flatten the raw GBFS captures into one Parquet file per day.

Input : the full raw archive (snapshot_2909/raw/status/<date>/*.json.gz)
Output: data/station_status/date=<date>/part-0.parquet

Nothing is dropped or corrected here: this step only flattens. Cleaning is clean.py.

Changes after peer review round 1:
- `lag_min` is renamed `lr_age_min`. It is the age of the last_reported timestamp when we
  read it, NOT the delay of the counts: last_reported renews about once an hour while the
  counts change between our 5-minute captures (see docs/data_quality_and_cleaning).
- stationCode and the mechanical / electric split are now kept (null when the capture
  lacks them, e.g. 21.09 22:50).

Runs on the full archive when it is there, otherwise on the untouched captures in
raw_sample/, which is what a reader of the submitted package gets. Works from any
working directory.
"""
import gzip, json, os, re, sys
import pandas as pd
from _paths import (RAW_STATUS, FULL_DAY, SAMPLE_STATUS, DATA_OUT,
                    NO_RAW, SAMPLE_NOTE, FULL_DAY_NOTE)

if RAW_STATUS is None and FULL_DAY is None and not SAMPLE_STATUS:
    sys.exit(NO_RAW)
OUT = DATA_OUT / "station_status"
COLS = ["station_id", "num_bikes_available", "num_docks_available",
        "is_installed", "is_renting", "is_returning", "last_reported"]

def ts_from(path):
    """Timestamp of the fetch, taken from <date>/<name>.json.gz."""
    day = path.parent.name
    d = re.sub(r"\D", "", path.name.replace(".json.gz", ""))
    if len(d) == 10 and d.startswith("17"):
        return pd.to_datetime(int(d), unit="s", utc=True)
    if len(d) >= 14:
        return pd.to_datetime(d[:14], format="%Y%m%d%H%M%S", utc=True)
    if len(d) >= 6:
        return pd.to_datetime(f"{day} {d[:2]}:{d[2:4]}:{d[4:6]}", utc=True)
    raise ValueError(f"cannot parse timestamp from {path}")

if RAW_STATUS is not None:
    groups = [(d.name, sorted(d.glob("*.json.gz")))
              for d in sorted(p for p in RAW_STATUS.iterdir() if p.is_dir())]
    print(f"source: {RAW_STATUS}  |  {len(groups)} days")
elif FULL_DAY is not None:
    day = FULL_DAY.name.replace("full_day_", "")
    files = sorted(FULL_DAY.glob("*.json.gz"))
    groups = [(day, files)]
    print(f"source: {FULL_DAY}  |  {len(files)} captures of {day}")
    print(FULL_DAY_NOTE)
else:
    groups = {}
    for f in SAMPLE_STATUS:
        d = re.sub(r"\D", "", f.name)[:8]
        groups.setdefault(f"{d[:4]}-{d[4:6]}-{d[6:8]}", []).append(f)
    groups = sorted(groups.items())
    print(f"source: raw_sample/  |  {len(SAMPLE_STATUS)} captures")
    print(SAMPLE_NOTE)

total, skipped = 0, []
for day, day_files in groups:
    rows = []
    for f in day_files:
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                pay = json.load(fh)
            fetched = ts_from(f)
            feed_upd = pay.get("lastUpdatedOther") or pay.get("last_updated")
            for s in pay["data"]["stations"]:
                r = {c: s.get(c) for c in COLS}
                types = {k: v for d in (s.get("num_bikes_available_types") or [])
                         for k, v in d.items()}
                r["stationCode"] = s.get("stationCode")
                r["mechanical"] = types.get("mechanical")
                r["ebike"] = types.get("ebike")
                r["fetched_at"] = fetched
                r["feed_last_updated"] = feed_upd
                r["source_file"] = f.name
                rows.append(r)
        except Exception as e:
            skipped.append((str(f), str(e)))
    if not rows:
        continue
    df = pd.DataFrame(rows)
    df["last_reported"] = pd.to_datetime(df["last_reported"], unit="s", utc=True)
    df["lr_age_min"] = (df["fetched_at"] - df["last_reported"]).dt.total_seconds() / 60
    for c in ("mechanical", "ebike"):
        df[c] = df[c].astype("Int64")
    (OUT / f"date={day}").mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT / f"date={day}" / "part-0.parquet", index=False, compression="snappy")
    total += len(df)
    print(f"{day}  {df['fetched_at'].nunique():>3} fetches  {len(df):>8} rows  "
          f"median last_reported age {df['lr_age_min'].median():.1f} min")

print(f"\nTOTAL {total} rows | skipped {len(skipped)} files")
for f, e in skipped[:10]:
    print("  SKIP", f, e)
