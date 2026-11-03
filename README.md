# Vélib' project. Group H. Intermediate version, 03.11.2026

Kenza Gueddas, Adem Ben Njima, Lara Normand, Amine Ben Bachir, Adrien Labergère
Course: Data, Data Storage, Data Collection

Our question: **how often does a Vélib' station fail its users (no bike to rent, or no free
dock to return) while no other station within 300 m of it can serve them instead, and does
this differ between Paris and the surrounding communes?**

The document for this checkpoint is `docs/data_quality_and_cleaning.pdf`: the assessment of
the raw data and the justification of every cleaning step. This README says what is where and
how to run it.

---

## What changed since 29.09

After the peer review by Group I and our own checks:

- **`last_reported` is not the time of the counts.** It renews about once an hour while the
  counts change between our 5-minute captures. We dropped our plan to deduplicate on it and keep
  every capture. `lag_min` is renamed `lr_age_min`. `sampling_test.py` shows what the old plan
  would have cost (about five episodes out of six).
- **The collector checks the content of each file** before archiving it (`collect.sh` v2), and
  `validate.py` applies the same check to every file archived before. On the shipped sample it
  finds one partial capture, 21.09 at 22:50 UTC. The full archives hold about 100 per machine
  (0.8 %), see `docs/vm_comparison.md`.
- **Cleaning is in place** (`clean.py`): same-day station list, temporary and event stations,
  capacity conflicts, silent and frozen stations, all as flags, plus one `in_panel` column.
- **Episodes are built on every capture**, separately for renting and returning (`episodes.py`).
- **First storage comparison**: SQLite vs Parquet + DuckDB (`storage_benchmark.py`).
- **The question names its terms**: station to station, renting vs returning, communes.
- **The 300 m has a source** (below), and population is used as context only.

## What is in this folder

```
GroupH_Velib_0311/
├── README.md                                   this file
├── DATA_DICTIONARY.md                          what every file and column means
├── docs/
│   ├── data_quality_and_cleaning.pdf           THE document for 03.11 (.md source beside it)
│   ├── response_to_peer_review.pdf             what we changed after Group I's review (.md beside it)
│   ├── justification.pdf                       our 29.09 document
│   ├── proposal.pdf                            our proposal of 16.09
│   ├── feedback_group_H.pdf                    the lecturer's feedback on our proposal
│   └── feedback_cohort.pdf                     the lecturer's general feedback
├── code/
│   ├── run_all.py                              runs every step below, in order
│   ├── collect.sh, crontab.txt                 the collector (v2) and its schedule, as on the VMs
│   ├── coverage.py                             HTTP log      ->  captures per day vs expected
│   ├── validate.py                             raw captures  ->  content check of every file
│   ├── build_snapshot.py                       raw captures  ->  one Parquet file per day
│   ├── daily_json.py                           raw captures  ->  one NDJSON file per day
│   ├── ndjson_to_csv.py                        one NDJSON day ->  a flat CSV for Excel
│   ├── neighbours.py                           station list  ->  distances, 200 / 300 / 500 m
│   ├── clean.py                                Parquet       ->  cleaned table with flags
│   ├── episodes.py                             cleaned table ->  failure episodes
│   ├── sampling_test.py                        cleaned table ->  last_reported check, 5 vs 15/30/60 min
│   ├── storage_benchmark.py                    cleaned table ->  SQLite vs Parquet + DuckDB
│   ├── compare_vms.py                          two VM archives -> what each caught
│   ├── _paths.py                               finds the files whatever the working directory
│   └── requirements.txt
├── data/
│   ├── station_status/date=2026-09-20/ ... 29/ flat table, one Parquet file per day, 10 days
│   ├── clean/
│   │   ├── station_status_clean/date=.../      the cleaned table
│   │   ├── episodes.parquet                    one row per failure episode
│   │   ├── stations_daily.csv                  one row per station per day
│   │   ├── cleaning_log.csv                    what each cleaning step did, in rows
│   │   ├── last_reported_check.csv             the last_reported diagnostics
│   │   ├── sampling_sensitivity.csv            episodes at 5 / 15 / 30 / 60 min
│   │   └── storage_benchmark.csv               the storage comparison
│   ├── capture_quality.csv                     content check, one row per raw capture
│   ├── coverage_status.csv, coverage_info.csv  captures per day vs 288 / 24 expected
│   ├── station_neighbours.csv                  distance to the nearest station, per station
│   ├── threshold_sensitivity.csv               share with a neighbour at 200 / 300 / 500 m
│   ├── station_information_20260929.json.gz    the station list of 29.09
│   ├── status_2026-09-21.ndjson.gz             21.09, raw, all 288 captures in one file
│   └── status_2026-09-21.csv                   the same day as a flat CSV
└── raw_sample/
    ├── full_day_2026-09-21/                    all 288 untouched captures of 21.09
    ├── status_2026092*T082001Z.json.gz         one untouched capture per day, 20.09 to 27.09
    ├── info_20260920T210520Z.json.gz           one untouched station list
    └── http_log.csv                            every request we made, successful or not
```

