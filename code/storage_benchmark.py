"""
First storage comparison on the cleaned table: relational (SQLite) vs date-partitioned
Parquet queried with DuckDB. Same rows, same three queries, same machine.

The three queries are the ones the analysis will actually run:
  Q1 share of time each station cannot rent        (full scan, group by station)
  Q2 one station's timeline over the period        (selective, one station)
  Q3 the whole network at one capture              (selective, one moment: what the
                                                    "viable alternative" rule needs)

Input : data/clean/station_status_clean/   (from clean.py)
Output: data/clean/storage_benchmark.csv, and a throwaway SQLite file in data/clean/

Timings depend on the machine: compare the two columns of one run, not runs on different
laptops. Each query runs 5 times; we keep the median.
Needs duckdb (pip install duckdb). Any working directory.
"""
import os, sqlite3, statistics, sys, time
import pandas as pd
from _paths import DATA_OUT

try:
    import duckdb
except ImportError:
    sys.exit("pip install duckdb")

SRC = DATA_OUT / "clean" / "station_status_clean"
DB = DATA_OUT / "clean" / "benchmark.sqlite"
if not SRC.is_dir():
    sys.exit(f"{SRC} not found: run clean.py first")

def folder_mb(p):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1024**2

def timed(fn, n=5):
    ts = []
    for _ in range(n):
        t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
    return round(statistics.median(ts) * 1000, 1)

df = pd.read_parquet(SRC)
df["fetched_at"] = df["fetched_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
df["last_reported"] = df["last_reported"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
station = int(df["station_id"].iloc[0])
moment = df["fetched_at"].iloc[len(df) // 2]
print(f"{len(df):,} rows")

# --- relational: one table, primary key + index on time ---------------------------
if DB.exists():
    DB.unlink()
t = time.perf_counter()
con = sqlite3.connect(DB)
con.execute("""CREATE TABLE status (
    station_id INTEGER, fetched_at TEXT, num_bikes_available INTEGER,
    num_docks_available INTEGER, can_rent INTEGER, can_return INTEGER, state TEXT,
    in_panel INTEGER, PRIMARY KEY (station_id, fetched_at))""")
cols = ["station_id", "fetched_at", "num_bikes_available", "num_docks_available",
        "can_rent", "can_return", "state", "in_panel"]
con.executemany("INSERT INTO status VALUES (?,?,?,?,?,?,?,?)",
                df[cols].astype({"can_rent": int, "can_return": int, "in_panel": int})
                .itertuples(index=False, name=None))
con.execute("CREATE INDEX idx_time ON status (fetched_at)")
con.commit()
load_sql = round(time.perf_counter() - t, 2)

q_sql = {
    "Q1": "SELECT station_id, AVG(1 - can_rent) FROM status WHERE in_panel GROUP BY station_id",
    "Q2": f"SELECT * FROM status WHERE station_id = {station} ORDER BY fetched_at",
    "Q3": f"SELECT * FROM status WHERE fetched_at = '{moment}'",
}
res_sql = {k: timed(lambda q=q: con.execute(q).fetchall()) for k, q in q_sql.items()}
con.close()

# --- columnar: Parquet partitioned by date, read in place by DuckDB ------------------
pq = f"'{SRC.as_posix()}/*/*.parquet'"
dk = duckdb.connect()
q_dk = {
    "Q1": f"SELECT station_id, AVG(1 - can_rent::INT) FROM read_parquet({pq}) "
          "WHERE in_panel GROUP BY station_id",
    "Q2": f"SELECT * FROM read_parquet({pq}) WHERE station_id = {station} ORDER BY fetched_at",
    "Q3": f"SELECT * FROM read_parquet({pq}) WHERE fetched_at = TIMESTAMPTZ '{moment}'",
}
res_dk = {k: timed(lambda q=q: dk.execute(q).fetchnumpy()) for k, q in q_dk.items()}

out = pd.DataFrame([
    {"measure": "size on disk (MB)", "sqlite": round(DB.stat().st_size / 1024**2, 1),
     "parquet_duckdb": round(folder_mb(SRC), 1)},
    {"measure": "load / write time (s)", "sqlite": load_sql,
     "parquet_duckdb": "written by clean.py"},
    *[{"measure": f"{k} median time (ms)", "sqlite": res_sql[k], "parquet_duckdb": res_dk[k]}
      for k in q_sql],
])
out.to_csv(DATA_OUT / "clean" / "storage_benchmark.csv", index=False)
print(out.to_string(index=False))
print("\nSQLite holds 8 columns, the Parquet files all 29: the size gap is a lower bound.")
DB.unlink()
