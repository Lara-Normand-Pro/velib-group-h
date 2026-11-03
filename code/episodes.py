"""
Failure episodes, built on every capture (no deduplication on last_reported).

Two sides, kept apart because a user renting and a user returning need different things:
  no_rent    the station cannot give a bike: not installed, not renting, or 0 bikes
  no_return  the station cannot take a bike: not installed, not returning, or 0 free docks

An episode is a run of at least MIN_CAPTURES consecutive captures on the same side.
Consecutive means less than 1.5 sampling intervals apart, so a missing capture ends the
run instead of being bridged. Only rows with in_panel = True are used.

Input : data/clean/station_status_clean/   (from clean.py)
Output: data/clean/episodes.parquet
        one row: station_id, side, cause (state at the first capture), start, end,
        n_captures, duration_min

duration_min = n_captures x 5 min: the time the station was SEEN failing. The true episode
can be up to one interval longer at each end.

Any working directory. sampling_test.py imports find_episodes() from here.
"""
import sys
import numpy as np
import pandas as pd
from _paths import DATA_OUT

MIN_CAPTURES = 2
STEP_MIN = 5

def find_episodes(df, flag, step_min=STEP_MIN, min_captures=MIN_CAPTURES):
    """df sorted by station_id, fetched_at. flag: boolean Series aligned with df."""
    sid = df["station_id"].to_numpy()
    t = df["fetched_at"].to_numpy()
    f = flag.to_numpy()
    gap = np.diff(t).astype("timedelta64[s]").astype(float) / 60
    cont = np.r_[False, (sid[1:] == sid[:-1]) & (gap < 1.5 * step_min)]
    # a new run starts where the flag is on and the previous row is not a continuation of it
    start = f & ~(cont & np.r_[False, f[:-1]])
    run = np.cumsum(start)
    sel = f
    ep = pd.DataFrame({"run": run[sel], "station_id": sid[sel], "t": t[sel],
                       "idx": np.flatnonzero(sel)})
    out = ep.groupby("run").agg(station_id=("station_id", "first"), start=("t", "min"),
                                end=("t", "max"), n_captures=("t", "size"),
                                first_idx=("idx", "first"))
    out = out[out["n_captures"] >= min_captures].reset_index(drop=True)
    out["duration_min"] = out["n_captures"] * step_min
    return out

def load_panel():
    src = DATA_OUT / "clean" / "station_status_clean"
    if not src.is_dir():
        sys.exit(f"{src} not found: run clean.py first")
    df = pd.read_parquet(src)
    df = df[df["in_panel"]].sort_values(["station_id", "fetched_at"]).reset_index(drop=True)
    return df

if __name__ == "__main__":
    df = load_panel()
    print(f"panel: {len(df):,} rows, {df['station_id'].nunique()} stations\n")
    sides = {"no_rent": ~df["can_rent"], "no_return": ~df["can_return"]}
    out = []
    for side, flag in sides.items():
        ep = find_episodes(df, flag)
        first = df.loc[ep["first_idx"]]
        ep["cause"] = np.where(first["out_of_service"].to_numpy(), "out_of_service",
                               "empty" if side == "no_rent" else "full")
        ep["side"] = side
        out.append(ep.drop(columns="first_idx"))
    ep = pd.concat(out, ignore_index=True)[
        ["station_id", "side", "cause", "start", "end", "n_captures", "duration_min"]]
    ep.to_parquet(DATA_OUT / "clean" / "episodes.parquet", index=False)

    summary = ep.groupby(["side", "cause"]).agg(
        episodes=("duration_min", "size"), stations=("station_id", "nunique"),
        median_min=("duration_min", "median"),
        share_under_30min=("duration_min", lambda d: round((d < 30).mean(), 3)))
    print(summary.to_string())
    print(f"\n{len(ep):,} episodes written to {DATA_OUT / 'clean' / 'episodes.parquet'}")