The flat table `data/station_status/` covers the whole snapshot of 29.09 (10 days, 3,686,536 rows).
Everything computed from it (cleaning, episodes, tests, storage benchmark) and all figures in the
documents are for **21.09**, the full day of raw captures shipped here, so anyone can rebuild every
one of them. The other nine days of the flat table come from our 29.09 submission: the raw files
of those days are not in this package, so they cannot be rebuilt here (see the data dictionary,
section 1). The full archive (20.09 to 16.11) stays on our machines until it is deposited on
Zenodo (see the end).

## How to run the code

```bash
pip install -r code/requirements.txt
python code/run_all.py              # every step, about one minute
python code/run_all.py --no-bench   # without the storage benchmark (no duckdb needed)
```

Or one script at a time, in the order of `run_all.py`. Each prints what it read, what it wrote,
and the figures quoted in our documents.

**Nothing you submitted gets overwritten.** Without the full archive the scripts write into
`data/rebuilt/`, so their output can be compared with the files in `data/`: they should match
(for the flat table, on 21.09).
On our machines, where the archive is present, the same scripts write into `data/`.

The scripts find their input from their own location, so the VS Code Run button, a terminal at
the package root and a terminal inside `code/` all behave the same. To run on the full period,
put the raw archive beside the package as `snapshot_2909/raw/status/` and `.../raw/info/`
(`code/_paths.py` is the one place to change if it lives elsewhere).

## How we collect

Vélib' publishes the network state through a public GBFS feed, current state only, no history.

- Feed: `https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json`
  (and `station_information.json`)
- Every 5 minutes for the status (288 a day), every hour for the station list (24 a day)
- Two always-on cloud VMs (Azure, Denmark East, Ubuntu, cron), same script on both
- Every attempt is logged. Since v2 of `collect.sh` the line is
  `timestamp,feed,http_code,bytes,n_stations,check`; older lines have the first three fields

**Collector v2.** The file is parsed and checked before it is archived: `ok` (complete),
`partial` (counts present, descriptive fields missing, archived and flagged), `bad`
(unreadable, truncated or counts missing, moved to `quarantine/`, never deleted). Version 1 only
logged the HTTP code, which is how the incomplete 21.09 22:50 capture went unnoticed.

Anyone can reproduce our *method* with `collect.sh` and `crontab.txt`. Nobody can reproduce our
*data*: the feed keeps no history, so an archive only grows forward from the day it starts.

## External sources

Both are static and joined in the analysis step: **IGN ADMIN-EXPRESS** commune boundaries (to
place each station in a commune; around 305 stations are outside Paris) and **INSEE** population
by commune. Population counts residents, not users, so we use it as context (stations per
resident, density), never as a number of people affected.

## Why 300 m

Vélib' Métropole states there is a station every 300 m in Paris
(https://www.velib-metropole.fr/communes/paris, accessed 11.10.2026). We tested it on the
station coordinates:

| Distance | Stations with another station within it |
|---|---|
| 200 m | 39.0% |
| 300 m | 68.0% |
| 500 m | 88.5% |

Median distance to the nearest station: 231 m. At 200 m almost two thirds of stations would be
"isolated" and the word means nothing; at 500 m we would call a six or seven minute walk an
alternative. Distances are straight lines, so real walks are longer and our isolation counts
are optimistic.

## Data quality, in short

Full assessment in `docs/data_quality_and_cleaning.pdf`.

| What we checked | Result |
|---|---|
| Status captures on full days (20.09 to 29.09 snapshot) | 288 / 288 every day |
| Requests that did not return 200 | 0 |
| Gaps longer than 10 minutes | 0 |
| Captures with incomplete content | 1 in the shipped sample (21.09 22:50, counts present); 96 (VM1) and 98 (VM2) in the full archives, 0.8 % (`docs/vm_comparison.md`) |
| Rows kept for analysis on 21.09 | 435,910 of 437,184 (99.7%) |
| Median age of `last_reported` when read | 32 min: an hourly signal, not a delay of the counts |

## What we cannot claim

- We cannot tell a broken station from one that stopped reporting, hence "out of service" and
  never "broken".
- The counts are renewed at least every 5 minutes, but the feed does not say how long after a
  real event they change.
- Episode durations are what we observed: the real episode can be up to 5 minutes longer at each
  end.
- Eight weeks in autumn is not a year: no winter, no summer, no big event outside our window.
- Demonstrations and riots in Paris after the 29.09 snapshot (autumn 2026) will show up in the data collected later: some stations were closed or damaged. The data shipped here (20.09 to 29.09) is not affected. For the final project we will mark the affected days and report the results with and without them.
- The figures shipped here come from the first machine; `compare_vms.py` compares the two (result in `docs/vm_comparison.md`: no missed slot on either machine over 43 full days).
  Both machines are in the same Azure region, so a regional outage would hit both.

## Where the raw data is

The full raw archive is not included (99 MB on 29.09, still growing). Shipped instead: all 288
untouched captures of 21.09, one capture per day, one station list and the complete log of the
29.09 snapshot. Collection stops on 16.11.2026; we then deposit the archive on Zenodo (DOI,
versioned) as a few compressed files, since a record holds at most 100 files, and delete the VMs.

## Licence

Data from Vélib' Métropole / Smovengo, Open Database License (ODbL). It describes stations, not
people: no personal data. 312 requests a day on a public file; nothing is bypassed.
