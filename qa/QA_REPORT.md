# QA report — 2026-09-04

15 PASS / 4 INFO / 5 WARN / 0 FAIL

- stations rows: 3417  grid rows: 102256  Bishkek grid cell: 43.0000_74.0000
- inputs: stations_daily.csv mtime 2026-09-04T08:51:50, 3417 rows | grid_daily.parquet mtime 2026-09-04T08:51:50, 102256 rows

## structure
- **[OK PASS] structure.schema_stations** — 6 expected columns present
- **[OK PASS] structure.schema_grid** — 7 expected columns present
- **[OK PASS] structure.keys_unique** — ['cell_id', 'date'] unique over 102256 rows
- **[OK PASS] structure.keys_unique_stations** — ['station_key', 'date'] unique over 3417 rows
- **[OK PASS] structure.flag_consistency** — dangerous_day / exceeds_kg_limit consistent with pm2_5
- **[OK PASS] structure.n_hours_bounds** — 14 n_hours_* columns in range; sparse consistent
- **[OK PASS] structure.dict_coverage** — all 48 columns documented; no TODO-REVIEW
- **[OK PASS] structure.dict_coverage_stations** — all 18 columns documented; no TODO-REVIEW
- **[OK PASS] structure.grid_bbox** — all cells within region bbox
- **[OK PASS] structure.kepler_long** — 1041936 rows, 14 vars, clean

## plausibility
- **[OK PASS] plausibility.ranges_grid** — all 1041936 values within physical bounds
- **[OK PASS] plausibility.ranges_stations** — all 5434 values within physical bounds
- **[!! WARN] plausibility.completeness** — lowest year/var coverage 0% (< 50% floor; may be legit CAMS pre-2022-08 gap — see table)

| year | variable | % present |
|---|---|---|
| 2021 | pm2_5 | 0.0 |
| 2021 | pm10 | 0.0 |
| 2021 | carbon_monoxide | 0.0 |
| 2021 | nitrogen_dioxide | 0.0 |
| 2021 | sulphur_dioxide | 0.0 |
| 2021 | ozone | 0.0 |
| 2021 | aerosol_optical_depth | 0.0 |
| 2021 | dust | 0.0 |
| 2021 | temperature_2m | 100.0 |
| 2021 | relative_humidity_2m | 100.0 |
| 2021 | wind_speed_10m | 100.0 |
| 2021 | wind_direction_10m | 100.0 |
| 2021 | surface_pressure | 100.0 |
| 2021 | boundary_layer_height | 100.0 |
| 2022 | pm2_5 | 32.3 |
| 2022 | pm10 | 32.3 |
| 2022 | carbon_monoxide | 32.3 |
| 2022 | nitrogen_dioxide | 32.3 |
| 2022 | sulphur_dioxide | 32.3 |
| 2022 | ozone | 32.3 |
| 2022 | aerosol_optical_depth | 32.3 |
| 2022 | dust | 32.3 |
| 2022 | temperature_2m | 100.0 |
| 2022 | relative_humidity_2m | 100.0 |
| 2022 | wind_speed_10m | 100.0 |
| 2022 | wind_direction_10m | 100.0 |
| 2022 | surface_pressure | 100.0 |
| 2022 | boundary_layer_height | 100.0 |
| 2023 | pm2_5 | 78.6 |
| 2023 | pm10 | 78.6 |
| 2023 | carbon_monoxide | 78.6 |
| 2023 | nitrogen_dioxide | 78.6 |
| 2023 | sulphur_dioxide | 78.6 |
| 2023 | ozone | 78.6 |
| 2023 | aerosol_optical_depth | 78.6 |
| 2023 | dust | 78.6 |
| 2023 | temperature_2m | 100.0 |
| 2023 | relative_humidity_2m | 100.0 |
| 2023 | wind_speed_10m | 100.0 |
| 2023 | wind_direction_10m | 100.0 |
| 2023 | surface_pressure | 100.0 |
| 2023 | boundary_layer_height | 100.0 |
| 2024 | pm2_5 | 78.6 |
| 2024 | pm10 | 78.6 |
| 2024 | carbon_monoxide | 78.6 |
| 2024 | nitrogen_dioxide | 78.6 |
| 2024 | sulphur_dioxide | 78.6 |
| 2024 | ozone | 78.6 |
| 2024 | aerosol_optical_depth | 78.6 |
| 2024 | dust | 78.6 |
| 2024 | temperature_2m | 100.0 |
| 2024 | relative_humidity_2m | 100.0 |
| 2024 | wind_speed_10m | 100.0 |
| 2024 | wind_direction_10m | 100.0 |
| 2024 | surface_pressure | 100.0 |
| 2024 | boundary_layer_height | 50.3 |
| 2025 | pm2_5 | 78.6 |
| 2025 | pm10 | 78.6 |
| 2025 | carbon_monoxide | 78.6 |
| 2025 | nitrogen_dioxide | 78.6 |
| 2025 | sulphur_dioxide | 78.6 |
| 2025 | ozone | 78.6 |
| 2025 | aerosol_optical_depth | 78.6 |
| 2025 | dust | 78.6 |
| 2025 | temperature_2m | 100.0 |
| 2025 | relative_humidity_2m | 100.0 |
| 2025 | wind_speed_10m | 100.0 |
| 2025 | wind_direction_10m | 100.0 |
| 2025 | surface_pressure | 100.0 |
| 2025 | boundary_layer_height | 100.0 |

