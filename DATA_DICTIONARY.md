# Data dictionary

Group H, Vélib' project, version of 03.11.2026. What every file in `data/` and `raw_sample/`
contains, and what every column means.

All timestamps are UTC. All distances are in metres, straight line. Figures are for 21.09, the
day of raw captures shipped in this package (the flat table in section 1 covers 10 days).

---

## 1. `station_status/date=YYYY-MM-DD/part-0.parquet`

The flat table: one row per station per capture, exactly as published. Nothing is dropped or
corrected here (that is section 2). Produced by `build_snapshot.py`.

**21.09:** 437,184 rows = 288 captures × 1,518 stations. Rebuilt from the raw captures in
`raw_sample/`, so anyone can check it.

**All 10 days (20.09 to 29.09):** 3,686,536 rows, one file per day, same columns. The nine days
other than 21.09 are the tables of our 29.09 submission, brought to the current column layout:
`lag_min` is renamed `lr_age_min` (same values), and `stationCode`, `mechanical` and `ebike` are
empty because the 29.09 version did not keep them. Their values are unchanged, and `source_file`
keeps the form `<date>/<file>` used by the collector's archive. Their raw files are not in this
package, so these nine days cannot be rebuilt here.

| Column | Type | Comes from | Meaning |
|---|---|---|---|
| `station_id` | integer | `station_id` | Identifies the station. Join key to the station list |
| `stationCode` | text | `stationCode` | Code shown on the station. Null in partial captures |
| `num_bikes_available` | integer | `num_bikes_available` | Bikes available to rent |
| `mechanical`, `ebike` | integer | `num_bikes_available_types` | The same bikes split by type. Null in partial captures |
| `num_docks_available` | integer | `num_docks_available` | Free docks |
| `is_installed` | 0 or 1 | `is_installed` | The station is physically deployed |
| `is_renting` | 0 or 1 | `is_renting` | The station allows rentals |
| `is_returning` | 0 or 1 | `is_returning` | The station accepts returns |
| `last_reported` | timestamp | `last_reported` (unix s) | An hourly signal from the station. **Not** the time of the counts, see below |
| `fetched_at` | timestamp | the file name | When **we** sent the request. The counts are as of this moment |
| `feed_last_updated` | integer | `lastUpdatedOther` | The feed's own update marker |
| `lr_age_min` | float | computed | `fetched_at` minus `last_reported`, in minutes. Called `lag_min` before 03.11 |
| `source_file` | text | computed | The raw file this row came from |

**What `last_reported` is.** We first read it as the moment the counts were measured. It is
not: it renews about once an hour, day and night alike, while the counts change between our
5-minute captures (on 21.09, 90.5% of count changes happen while `last_reported` is unchanged).
So `lr_age_min` is the age of an hourly signal (median 32 min), not a reporting delay, and rows
that repeat a `(station_id, last_reported)` pair (91.2%) are **not** duplicates. Never
deduplicate on that pair: it would erase about five episodes out of six. Details in
`docs/data_quality_and_cleaning.pdf` and `clean/last_reported_check.csv`.

## 2. `clean/station_status_clean/date=YYYY-MM-DD/part-0.parquet`

The cleaned table, produced by `clean.py`. Same rows as section 1 minus truncated captures and
exact duplicates (none on 21.09). Problems are flagged, never corrected. Use `in_panel` for
analysis.

| Column | Meaning |
|---|---|
| `fetched_at`, `station_id`, `stationCode`, counts, flags, `last_reported`, `lr_age_min` | As in section 1 |
| `name`, `lat`, `lon`, `capacity` | From the station list **of the same day**. Capacity 0 is stored as null |
| `docks_unavailable` | `capacity - bikes - free docks`: docks out of use. Negative = conflict |
| `state` | `out_of_service`, `empty`, `full` or `ok`, in that order of priority |
| `out_of_service` | Not installed, or neither renting nor returning |
| `can_rent` | Installed, renting, and at least 1 bike. What a user taking a bike needs |
| `can_return` | Installed, returning, and at least 1 free dock. What a user returning a bike needs |
| `partial_capture` | The capture lacked `stationCode` and bike types (21.09 22:50) |
| `in_station_list` | The station is in that day's station list |
| `temporary` | Listed on fewer than half the days of the period |
| `event_station` | Capacity of 100 docks or more (regular stations: 78 at most) |
| `capacity_conflict` | Bikes + free docks exceed capacity |
| `silent` | `last_reported` older than 180 min (three missed hourly signals) |
| `frozen` | In service, counts identical for 12 h or more |
| `in_panel` | **The analysis filter**: in the same-day list, not temporary, not event, not frozen |

**21.09:** `in_panel` keeps 435,910 rows (99.7%) and 1,515 stations.

## 3. `clean/episodes.parquet`

One row per failure episode, produced by `episodes.py` from the panel rows.

