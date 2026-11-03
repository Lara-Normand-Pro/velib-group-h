"""
Nearest-neighbour distances between stations, and sensitivity of the isolation
threshold (200 / 300 / 500 m).

Input : data/station_information_*.json.gz
Output: data/station_neighbours.csv, data/threshold_sensitivity.csv

Runs on the submitted package. Works from any working directory.
"""
import gzip, json, sys
import numpy as np
import pandas as pd
from _paths import STATION_INFO, DATA_OUT

if STATION_INFO is None:
    sys.exit("station_information file not found")
print(f"source: {STATION_INFO}")
DATA_OUT.mkdir(parents=True, exist_ok=True)

op = gzip.open if str(STATION_INFO).endswith(".gz") else open
with op(STATION_INFO, "rt", encoding="utf-8") as fh:
    payload = json.load(fh)

st = pd.DataFrame(payload["data"]["stations"])[
    ["station_id", "stationCode", "name", "lat", "lon", "capacity"]
]
print(f"{len(st)} stations")

# pairwise distances, equirectangular projection (accurate at this scale)
R = 6371000.0
lat = np.radians(st["lat"].to_numpy())
lon = np.radians(st["lon"].to_numpy())
x = R * lon * np.cos(lat.mean())
y = R * lat
d = np.sqrt((x[:, None] - x[None, :])**2 + (y[:, None] - y[None, :])**2)
np.fill_diagonal(d, np.inf)

st["nearest_m"] = d.min(axis=1).round(1)
st["nearest_station_id"] = st["station_id"].to_numpy()[d.argmin(axis=1)]
for t in (200, 300, 500):
    st[f"n_within_{t}m"] = (d <= t).sum(axis=1)

st.to_csv(DATA_OUT / "station_neighbours.csv", index=False)

rows = []
for t in (200, 300, 500):
    has = st[f"n_within_{t}m"] > 0
    rows.append({
        "threshold_m": t,
        "with_neighbour": int(has.sum()),
        "isolated": int((~has).sum()),
        "share_with_neighbour_%": round(has.mean() * 100, 1),
        "share_isolated_%": round((~has).mean() * 100, 1),
        "mean_neighbours": round(st[f"n_within_{t}m"].mean(), 2),
    })
sens = pd.DataFrame(rows)
sens.to_csv(DATA_OUT / "threshold_sensitivity.csv", index=False)

print("\n--- threshold sensitivity ---")
print(sens.to_string(index=False))
print("\n--- nearest-neighbour distance (m) ---")
print(st["nearest_m"].describe(percentiles=[.25, .5, .75, .9, .95]).round(1).to_string())
print("\n--- 10 most isolated stations ---")
print(st.nlargest(10, "nearest_m")[["stationCode", "name", "nearest_m"]].to_string(index=False))
print(f"\nwritten to {DATA_OUT}")