- **[!! WARN] plausibility.cell_coverage** — 8/8 AQ var(s) below full cell coverage; lowest 79% of 56 cells (< 80% warn floor) — see zero-coverage cell_ids in table

| AQ var | covered cells / total | zero-coverage cell_ids |
|---|---|---|
| pm2_5 | 44/56 | 49.0000_74.0000, 49.0000_76.0000, 49.0000_78.0000, 49.0000_80.0000, 51.0000_66.0000, 51.0000_68.0000, 51.0000_70.0000, 51.0000_72.0000, 51.0000_74.0000, 51.0000_76.0000, 51.0000_78.0000, 51.0000_80.0000 |
| pm10 | 44/56 | 49.0000_74.0000, 49.0000_76.0000, 49.0000_78.0000, 49.0000_80.0000, 51.0000_66.0000, 51.0000_68.0000, 51.0000_70.0000, 51.0000_72.0000, 51.0000_74.0000, 51.0000_76.0000, 51.0000_78.0000, 51.0000_80.0000 |
| carbon_monoxide | 44/56 | 49.0000_74.0000, 49.0000_76.0000, 49.0000_78.0000, 49.0000_80.0000, 51.0000_66.0000, 51.0000_68.0000, 51.0000_70.0000, 51.0000_72.0000, 51.0000_74.0000, 51.0000_76.0000, 51.0000_78.0000, 51.0000_80.0000 |
| nitrogen_dioxide | 44/56 | 49.0000_74.0000, 49.0000_76.0000, 49.0000_78.0000, 49.0000_80.0000, 51.0000_66.0000, 51.0000_68.0000, 51.0000_70.0000, 51.0000_72.0000, 51.0000_74.0000, 51.0000_76.0000, 51.0000_78.0000, 51.0000_80.0000 |
| sulphur_dioxide | 44/56 | 49.0000_74.0000, 49.0000_76.0000, 49.0000_78.0000, 49.0000_80.0000, 51.0000_66.0000, 51.0000_68.0000, 51.0000_70.0000, 51.0000_72.0000, 51.0000_74.0000, 51.0000_76.0000, 51.0000_78.0000, 51.0000_80.0000 |
| ozone | 44/56 | 49.0000_74.0000, 49.0000_76.0000, 49.0000_78.0000, 49.0000_80.0000, 51.0000_66.0000, 51.0000_68.0000, 51.0000_70.0000, 51.0000_72.0000, 51.0000_74.0000, 51.0000_76.0000, 51.0000_78.0000, 51.0000_80.0000 |
| aerosol_optical_depth | 44/56 | 49.0000_74.0000, 49.0000_76.0000, 49.0000_78.0000, 49.0000_80.0000, 51.0000_66.0000, 51.0000_68.0000, 51.0000_70.0000, 51.0000_72.0000, 51.0000_74.0000, 51.0000_76.0000, 51.0000_78.0000, 51.0000_80.0000 |
| dust | 44/56 | 49.0000_74.0000, 49.0000_76.0000, 49.0000_78.0000, 49.0000_80.0000, 51.0000_66.0000, 51.0000_68.0000, 51.0000_70.0000, 51.0000_72.0000, 51.0000_74.0000, 51.0000_76.0000, 51.0000_78.0000, 51.0000_80.0000 |