| Column | Meaning |
|---|---|
| `station_id` | The station |
| `side` | `no_rent` (cannot give a bike) or `no_return` (cannot take one) |
| `cause` | State at the first capture: `empty`, `full` or `out_of_service` |
| `start`, `end` | First and last capture of the episode |
| `n_captures` | Number of consecutive captures, at least 2 |
| `duration_min` | `n_captures × 5`: the time we saw it. The real episode can be up to 5 min longer at each end |

Consecutive means less than 7.5 minutes apart, so a missing capture ends an episode.
**21.09:** 2,630 `no_rent` and 1,667 `no_return` episodes.

## 4. `clean/stations_daily.csv`

One row per station per day: name, capacity, captures, `in_station_list`, `temporary`,
`event_station`, and the share of that day's captures that were out of service, empty, full,
silent, frozen or in capacity conflict.

## 5. `clean/cleaning_log.csv`

One row per cleaning step: the rule, rows before, rows after, rows flagged. For `in_panel`,
`rows_flagged` is the number of rows **selected**.

## 6. `clean/last_reported_check.csv` and `clean/sampling_sensitivity.csv`

From `sampling_test.py`. The first holds the diagnostics behind section 1's warning. The second
recounts episodes keeping one capture every 15, 30 or 60 minutes, or one row per
`last_reported`:

| Column | Meaning |
|---|---|
| `side`, `sampling` | Which side, which data kept |
| `rows_kept` | Rows left after thinning |
| `episodes`, `episodes_vs_5min_%` | Episodes found with the same rule, and as a share of the 5-min count |
| `5min_episodes_seen_at_all_%` | Share of 5-min episodes containing at least one kept row |
| `share_of_rows_failing_%` | Share of kept rows where the station fails on that side |

## 7. `clean/storage_benchmark.csv`

From `storage_benchmark.py`: size, load time and median time of three queries, SQLite vs
Parquet + DuckDB, on the same rows.

## 8. `capture_quality.csv`

From `validate.py`, one row per raw status capture: `file`, `fetched_at`, `bytes`,
`n_stations`, `missing_<field>` (stations lacking each field), `check` (`ok`, `partial`, `bad`)
and `problem`. **21.09 and samples:** 295 captures, 294 `ok`, 1 `partial`.

## 9. `station_information_20260929.json.gz`

The station list archived on 29.09, 1,519 stations: `station_id`, `stationCode`, `name`,
`lat`, `lon`, `capacity`, `station_opening_hours` (empty everywhere). Four stations have
capacity 0. `rental_methods` is present on 894 entries only and is not used. `clean.py` uses
the list of the same day as the status data whenever the hourly archive is available.

## 10. `status_2026-09-21.ndjson.gz` and `status_2026-09-21.csv`

21.09 in its original shape: one line per capture (288), each with `fetched_at`,
`lastUpdatedOther`, `ttl`, `n_stations` and the untouched `stations` list. The CSV is the same
day flattened for Excel (`ndjson_to_csv.py`), 437,184 rows, with the columns of section 1
(`last_reported_utc` added in readable form).

## 11. `coverage_status.csv` and `coverage_info.csv`

From `coverage.py`, per day: `captured` (requests returning 200), `attempted`, `expected` (288
or 24), `coverage_%`. Once the log holds collector v2 lines, also `check_ok`,
`check_partial`, `check_bad`. First and last days are partial because collection started on
20.09 in the evening and the snapshot was taken on 29.09 in the morning.

## 12. `station_neighbours.csv` and `threshold_sensitivity.csv`

From `neighbours.py`. Per station: `nearest_m`, `nearest_station_id`, and `n_within_200m`,
`n_within_300m`, `n_within_500m` (other stations within each radius). A station with
`n_within_300m` = 0 is isolated. The summary: 39.0% of stations have a neighbour within 200 m,
68.0% within 300 m, 88.5% within 500 m; median nearest distance 231 m.

## 13. `raw_sample/http_log.csv`

One line per request, no header, written by the collector whatever happens.

| Position | Example | Meaning |
|---|---|---|
| 1 | `20260920T210520Z` | When the request was sent |
| 2 | `status` or `info` | Which feed |
| 3 | `200` | HTTP code |
| 4 to 6 (v2 only) | `464177,1518,ok` | Bytes received, stations in the file, content check |

## How we define a failure

| Concept | Rule |
|---|---|
| Cannot rent | `can_rent` is false: not installed, not renting, or 0 bikes |
| Cannot return | `can_return` is false: not installed, not returning, or 0 free docks |
| Empty / full / out of service | The `state` column: why the station fails |
| Failure episode | At least two consecutive captures (less than 7.5 min apart) failing on the same side |
| Viable alternative | Another panel station within 300 m that does not fail **on the same side** at the **same capture** |
| Isolated station | No other panel station within 300 m |
| Comparison unit | The commune (IGN), summarised as Paris vs the rest of the network |

We never merge renting and returning into one "failure" count, and we never write "broken": the
feed cannot tell a broken station from one that stopped reporting.
