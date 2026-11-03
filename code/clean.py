"""
Cleaning: from the flat status table to a table fit for the question.

Input : data/station_status/date=*/part-0.parquet   (from build_snapshot.py)
        the station lists (full archive: raw/info/<date>/; package: raw_sample/info_*
        and data/station_information_*)
Output: data/clean/station_status_clean/date=*/part-0.parquet
        data/clean/stations_daily.csv      one row per station per day
        data/clean/cleaning_log.csv        what each step did, in numbers

Principle: we flag, we do not alter. Counts are never corrected or imputed, because the
feed is our only source and we cannot know the true value. Rows are only removed when they
carry no usable information (an unusable capture, an exact duplicate). Every other problem
becomes a flag column, and the analysis decides through one column, `in_panel`.

What we deliberately do NOT do any more: deduplicate on (station_id, last_reported).
last_reported renews about once an hour while the counts change between our 5-minute
captures, so that deduplication would keep about one row per station per hour and lose
most short episodes (see sampling_test.py).

Runs on the submitted package (one day) and on the full archive. Any working directory.
"""
import gzip, json, re, sys
import numpy as np
import pandas as pd
from _paths import DATA_OUT, RAW_INFO, INFO_FILES

IN = DATA_OUT / "station_status"
OUT = DATA_OUT / "clean"

# --- thresholds, all justified in docs/data_quality_and_cleaning ---------------------
MIN_STATIONS = 1400     # a capture with fewer stations is truncated: dropped
SILENT_MIN = 180        # last_reported older than 3 h = three missed hourly heartbeats
FROZEN_H = 12           # counts unchanged 12 h while in service; normal max on 21.09 is ~6 h
TEMP_SHARE = 0.5        # in the station list on fewer than half the days = temporary
EVENT_CAPACITY = 100    # regular stations have at most 78 docks; 100+ are event stations
CAPTURE_GAP_MIN = 7.5   # two captures more than 7.5 min apart are not consecutive

if not IN.is_dir() or not any(IN.glob("date=*/part-0.parquet")):
    sys.exit(f"no Parquet tables in {IN}: run build_snapshot.py first")
OUT.mkdir(parents=True, exist_ok=True)
log = []
def step(name, rule, before, after=None, flagged=None):
    log.append({"step": name, "rule": rule, "rows_before": before,
                "rows_after": before if after is None else after,
                "rows_flagged": flagged if flagged is not None else ""})
    extra = f", {flagged} rows flagged" if flagged is not None else ""
    print(f"  {name:<22} {before:>9} -> {log[-1]['rows_after']:>9}{extra}")

# --- 0. load ------------------------------------------------------------------------
df = pd.concat([pd.read_parquet(p).assign(date=p.parent.name[5:])
                for p in sorted(IN.glob("date=*/part-0.parquet"))], ignore_index=True)
days = sorted(df["date"].unique())
print(f"loaded {len(df):,} rows, {df['station_id'].nunique()} stations, days {days[0]} to {days[-1]}\n")

# --- 1. unusable captures -----------------------------------------------------------
n0 = len(df)
per_cap = df.groupby("fetched_at")["station_id"].transform("size")
df = df[per_cap >= MIN_STATIONS]
step("truncated_captures", f"drop captures with < {MIN_STATIONS} stations", n0, len(df))

n0 = len(df)
df = df.drop_duplicates(["station_id", "fetched_at"])
step("exact_duplicates", "drop repeated (station_id, fetched_at), e.g. after merging VMs",
     n0, len(df))

n0 = len(df)
df["partial_capture"] = df["stationCode"].isna()
step("partial_captures", "keep, flag: counts present, stationCode / bike types missing",
     n0, flagged=int(df["partial_capture"].sum()))

