# Before / after (same raw US Embassy data)

| metric | before (legacy logic) | after (prep pipeline) |
|---|---|---|
| daily rows (station-days) | 3254 (2 keys for 1 instrument) | 2012 (1 series) |
| same instrument-day present twice | 1411 | 0 |
| calendar days covered (any value) | 1843 / 2012 | 1038 valid / 2012 |
| day definition | UTC calendar day (18:00-18:00 local) | local day Asia/Bishkek (EPA) |
| days with < 18 hours used as values | 144 (8225 key) | 0 (set to NaN) |
| days with negative daily mean (-999 sentinel averaged in) | 286 (8225 key) | 0 |
| hours with -999 sentinel inside means | 2578 | 0 |
| days from the contaminated feed window 2023-03-16..2025-01-16 | 516 used | 0 used (673 rows kept as NaN) |
| missing target days inside study span | 324 (8225 key) | 974 (incl. contaminated window) |

## Days by split (day treated as a target day)

| split | before: days | before: dangerous (>55.4, UTC day, unfiltered) | after: valid days | after: dangerous (EPA trunc >= 55.5, local day) | after: > 35 (KG limit) |
|---|---|---|---|---|---|
| train | 632 | 112 | 565 | 111 | 182 |
| validation | 313 | 36 | 267 | 36 | 70 |
| test | 202 | 61 | 190 | 72 | 112 |
| outside | 541 | 0 | 16 | 0 | 0 |