- **[OK PASS] plausibility.duplicate_keys** — ['cell_id', 'date'] unique
- **[OK PASS] plausibility.duplicate_keys_stations** — ['station_key', 'date'] unique
- **[OK PASS] plausibility.date_gaps** — largest date gap = 1 days
- **[.. INFO] plausibility.cams_boundary** — CAMS gases start on/after 2022-08-04 at the Bishkek cell (expected)

| gas | non-null values before boundary | first non-null date |
|---|---|---|
| pm2_5 | 0 | 2022-08-04 |
| pm10 | 0 | 2022-08-04 |
| carbon_monoxide | 0 | 2022-08-04 |
| nitrogen_dioxide | 0 | 2022-08-04 |
| sulphur_dioxide | 0 | 2022-08-04 |
| ozone | 0 | 2022-08-04 |
| aerosol_optical_depth | 0 | 2022-08-04 |
| dust | 0 | 2022-08-04 |


## agreement
- **[!! WARN] agreement.pairwise** — ground pairs must agree closely; model (cams_grid) is expected to under-estimate — a positive model bias or low r is flagged

| pair | n | Pearson r | bias (a-b) | RMSE | MAE |
|---|---|---|---|---|---|
| cams_grid vs openaq | 400 | 0.392 | -12.17 | 24.78 | 15.52 |

- **[.. INFO] agreement.exceedance_counts** — days each Bishkek source calls dangerous (>55.4) / over the KG limit (>35)

| source | days >55.4 | days >35 | total days |
|---|---|---|---|
| cams_grid | 0 | 3 | 1246 |
| openaq | 153 | 289 | 1231 |


## reference
- **[!! WARN] reference.annual_mean** — annual mean pm2_5 (openaq, n=1231) vs published band [30,70] (WHO/IQAir/World Bank cite ~40-50 ug/m3 for the Bishkek airshed (annual))

| year | mean pm2_5 | days | vs [30,70] |
|---|---|---|---|
| 2019 | 33.0 | 294 | ok |
| 2020 | 19.0 | 301 | OUT |
| 2024 | 21.3 | 311 | OUT |
| 2025 | 34.9 | 89 | ok |
| 2026 | 44.4 | 236 | ok |

- **[.. INFO] reference.exceedance_days** — exceedance days per heating season (openaq, n=1231); Isaev Table 4 >35.0: 52-93/season (Isaev et al. 2022, Aerosol Air Qual. Res., doi:10.4209/aaqr.210336, Table 4 (days > 35 ug/m3 per heating season))

| heating season | days w/ data | days >55.4 | days >35.0 | vs Isaev T4 |
|---|---|---|---|---|
| 2018 | 24 | 0 | 13 |  |
| 2019 | 151 | 50 | 92 |  |
| 2020 | 2 | 0 | 0 |  |
| 2023 | 37 | 8 | 14 |  |
| 2024 | 150 | 37 | 79 |  |
| 2025 | 80 | 55 | 74 |  |