# --- 2. same-day station list -------------------------------------------------------
def load_list(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        st = json.load(fh)["data"]["stations"]
    return pd.DataFrame(st)[["station_id", "stationCode", "name", "lat", "lon", "capacity"]]

def list_date(path):
    d = re.sub(r"\D", "", path.name)[:8]
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"

lists = {}
if RAW_INFO is not None:          # full archive: every hourly list of the day
    for day in days:
        files = sorted((RAW_INFO / day).glob("*.json.gz"))
        if files:
            frames = [load_list(f) for f in files]
            members = set().union(*(set(f["station_id"]) for f in frames))
            lists[day] = (frames[-1], members, f"{len(files)} lists of {day}")
    print(f"station lists: hourly archive, {len(lists)} days")
else:                             # package: closest available list, earlier one first
    avail = sorted(((list_date(p), p) for p in INFO_FILES), key=lambda x: x[0])
    for day in days:
        before = [a for a in avail if a[0] <= day]
        d, p = (before[-1] if before else avail[0])
        frame = load_list(p)
        lists[day] = (frame, set(frame["station_id"]), p.name)
    print("station lists: package mode, closest list per day:",
          {k: v[2] for k, v in lists.items()})

parts = []
for day, (frame, members, src) in lists.items():
    sub = df[df["date"] == day].merge(
        frame[["station_id", "name", "lat", "lon", "capacity"]], on="station_id", how="left")
    sub["in_station_list"] = sub["station_id"].isin(members)
    parts.append(sub)
df = pd.concat(parts, ignore_index=True)
n0 = len(df)
step("not_in_station_list", "flag rows whose station is absent from that day's list",
     n0, flagged=int((~df["in_station_list"]).sum()))

# temporary stations: present in the station list on fewer than half the days
listed = pd.DataFrame([(d, s) for d, (_, m, _) in lists.items() for s in m],
                      columns=["date", "station_id"])
days_listed = listed.groupby("station_id")["date"].nunique()
temporary = set(days_listed[days_listed < TEMP_SHARE * len(lists)].index)
df["temporary"] = df["station_id"].isin(temporary)
step("temporary_stations", f"flag stations listed on < {TEMP_SHARE:.0%} of days "
     f"({len(temporary)} stations)", len(df), flagged=int(df["temporary"].sum()))
if len(lists) < 2:
    print("    note: one day only, so no station can be classed as temporary here")

# event stations: Concorde, Invalides (~410 docks, open 26.09 only), Tour de France,
# Hippodrome. They are listed for weeks, so presence alone does not catch them.
df["event_station"] = df["capacity"] >= EVENT_CAPACITY
step("event_stations", f"flag capacity >= {EVENT_CAPACITY} "
     f"({df.loc[df['event_station'], 'station_id'].nunique()} stations)", len(df),
     flagged=int(df["event_station"].sum()))

# --- 3. capacity --------------------------------------------------------------------
df["capacity"] = df["capacity"].where(df["capacity"] > 0)          # 0 means unknown
df["docks_unavailable"] = df["capacity"] - df["num_bikes_available"] - df["num_docks_available"]
df["capacity_conflict"] = df["docks_unavailable"] < 0
step("capacity_missing", "capacity 0 or absent -> NA, flag", len(df),
     flagged=int(df["capacity"].isna().sum()))
step("capacity_conflict", "flag bikes + docks > capacity (counts kept as published)",
     len(df), flagged=int(df["capacity_conflict"].sum()))

# --- 4. service state and the two sides of the question ------------------------------
inst = df["is_installed"] == 1
df["out_of_service"] = ~inst | ((df["is_renting"] == 0) & (df["is_returning"] == 0))
df["can_rent"] = inst & (df["is_renting"] == 1) & (df["num_bikes_available"] > 0)
df["can_return"] = inst & (df["is_returning"] == 1) & (df["num_docks_available"] > 0)
df["state"] = np.select(
    [df["out_of_service"], df["num_bikes_available"] == 0, df["num_docks_available"] == 0],
    ["out_of_service", "empty", "full"], "ok")

# --- 5. silent and frozen stations --------------------------------------------------
df["silent"] = df["lr_age_min"] > SILENT_MIN
step("silent", f"flag last_reported older than {SILENT_MIN} min", len(df),
     flagged=int(df["silent"].sum()))

df = df.sort_values(["station_id", "fetched_at"]).reset_index(drop=True)
g = df.groupby("station_id")
gap = g["fetched_at"].diff().dt.total_seconds() / 60
changed = (g["num_bikes_available"].diff() != 0) | (g["num_docks_available"].diff() != 0) \
          | (gap > CAPTURE_GAP_MIN)
run_id = changed.groupby(df["station_id"]).cumsum()
grp = df.groupby(["station_id", run_id])["fetched_at"]
run_h = (grp.transform("max") - grp.transform("min")).dt.total_seconds() / 3600
df["frozen"] = (run_h >= FROZEN_H) & ~df["out_of_service"]
step("frozen", f"flag in-service rows whose counts stay identical >= {FROZEN_H} h",
     len(df), flagged=int(df["frozen"].sum()))

# --- 6. the analysis panel ----------------------------------------------------------
df["in_panel"] = (df["in_station_list"] & ~df["temporary"] & ~df["event_station"]
                  & ~df["frozen"])
step("in_panel", "rows SELECTED for analysis: in same-day list, not temporary, "
     "not event station, not frozen",
     len(df),
     flagged=int(df["in_panel"].sum()))

# --- write --------------------------------------------------------------------------
keep = ["fetched_at", "station_id", "stationCode", "name", "lat", "lon", "capacity",
        "num_bikes_available", "mechanical", "ebike", "num_docks_available",
        "docks_unavailable", "is_installed", "is_renting", "is_returning",
        "state", "out_of_service", "can_rent", "can_return",
        "last_reported", "lr_age_min",
        "partial_capture", "in_station_list", "temporary", "event_station", "capacity_conflict",
        "silent", "frozen", "in_panel"]
for day, sub in df.groupby("date"):
    (OUT / "station_status_clean" / f"date={day}").mkdir(parents=True, exist_ok=True)
    sub[keep].to_parquet(OUT / "station_status_clean" / f"date={day}" / "part-0.parquet",
                         index=False, compression="snappy")

df["is_empty"] = df["state"] == "empty"
df["is_full"] = df["state"] == "full"
daily = df.groupby(["date", "station_id"]).agg(
    name=("name", "first"), capacity=("capacity", "first"),
    captures=("fetched_at", "size"), in_station_list=("in_station_list", "first"),
    temporary=("temporary", "first"), event_station=("event_station", "first"),
    share_out_of_service=("out_of_service", "mean"),
    share_empty=("is_empty", "mean"), share_full=("is_full", "mean"),
    share_silent=("silent", "mean"), share_frozen=("frozen", "mean"),
    share_capacity_conflict=("capacity_conflict", "mean")).round(4)
daily.to_csv(OUT / "stations_daily.csv")
pd.DataFrame(log).to_csv(OUT / "cleaning_log.csv", index=False)

print("\nrows by state:", df["state"].value_counts().to_dict())
print(f"stations frozen at some point: {df.loc[df['frozen'], 'station_id'].nunique()}, "
      f"silent at some point: {df.loc[df['silent'], 'station_id'].nunique()}")
print(f"\nwritten to {OUT}")
