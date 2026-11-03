"""
Coverage of the collection, computed from the collector's own HTTP log.

Input : raw_sample/http_log.csv   (no header)
        collector v1 lines: timestamp,feed,http_code
        collector v2 lines: timestamp,feed,http_code,bytes,n_stations,check
Output: data/coverage_status.csv, data/coverage_info.csv
        data/failed_attempts.csv  (only if there are any)

Runs on the submitted package. Works from any working directory.
"""
import sys
import pandas as pd
from _paths import HTTP_LOG, DATA_OUT

if HTTP_LOG is None:
    sys.exit("http_log.csv not found")
print(f"log: {HTTP_LOG}")
DATA_OUT.mkdir(parents=True, exist_ok=True)

# v1 lines have 3 fields, v2 lines 6: the missing fields are read as empty
log = pd.read_csv(HTTP_LOG, header=None,
                  names=["ts", "feed", "http_status", "bytes", "n_stations", "check"])
log["ts"] = pd.to_datetime(log["ts"], format="%Y%m%dT%H%M%SZ", utc=True)
log["date"] = log["ts"].dt.date

print(f"log rows: {len(log)} | {log['ts'].min()} -> {log['ts'].max()}\n")
print("status codes:\n", log["http_status"].value_counts(), "\n")

for feed, expected in [("status", 288), ("info", 24)]:
    sub = log[log["feed"] == feed]
    ok = sub[sub["http_status"] == 200]
    cov = ok.groupby("date").size().rename("captured").to_frame()
    cov["attempted"] = sub.groupby("date").size()
    cov["expected"] = expected
    cov["coverage_%"] = (cov["captured"] / expected * 100).round(1)
    # content check: only lines written by collector v2 carry one. For older lines,
    # validate.py checks the archived files themselves.
    if sub["check"].notna().any():
        for c in ("ok", "partial", "bad"):
            cov[f"check_{c}"] = sub[sub["check"] == c].groupby("date").size()
        cov = cov.fillna(0).astype({c: int for c in cov.columns if c != "coverage_%"})
    cov.to_csv(DATA_OUT / f"coverage_{feed}.csv")
    print(f"--- {feed} ---")
    print(cov.to_string(), "\n")

fails = log[log["http_status"] != 200]
if len(fails):
    fails.to_csv(DATA_OUT / "failed_attempts.csv", index=False)
    print(f"FAILED ATTEMPTS: {len(fails)}")
    print(fails.to_string())
else:
    print("FAILED ATTEMPTS: none - every logged attempt returned 200")

s = log[(log["feed"] == "status") & (log["http_status"] == 200)].sort_values("ts")
gap = s["ts"].diff().dt.total_seconds() / 60
big = s.loc[gap > 10].assign(gap_min=gap[gap > 10].round(1))
print(f"\nGAPS > 10 min: {len(big)}")
if len(big):
    print(big[["ts", "gap_min"]].to_string(index=False))
