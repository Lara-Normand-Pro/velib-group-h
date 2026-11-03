"""
Two checks behind the decision to keep every capture (peer review round 1, Group I).

A. What last_reported really is.
   If last_reported were the moment the counts were measured, the counts could only change
   when last_reported changes. We measure how often they change while it stays the same,
   and how often each of the two renews.

B. What a coarser sampling would have lost.
   Keep one capture every 15, 30 or 60 minutes, or one row per (station, last_reported)
   as we had planned, and recount the episodes with exactly the same rule. If the 5-minute
   captures carried nothing new, the counts would hardly move.

Input : data/clean/station_status_clean/   (from clean.py)
Output: data/clean/last_reported_check.csv, data/clean/sampling_sensitivity.csv

Any working directory.
"""
import numpy as np
import pandas as pd
from _paths import DATA_OUT
from episodes import find_episodes, load_panel

df = load_panel()
out_dir = DATA_OUT / "clean"
print(f"panel: {len(df):,} rows, {df['station_id'].nunique()} stations, "
      f"{df['fetched_at'].dt.date.nunique()} day(s)\n")

# ---------------------------------------------------------------- A. last_reported
g = df.groupby("station_id")
prev_ok = g["fetched_at"].diff().dt.total_seconds().between(0, 7.5 * 60)  # consecutive pair
lr_same = (g["last_reported"].diff() == pd.Timedelta(0)) & prev_ok
lr_new = (g["last_reported"].diff() != pd.Timedelta(0)) & prev_ok
cnt_chg = ((g["num_bikes_available"].diff() != 0) |
           (g["num_docks_available"].diff() != 0)) & prev_ok
hours = df["fetched_at"].dt.hour
night = hours.isin([0, 1, 2, 3, 4])                     # 02:00 to 06:59 Paris time (CEST)
day = hours.between(6, 19)
def per_station_hour(event, mask):
    n_hours = df.loc[mask, "fetched_at"].dt.floor("h").nunique()
    return round((event & mask).sum() / df["station_id"].nunique() / max(n_hours, 1), 2)

A = pd.DataFrame([
    ("pairs with unchanged last_reported where the counts changed (%)",
     round(100 * (cnt_chg & lr_same).sum() / lr_same.sum(), 1)),
    ("count changes that happen under an unchanged last_reported (%)",
     round(100 * (cnt_chg & lr_same).sum() / cnt_chg.sum(), 1)),
    ("rows repeating an earlier (station_id, last_reported) pair (%)",
     round(100 * df.duplicated(["station_id", "last_reported"]).mean(), 1)),
    ("last_reported renewals per station per hour, night (00-05 UTC)",
     per_station_hour(lr_new, night)),
    ("last_reported renewals per station per hour, day (06-19 UTC)",
     per_station_hour(lr_new, day)),
    ("count changes per station per hour, night (00-05 UTC)", per_station_hour(cnt_chg, night)),
    ("count changes per station per hour, day (06-19 UTC)", per_station_hour(cnt_chg, day)),
    ("median age of last_reported when read (min)", round(df["lr_age_min"].median(), 1)),
], columns=["measure", "value"])
A.to_csv(out_dir / "last_reported_check.csv", index=False)
print("A. last_reported")
print(A.to_string(index=False), "\n")

# ---------------------------------------------------------------- B. coarser sampling
def runs_seen(full, flag, kept):
    """Share of 5-min episodes containing at least one kept, failing row."""
    sid = full["station_id"].to_numpy()
    t = full["fetched_at"].to_numpy()
    f = flag.to_numpy()
    gap = np.diff(t).astype("timedelta64[s]").astype(float) / 60
    cont = np.r_[False, (sid[1:] == sid[:-1]) & (gap < 7.5)]
    run = np.cumsum(f & ~(cont & np.r_[False, f[:-1]]))
    sizes = pd.Series(run[f]).value_counts()
    episodes = set(sizes[sizes >= 2].index)
    seen = set(run[f & kept.to_numpy()]) & episodes
    return len(seen) / max(len(episodes), 1)

minute = df["fetched_at"].dt.minute + 60 * df["fetched_at"].dt.hour
first_lr = ~df.duplicated(["station_id", "last_reported"])
variants = [("every 5 min (all captures)", pd.Series(True, index=df.index), 5)]
variants += [(f"every {k} min", minute % k == 0, k) for k in (15, 30, 60)]
variants += [("one row per (station, last_reported)", first_lr, None)]

rows = []
for side, flag in (("no_rent", ~df["can_rent"]), ("no_return", ~df["can_return"])):
    base = None
    for name, kept, step in variants:
        sub = df[kept]
        f_sub = flag[kept]
        # dedup on last_reported has no fixed step: any two kept rows of a station are
        # "consecutive", which is what the original plan implied
        ep = find_episodes(sub, f_sub, step_min=step or 1e9)
        n = len(ep)
        base = base or n
        rows.append({
            "side": side, "sampling": name, "rows_kept": len(sub),
            "episodes": n, "episodes_vs_5min_%": round(100 * n / base, 1),
            "5min_episodes_seen_at_all_%": round(100 * runs_seen(df, flag, kept), 1),
            "share_of_rows_failing_%": round(100 * f_sub.mean(), 2),
        })
B = pd.DataFrame(rows)
B.to_csv(out_dir / "sampling_sensitivity.csv", index=False)
print("B. coarser sampling, same episode rule (>= 2 consecutive kept captures)")
print(B.to_string(index=False))
print(f"\nwritten to {out_dir}")
