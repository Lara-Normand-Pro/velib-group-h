"""
Compare the two collectors (VM1 and VM2) to measure our own reliability.

Usage:  python code/compare_vms.py <vm1_velib_folder> <vm2_velib_folder>
        each folder is a copy of ~/velib from one VM (http_log.csv + status/<date>/...)

What it tells us:
  1. captures per day on each machine, and on the union of both (what merging recovers)
  2. timestamps caught by one machine only (the gaps the other one fills)
  3. for captures taken in the same 5-minute slot by both, whether they read the same
     counts: if not, the feed changed between the two requests, which bounds how
     "instantaneous" a capture is

Output: data/vm_comparison.csv (per day). Not runnable on the package: the VM archives
are not included. Any working directory.
"""
import gzip, json, sys
from pathlib import Path
import pandas as pd
from _paths import DATA_OUT

if len(sys.argv) != 3:
    sys.exit(__doc__)
vm = {name: Path(p) for name, p in zip(("vm1", "vm2"), sys.argv[1:])}

def slots(root):
    """5-minute slot -> file, from the files actually archived (not the log)."""
    out = {}
    for f in (root / "status").glob("*/*.json.gz"):
        t = pd.to_datetime(f.name[:16], format="%Y%m%dT%H%M%SZ", utc=True)
        out[t.floor("5min")] = f
    return out

s = {k: slots(v) for k, v in vm.items()}
allslots = sorted(set(s["vm1"]) | set(s["vm2"]))
tab = pd.DataFrame({"slot": allslots})
tab["vm1"] = tab["slot"].isin(s["vm1"])
tab["vm2"] = tab["slot"].isin(s["vm2"])
tab["date"] = tab["slot"].dt.date

def counts(f):
    with gzip.open(f, "rt", encoding="utf-8") as fh:
        st = json.load(fh)["data"]["stations"]
    return {x["station_id"]: (x["num_bikes_available"], x["num_docks_available"]) for x in st}

both = tab[tab["vm1"] & tab["vm2"]]
step = max(1, len(both) // 300)                 # a sample of ~300 shared slots is enough
same = []
for slot in both["slot"].iloc[::step]:
    a, b = counts(s["vm1"][slot]), counts(s["vm2"][slot])
    common = set(a) & set(b)
    same.append({"slot": slot, "stations_identical_%":
                 100 * sum(a[k] == b[k] for k in common) / max(len(common), 1)})
same = pd.DataFrame(same)

per_day = tab.groupby("date").agg(vm1=("vm1", "sum"), vm2=("vm2", "sum"),
                                  union=("slot", "size"),
                                  only_vm1=("vm1", lambda x: int((x & ~tab.loc[x.index, "vm2"]).sum())),
                                  only_vm2=("vm2", lambda x: int((x & ~tab.loc[x.index, "vm1"]).sum())))
per_day.to_csv(DATA_OUT / "vm_comparison.csv")
print(per_day.to_string(), "\n")
if len(same):
    print(f"same-slot captures compared: {len(same)}; stations with identical counts: "
          f"median {same['stations_identical_%'].median():.1f}%, "
          f"min {same['stations_identical_%'].min():.1f}%")
print(f"\nwritten to {DATA_OUT / 'vm_comparison.csv'}")
