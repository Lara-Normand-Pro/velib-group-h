# Vélib' project: raw data quality and cleaning (one page)

Group H. Kenza Gueddas, Adem Ben Njima, Lara Normand, Amine Ben Bachir, Adrien Labergère. 03.11.2026.

Detail and evidence: `data_quality_and_cleaning.pdf`.

**Data.** The GBFS `station_status` feed, captured every 5 minutes by two Azure VMs since 20.09 (45 days). Figures are from 21.09, the complete day shipped in `raw_sample/` (437,184 rows, 1,518 stations), unless marked *full archives*.

## Quality of the raw data

| Level | What we found |
|--------|----------------------------------------|
| Collection | 288 of 288 captures every day on both VMs over the 43 full days (*full archives*); each VM holds every slot, so merging them adds none. No failed request and no gap over 10 minutes up to the 29.09 snapshot. |
| File content | 0.8% of captures are partial (96 on VM1, 98 on VM2, *full archives*): bike and dock counts present, `stationCode` and mechanical / electric split missing. 96 fall in the same slot on both VMs, so the cause is the server, not us. No truncated capture in 295 checked files. |
| Reliability of our own capture | On 307 slots caught by both VMs, the median share of stations with identical counts is 100% (minimum 75.8%): a capture is close to instantaneous. No exact duplicate on one machine; some will appear when the two archives are merged. |
| Meaning | `last_reported` is not the time of the counts: it renews about once an hour, and 90.5% of count changes happen while it is unchanged. |
| Stations | Concorde and Invalides (about 410 docks, open one day) appear for the 26.09 event; 4 stations with capacity 0; 0.85% of rows with bikes + docks above capacity; 23 silent and 3 frozen stations. 1.6% of rows are out of service, 26 stations all day: a real failure for users, so kept. |

## Main cleaning choices, and why

We **flag, we do not alter**: the feed is our only source, so nothing can correct a count. Rows are dropped only when they carry no information; every other problem is a boolean column, and `in_panel` combines them so each exclusion stays visible and reversible.

1. **Drop** captures with fewer than 1,400 stations (network: about 1,519) and repeated `(station_id, fetched_at)` rows. **Keep** partial captures, since availability only needs the counts.
2. **Match each day with that day's station list**, because the network changes during the period.
3. **Exclude temporary and event stations** (100+ docks) from the panel: they would count as failures or as false alternatives.
4. **Keep every capture, no deduplication on `last_reported`.** At one capture per hour, or with our old plan, only about half of the 5-minute episodes remain visible (48.7% and 52.4%) and the share of time without a bike drops from 6.67% to 5.82%.
5. **Flag** silent (`last_reported` older than 180 min) and frozen stations (identical counts for 12 h or more); capacity 0 becomes unknown, capacity conflicts are flagged, not corrected.

Result on 21.09: the panel keeps 435,910 of 437,184 rows (99.7%) and 1,515 stations.

## What the cleaned day already shows (21.09)

| Measure | Value |
|-----------------|--------------------------|
| Share of time a station cannot rent / cannot take a return | 6.7% / 4.7% |
| Failure episodes (at least 2 consecutive captures) | 2,602 no-bike and 1,639 no-dock, plus 28 per side lasting the whole day, almost all at stations out of service |
| Median observed duration | 25 min (no bike), 20 min (no dock); 56% of no-bike episodes last under 30 min |

Durations are what we saw: a real episode can be up to 5 minutes longer at each end.

## Storage

On the cleaned day, Parquet partitioned by date and read with DuckDB takes 1.8 MB for 29 columns, against 46.8 MB for 8 columns in SQLite, and scans faster (10 ms vs 63 ms for the share of time without a bike). SQLite is faster for one-station lookups (0.4 ms vs 7 ms). Our queries are mostly scans, so we keep Parquet, and will measure again on the whole period.

## Limits and what is still open

- Eight weeks of autumn: no winter, no summer. Demonstrations in Paris after the 29.09 snapshot closed or damaged some stations; for the final project we will mark those days and report the results with and without them.
- The counts are renewed at least every 5 minutes, but the feed does not say how long after an event they change, so a short delay may remain.
- Not yet done: the cleaning run on the whole period (our archive is too large to ship), and the commune boundaries (IGN) and population (INSEE), joined in the analysis step as context only.
