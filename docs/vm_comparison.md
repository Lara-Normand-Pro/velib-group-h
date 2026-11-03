# VM1 vs VM2: reliability of our own collection

Run on 03.11.2026 with `code/compare_vms.py` on the two full raw archives
(`~/velib/status/` copied from each VM). Per-day table: `data/vm_comparison.csv`.

| | VM1 | VM2 |
|---|---|---|
| Start of collection | 20.09.2026 21:05 UTC | 20.09.2026 18:57 UTC |
| Status captures archived | 12,613 | 12,605 |

## Results

**1. Both machines caught every capture on every full day.**
From 21.09 to 02.11 (43 days), each VM has 288 captures a day, i.e. 12,384 each, and the union
of the two is also 12,384. Neither machine missed a 5-minute slot, so merging the two archives
recovers nothing that one machine alone did not already have.

**2. The only slots caught by one machine are explained by the calendar, not by failures.**

| Day | Only VM1 | Only VM2 | Reason |
|---|---|---|---|
| 20.09 | 0 | 26 | VM2 started at 18:57 UTC, VM1 at 21:05 UTC |
| 03.11 | 34 | 0 | day in progress: the VM2 copy was taken a few hours before the VM1 copy |

**3. Two requests a few seconds apart read nearly the same feed.**
On 307 slots compared (a sample of the slots both VMs caught), the share of stations with
identical bike and dock counts is 100 % at the median and 75.8 % at the minimum. The feed does
change between two requests made seconds apart, but only for a small part of the stations, so a
capture is close to instantaneous.

**4. The partial captures come from the server, not from our machines.**
Version 1 of the collector archived whatever the server returned. In the archives, 96 captures
on VM1 and 98 on VM2 (about 0.8 %) are partial: station counts are present, but `stationCode`
and the bike types are empty, and the file is about 24 KB instead of about 34 KB. 96 of them
fall in the same 5-minute slot on both machines. They are spread over all hours and all minutes
of the hour. The same degraded answer reaches both machines at the same moment, so the cause is
on the Vélib' side. This is more frequent than the single capture (21.09 at 22:50 UTC) reported
after the first peer review. Version 2 of the collector flags them as `partial` in the log; it still archives them, and only files that fail the core check go to `quarantine/`.

## What it changes for the project

- The counts (`num_bikes_available`, `num_docks_available`), which the failure episodes use,
  are present in the partial captures, so they are kept for the analysis. Only the bike-type
  split is unavailable for about 0.8 % of the captures.
- One machine would have been enough over this period. The second one is a safeguard, and its
  archive is a check of the first.
