"""
Run the whole workflow in order, from raw captures to cleaned table and checks.

    python code/run_all.py              # everything that runs on this package
    python code/run_all.py --no-bench   # skip the storage benchmark (needs duckdb)

Stops at the first script that fails. Any working directory.
"""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [
    ("coverage.py",          "collection coverage, from the HTTP log"),
    ("validate.py",          "content check of every raw capture"),
    ("build_snapshot.py",    "raw captures -> one Parquet file per day"),
    ("daily_json.py",        "raw captures -> one NDJSON file per day"),
    ("neighbours.py",        "station distances, 200 / 300 / 500 m"),
    ("clean.py",             "cleaning: flags, same-day station list, panel"),
    ("episodes.py",          "failure episodes, renting and returning sides"),
    ("sampling_test.py",     "last_reported check, 5 vs 15 / 30 / 60 min"),
    ("storage_benchmark.py", "SQLite vs Parquet + DuckDB"),
]
if "--no-bench" in sys.argv:
    STEPS = STEPS[:-1]

for script, what in STEPS:
    print(f"\n{'=' * 78}\n{script}: {what}\n{'=' * 78}", flush=True)
    r = subprocess.run([sys.executable, str(HERE / script)])
    if r.returncode != 0:
        sys.exit(f"\nstopped: {script} failed")
print("\nall steps done")
