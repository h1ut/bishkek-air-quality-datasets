# Real pipeline run — record (2026-08-29)

Task 11 of `docs/superpowers/plans/2026-08-29-qa-standards-and-verified-deliverables.md`.
Started as a background subagent; the subagent hit the Open-Meteo daily quota wall
and stalled, so the controller aborted it and ran the remaining pipeline steps
directly to meet a user deadline.

## Fetch results

### OpenAQ (live key) — `fetch_openaq`, 4 cities

| city | days | span | pollutants | 2025 pm2_5 non-null days |
|---|---|---|---|---|
| Bishkek | 1237 | 2019-03-08 … 2026-09-03 | pm10, pm2_5 | 89 |
| Almaty | 1227 | 2020-04-08 … 2026-09-03 | pm10, pm2_5 | 363 |
| Tashkent | 511 | 2018-11-27 … 2026-01-18 | ozone, pm2_5 | 124 |
| Astana | 389 | 2018-07-26 … 2026-07-31 | pm2_5 | 0 |

`_stations_staging.csv`: **296 sensor locations** in the region —
OpenAQ:AirGradient 163, OpenAQ:Clarity 128, OpenAQ:AirNow 3, OpenAQ:StateAir 2.

### AirNow 2025 gap-fill — `fetch_airnow --start 2025-01-01 --end 2025-12-31`

Ran because Bishkek OpenAQ 2025 coverage (89 days) < 250 threshold. Result:
53 daily rows, **0 usable pm2_5** (endpoint returned AQI without a µg/m³ value;
run stopped ~2025-03-04, likely the 500 req/hour cap). Not a useful gap-fill;
the Bishkek reference series is covered by OpenAQ's own AirNow-provider station.

### Zenodo — `fetch_zenodo_bishkek` + `parse_zenodo_bishkek`

Archive present (58 MB, checksum-verified in predecessor Task 5). **No rar
extractor (7z / unrar / bsdtar) on this machine** → `bishkek_monitoring_us.embassy2019-2024.rar`
not unpacked; `parse_us_embassy` = 0 days, `parse_clarity` = 0 days. The US
Embassy archive series is therefore unavailable this run.

### Open-Meteo — `fetch_open_meteo` — QUOTA BLOCKED

- The subagent's `--mode points` run stalled at roughly 56 of ~300 point-pairs
  and produced no fresh `openmeteo_points_daily.csv`; the `--mode grid` run was
  never reached. Cache write rate: ~12/min from 08:19, collapsing to 0 by 08:33
  (~113 successful calls, then a hard wall — the Open-Meteo free-tier daily
  request limit, the same wall the predecessor plan hit).
- The stuck fetch processes were terminated so they would stop consuming quota.
- **Ruling:** ship the existing real 2° grid; defer the 1.0° grid to a
  fresh-quota day (`fetch_open_meteo --mode grid --grid-spacing 1.0`).

## Datasets built (controller, from real stations + the existing 2° grid)

- `dataset/stations_daily.csv` — **3417 rows**, 5 station_keys
  (bishkek 1237, almaty 1227, tashkent 511, astana 389, bishkek_us_embassy 53).
  Bishkek pm2_5 mean ≈ 28.9, max 435.6; Almaty mean 34.3; Tashkent 48.6; Astana 31.4.
- `dataset/grid_daily.parquet` — 102 256 rows, 56 cells (2° grid), 2021-01-01 … 2025-12-31,
  all 8 CAMS + 6 ERA5 variables. CAMS pollutants non-null only from 2022-08-04
  (53.6% of the timeline); ERA5 meteorology 100%.
- `dataset/data_dictionary.md` — 0 TODO-REVIEW.
- `dataset/grid_daily_sample.csv` — regenerated (Bishkek-area cells, unchanged content).
- `map/bishkek_air_quality_map.html` — rebuilt; snapshot 2025-03-26 (worst
  heating-season day); LayerControl + CAMS grid layer present; 0 `pm2_5=nan`
  markers. (The "Study & campaign sites" FeatureGroup name is absent from the
  rendered HTML — pre-existing minor, tracked for Task 13.)
- `kepler/stations_kepler.csv` — refreshed from `catalog/stations.geojson`.

## kepler.gl deliverables (controller, full detail — sent to the user)

- `kepler/ca_air_quality_grid.csv` — daily grid, 14 vars + 2 flags, 102 256 rows (~22 MB).
- `kepler/ca_air_quality_stations.csv` — 3288 rows, 4 cities' daily OpenAQ obs with coords.
- `kepler/ca_air_quality_sensors.csv` — 296 sensor point locations.
- `kepler/kepler_config.json` — 3 layers (grid / stations / sensors) + 2 time filters.
- `kepler/ca_air_quality_map.json` — all 3 datasets + config, one-drag (~26 MB).
- `kepler/HOW_TO_LOAD.md` — load order (CSVs then config), full detail, no aggregation.
(The bulky `kepler/ca_air_quality_*` files are gitignored — regenerated per run.)

## Acceptance gates (Task 11 §7)

| gate | status |
|---|---|
| pytest suite green | PASS (64) |
| no `55.4` / `> 35` literal in build_dataset flag logic | PASS (only `_DICT` caveat text) |
| `stations_daily.csv` non-empty, Bishkek key present | PASS (3417 rows; `bishkek`) |
| `grid_daily.parquet` cell count | 56 (2° — 1.0° deferred, quota) |
| `data_dictionary.md` zero TODO-REVIEW | PASS |
| `kepler/stations_kepler.csv` has rows | PASS |
| no gitignored file staged | PASS |

## Known limitations carried forward

1. Grid is 2° / 56 cells, not the planned 1.0° / ~210 — Open-Meteo free-tier
   daily quota. Re-run `--grid-spacing 1.0` on a fresh day.
2. CAMS pollutant columns blank before 2022-08-04 (archive start). ERA5 met full.
3. Zenodo US Embassy / Clarity series unavailable (no rar extractor on the host).
4. AirNow direct 2025 gap-fill produced no usable pm2_5.
5. QA (Task 12) must widen `surface_pressure` and `dust`/`pm10` plausibility
   ranges — high-altitude Tian Shan / Pamir cells (~534 hPa) and Aral/Karakum
   dust storms (pm10 > 2000, dust > 3000 µg/m³) are physically real for this
   grid and would otherwise trip range FAILs.
6. 12 of the 56 grid cells (latitudes 49° and 51°, the northern edge ~700 km
   from Bishkek) carry **no CAMS pollutant data at all** — the Open-Meteo grid
   fetch was truncated by the free-tier daily quota. ERA5 meteorology is present
   for those cells. The `plausibility.cell_coverage` QA check now surfaces this
   explicitly (44/56 = 79 % AQ-var cell coverage → WARN). It does not affect the
   Bishkek-centred analysis but the 1.0° re-run must refetch those cells.