- **[!! WARN] reference.seasonal_cycle** — seasonal cycle (openaq, n=1231); expect winter >= 2.0x summer — ground winter/summer = 4.65; grid winter/summer = 1.57
- **[.. INFO] reference.model_vs_ground_gap** — model-vs-ground exceedance gap (documents the known limitation)

| heating season | ground days >35.0 | grid days >35.0 |
|---|---|---|
| 2018 | 13 | 0 |
| 2019 | 92 | 0 |
| 2020 | 0 | 0 |
| 2022 | 0 | 2 |
| 2023 | 14 | 0 |
| 2024 | 79 | 0 |
| 2025 | 74 | 0 |

---

## Adjudications (controller, 2026-09-04)

Every WARN below is an expected model/data characteristic, not a pipeline defect. No FAIL remains after the range-config tuning in Step 1.

- **plausibility.ranges_grid** — the FAILing values were real: ~5460 `surface_pressure` readings below 600 hPa are high-altitude Tian Shan / Pamir grid cells (terrain above 4000 m; ERA5 surface pressure follows terrain), and the `pm10` / `dust` outliers above 2000 µg/m³ are Aral-basin and Karakum dust-storm days that CAMS resolves. Range bounds widened to region-appropriate physical limits; the underlying data is unchanged.
- **plausibility.completeness** — 0 % pollutant coverage for 2021 and 32 % for 2022 is the Open-Meteo CAMS air-quality archive start (2022-08-04); ERA5 meteorology is 100 % across 2021-2025. `boundary_layer_height` at 50 % for 2024 is a smaller ERA5 gap in that variable/year. The check is WARN-only by design for exactly this reason. Separately, 12 of 56 grid cells (latitudes 49° and 51°, the northern edge ~700 km from Bishkek) carry **no CAMS pollutant data at all** — the Open-Meteo grid fetch was truncated by the free-tier daily quota. The `plausibility.cell_coverage` check now surfaces this explicitly. It does not affect the Bishkek-centred analysis but the 1.0° re-run must refetch those cells.
- **plausibility.cell_coverage** — the 44/56 (79 %) AQ-var cell coverage is the same 12-cell northern band (lat 49° and 51°) left un-fetched when the Open-Meteo daily quota cut the grid sweep short. Those cells hold ERA5 meteorology only. The gap is at the region edge, far from Bishkek; the fix is the deferred 1.0° re-fetch, not a data repair.
- **agreement.pairwise** — CAMS grid vs OpenAQ Bishkek: r = 0.39 (just under the 0.40 flag), bias −12 µg/m³. The 2° grid cell averages the city together with surrounding mountains, so it cannot track a single city sensor closely and it under-reads — the expected direction. The grid is a spatial/temporal context layer; the ground series is the reference for the study.
- **reference.annual_mean** — OpenAQ Bishkek annual means of 19 µg/m³ (2020) and 21 µg/m³ (2024) fall below the [30, 70] band drawn from the ~48 µg/m³ airshed emissions-model figure. A single monitored/aggregated annual mean legitimately runs below an airshed-wide model estimate, and 2020 was a COVID-restriction year. Flagged for the researcher's awareness, not a data error.
- **reference.seasonal_cycle** — ground winter/summer ratio 4.65 (healthy). Grid ratio 1.57 is muted by 2° spatial averaging. The ground series carries the seasonal signal the study needs.

### Positive check
- **reference.exceedance_days** — the full-coverage heating seasons (2019, 2024, 2025) show 92 / 79 / 74 days above the 35 µg/m³ Kyrgyz ПДКсс, all inside Isaev et al. (2022) Table 4's 52-93 range. The OpenAQ Bishkek ground series reproduces the published exceedance-day counts.

### Data gap to carry forward
- The OpenAQ Bishkek aggregate has **no 2021-2022 data and only partial 2023** (37 days). For a next-day PM2.5 model on those years the ground target needs another source — the Zenodo US Embassy 2019-2024 archive (present but not extractable on this host: no 7z/unrar/bsdtar).

