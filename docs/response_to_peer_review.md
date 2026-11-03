# Response to the peer review by Group I

Group H, Vélib' project. Review of our 29.09 submission; changes made for 03.11.2026.

Thank you to Group I: running our code on the raw files rather than only reading our documents
is what found the main problem below, before it was built into the dataset.

| # | Point raised | What we did | Where |
|---|---|---|---|
| 1 | **`last_reported` is not the time of the counts** (main recommendation) | Confirmed on our data: 90.5% of count changes happen while `last_reported` is unchanged; it renews about hourly, day and night. Dropped the deduplication on it, keep every capture, renamed `lag_min` to `lr_age_min`. Ran the test you proposed: at 60 min, or with our old plan, only about 1 episode in 6 is still counted, and the share of time without a bike drops from 6.67% to 5.82% with the old plan. | `sampling_test.py`, quality doc, "The main correction" |
| 2 | Question: "300 m from the user" vs station to station | The question now says station to station, and why | README, quality doc, first section |
| 3 | Usable for whom: renting vs returning | Two separate sides everywhere: `can_rent`, `can_return`, episodes per side | `clean.py`, `episodes.py`, dictionary |
| 4 | "Everywhere": unit of comparison | Communes, summarised as Paris vs the rest of the network | Question |
| 5 | Source of the 300 m | velib-metropole.fr/communes/paris (Paris only; our check shows it does not hold in the suburbs) | README |
| 6 | Population is not users | Used as context (stations per resident, density), never as people affected | README |
| 7 | Station count not constant; match each day with that day's list | Each day is joined with its own station list. New flags `temporary` (listed under half the days) and `event_station` (100+ docks: Concorde and Invalides, which presence alone would miss) | `clean.py` step 2 |
| 8 | Check file content, not only the HTTP code (21.09 22:50) | `collect.sh` v2 checks every file before archiving (ok / partial / bad, bad files quarantined). `validate.py` checks every past file: on the shipped sample it finds exactly that capture, kept because the counts are present. The full archives hold about 100 such captures per machine (0.8 %), see row 9 | `collect.sh`, `validate.py` |
| 9 | Compare VM1 and VM2 | Run on the full archives (20.09 to 03.11): both machines hold all 288 captures on each of the 43 full days; on 307 shared slots the median share of stations with identical counts is 100 % (minimum 75.8 %). Details in `docs/vm_comparison.md` | `compare_vms.py` |
| 10 | Both VMs in the same region | Kept in Denmark East and stated as a limit: a regional outage would hit both. It would show as a gap in both logs; none up to the 29.09 snapshot | README, limits |

Two limits of the reading that Group I flagged themselves, and that we keep: we can only
describe how `last_reported` behaves, not why (only the operator could say), and the counts are
renewed at least every 5 minutes, which does not prove they are instantaneous.
