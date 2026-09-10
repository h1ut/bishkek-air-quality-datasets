# Project documentation — Central Asia Air Quality Dataset Collection

_Last updated: 2026-09-10_

This document is the single narrative record of everything built in this
repository: what it is, why each piece exists, how it maps to the research
questions, what the pipeline produces, how the data was quality-checked, and
what is finished versus deferred. For the column-level dataset reference and the
per-source grading rationale, see [`README.md`](../README.md); this document
does not repeat those tables, it links to them.

---

## 1. Purpose and research context

The repository is the **data foundation** for a machine-learning study that
forecasts **next-day daily-mean PM2.5 in Bishkek** during the heating season
(Nov–Mar), with model error reported **separately for ordinary days and
"dangerous" days** plus recall on dangerous days. The forecasting model itself
is a **separate project** — this repo only collects, catalogs, quality-checks
and packages the inputs.

### How the deliverables serve the research questions

| RQ | Question (paraphrased) | What this repo provides |
|---|---|---|
| **RQ1** | Can air quality be predicted accurately in a data-scarce region like Bishkek? | A verified ground-truth PM2.5 series for Bishkek (OpenAQ + AirNow US Embassy + the Zenodo US Embassy archive), quantified data gaps (§6), and a QA layer (§5) that proves the ground series reproduces published exceedance-day counts. This is the honest baseline of *how* data-scarce the problem actually is. |
| **RQ2** | Do extra pollutants (SO2, CO, NO2, PM10) improve next-day PM2.5 forecasts, or mainly add noise/missing values? | Every candidate predictor is in the two datasets with an explicit **missingness profile** (`n_hours_*` counts, `sparse` flag, per-year completeness in the QA report). The catalog grades each source A/B/C so the modeller knows which pollutant columns are measurement vs model estimate before doing the ablation. |
| **RQ3** | How does performance change with the algorithm used? | Out of scope for this repo (it is a modelling question), but the datasets are delivered in algorithm-neutral wide/long form (CSV + Parquet) with a temporal key, so any learner can be dropped on top without re-engineering the inputs. |

### Framing decisions already fixed (in project memory)

- **Dangerous day (primary)** = daily-mean PM2.5 **> 55.4 µg/m³** — US EPA AQI
  "Unhealthy" lower breakpoint.
- **National limit (secondary)** = daily-mean PM2.5 **> 35 µg/m³** — Kyrgyz
  ПДК среднесуточная, ПП КР №201 от 11.04.2016, поз. 613.
- **Only these two standards are used.** WHO and EU values were considered and
  deliberately excluded. See [`catalog/standards.csv`](../catalog/standards.csv)
  and §4 below.
- Daily resolution, **temporal** train/test split (never random), heating
  season Nov–Mar.

---

## 2. What was built — component inventory

| Area | Files | What it does |
|---|---|---|
| **Source catalog** | [`catalog/sources.csv`](../catalog/sources.csv) (12 sources), [`catalog/studies.csv`](../catalog/studies.csv) (8 case studies), [`catalog/stations.geojson`](../catalog/stations.geojson), [`catalog/validate_catalog.py`](../catalog/validate_catalog.py) | Machine-readable, schema-validated inventory of every usable data source with an A/B/C quality grade, licence, coverage and access method. |
| **Standards module** | [`catalog/standards.csv`](../catalog/standards.csv) (13 rows), [`catalog/standards.py`](../catalog/standards.py) | The exact threshold values (US EPA 55.4, Kyrgyz ПДК set) with citations. `load_standards()` / `require()` feed the dataset builder so **no threshold literal is hard-coded** in the flag logic. |
| **Fetch scripts** | [`fetch/fetch_openaq.py`](../fetch/fetch_openaq.py), [`fetch/fetch_airnow.py`](../fetch/fetch_airnow.py), [`fetch/fetch_zenodo_bishkek.py`](../fetch/fetch_zenodo_bishkek.py), [`fetch/parse_zenodo_bishkek.py`](../fetch/parse_zenodo_bishkek.py), [`fetch/fetch_open_meteo.py`](../fetch/fetch_open_meteo.py), [`fetch/common.py`](../fetch/common.py) | Runnable, cached (30-day TTL), rate-limit-aware API clients. Each writes a `*_quality_report.md` next to its output. |
| **Dataset builder** | [`fetch/build_dataset.py`](../fetch/build_dataset.py) | Merges all fetched sources into the two analysis-ready datasets, computes the `dangerous_day` / `exceeds_kg_limit` flags from the standards module, and regenerates [`dataset/data_dictionary.md`](../dataset/data_dictionary.md). |
| **QA layer** | [`qa/`](../qa/) — `report.py`, `loaders.py`, `geo.py`, `thresholds.yaml`, `reference_values.yaml`, `checks/{structure,plausibility,agreement,reference}.py` | Four-axis, read-only quality assessment → [`qa/QA_REPORT.md`](../qa/QA_REPORT.md). Exits non-zero on any FAIL. Never modifies data. |
| **Folium map** | [`map/build_map.py`](../map/build_map.py) → `map/bishkek_air_quality_map.html` | Layered Leaflet map: reference monitors, agency sensors, low-cost/citizen sensors, comparison cities, study sites, airshed extent, and a one-day CAMS PM2.5 grid snapshot. |
| **kepler.gl exports** | [`kepler/build_kepler_map.py`](../kepler/build_kepler_map.py), [`kepler/HOW_TO_LOAD.md`](../kepler/HOW_TO_LOAD.md), [`kepler/kepler_config.json`](../kepler/kepler_config.json) | Generates CSVs (grid / stations / sensors) + a styling JSON for <https://kepler.gl/demo>, with a time slider over 2021–2025. |
| **Design + plan records** | [`docs/superpowers/specs/`](superpowers/specs/), [`docs/superpowers/plans/`](superpowers/plans/) | The two design specs and implementation plans the work was executed against, plus the real-run record. |
| **Tests** | [`tests/`](../tests/) | **72 passing** (`.venv/Scripts/python -m pytest -q`). |

---

## 3. Data sources (summary)

Full grading rationale and per-source ML-relevance notes: [`README.md` §3](../README.md).

**Ground measurement**

| source | grade | role |
|---|---|---|
| AirNow — US Embassy Bishkek | **A** | Reference-grade PM2.5 ground truth for Bishkek; validation yardstick for the grid. Single point, occasional gaps. |
| OpenAQ v3 | **B** | Primary programmatic multi-pollutant + lagged-PM2.5 source for Bishkek, Almaty, Tashkent, Astana. Mixes reference and low-cost instruments — check per-station provenance. |
| Zenodo 12720883 (Guttikunda 2024) | **B** | Offline fallback for the Bishkek ground record (US Embassy 2019–2024 + Clarity 2021) and a static 2018 emissions grid. |
| Kyrgyzhydromet / MoveGreen AQ.kg / AirKaz | **C** | Extra spatial density / pollutant coverage, but PDF-only history or uncalibrated low-cost sensors. Documented, not automated. |

**Model / reanalysis / satellite**

| source | grade | role |
|---|---|---|
| Open-Meteo Air Quality (Copernicus CAMS) | **B** | Region-wide gridded pollutants (pm2_5, pm10, CO, NO2, SO2, O3, AOD, dust). Coarse model surface; **archive starts 2022-08-04**. |
| Open-Meteo Historical Weather (ERA5) | **B** | Meteorology block incl. **boundary_layer_height** (the winter-inversion driver). Full 2021–2025. |
| Sentinel-5P TROPOMI, CAMS EAC4 | **B** | Documented with ready-to-run snippets, **not automated** this iteration. |

**Study tables** — WHO Ambient Air Quality DB, World Bank Bishkek 2023 — grade **C**, used only for sanity-checking annual levels.

---

## 4. Air quality standards

Decision: **use only the US EPA and Kyrgyz thresholds.** All 13 rows in
[`catalog/standards.csv`](../catalog/standards.csv) are cited to a primary
source.

| standard_id | value | kind | citation |
|---|---|---|---|
| `epa_aqi_unhealthy_pm25` | 55.4 µg/m³ (24 h) | alert | US EPA AQI Technical Assistance Document — "Unhealthy" lower breakpoint |
| `kg_mpc_daily_pm25` | 35 µg/m³ (24 h) | limit | ПП КР №201 от 11.04.2016, поз. 613 (0,035 мг/м³ среднесуточная) |
| `kg_mpc_annual_pm25` | 25 µg/m³ (1 y) | limit | ПП КР №201, поз. 613 примечание |
| `kg_mpc_daily_pm10` / annual | 60 / 40 µg/m³ | limit | ПП КР №201, поз. 612 |
| `kg_mpc_daily_so2` | 50 µg/m³ | limit | ПП КР №201, поз. 463 |
| `kg_mpc_daily_no2` / `_no` | 40 / 60 µg/m³ | limit | ПП КР №201, поз. 4 / 6 |
| `kg_mpc_daily_co` | 3000 µg/m³ (3 mg/m³) | limit | ПП КР №201, поз. 521 |
| `kg_mpc_daily_o3` | 30 µg/m³ | limit | ПП КР №201, поз. 387 |
| `kg_mpc_daily_nh3` / `_hcoh` / `_hcn` | 40 / 3 / 1 µg/m³ | limit | ПП КР №201, поз. 103 / 541 |

The Kyrgyz decree values were extracted directly from the official PDF
(faolex.fao.org/docs/pdf/kyr179875.pdf). `build_dataset.py` reads
`epa_aqi_unhealthy_pm25` and `kg_mpc_daily_pm25` via `catalog.standards.require()`
to compute the two boolean flags — a nullable boolean, `<NA>` where `pm2_5` is
missing (distinct from `False`).

---

## 5. The two datasets

Column-by-column reference: [`dataset/data_dictionary.md`](../dataset/data_dictionary.md)
(auto-generated, 0 `TODO-REVIEW` rows). A committed 63-row preview of the grid is
[`dataset/grid_daily_sample.csv`](../dataset/grid_daily_sample.csv).

### 5.1 `dataset/stations_daily.csv` — ground truth (wide, one row per station-date)

- Keys `station_key, date, lat, lon, city`; pollutants `pm2_5, pm10,
  carbon_monoxide, nitrogen_dioxide, sulphur_dioxide, ozone` (+ `_max`);
  `n_hours_<var>`, `sparse`; `<var>_source` provenance (`openaq` / `airnow`,
  AirNow wins for Bishkek PM2.5).
- **Real run:** 3417 rows across Bishkek, Almaty, Tashkent, Astana and the
  US Embassy key.

### 5.2 `dataset/grid_daily.parquet` — regional gridded surface (wide, one row per cell-date)

- Keys `cell_id (<lat:.4f>_<lon:.4f>), lat, lon, date`; 8 CAMS pollutants
  (+ `_max`); 6 ERA5 meteorology vars (+ `_max`; wind direction is a vector
  mean); `n_hours_<var>`, `sparse`; derived `dangerous_day`, `exceeds_kg_limit`.
- **Real run:** 102 256 rows = 56 cells × 1826 days, 2021-01-01 → 2025-12-31,
  built at **2° spacing** (see §6). CAMS pollutants populate from 2022-08-04;
  ERA5 meteorology is complete.
- Long-format twin for the kepler time slider:
  `kepler/grid_daily_long.parquet` (`cell_id, lat, lon, date, variable, value`).

---

## 6. Quality assessment

`.venv/Scripts/python -m qa.report` → [`qa/QA_REPORT.md`](../qa/QA_REPORT.md).
Latest committed run (2026-09-04): **15 PASS / 4 INFO / 5 WARN / 0 FAIL**.

### The four axes

1. **structure** — schema, key uniqueness, flag↔`pm2_5` consistency,
   `n_hours` bounds, data-dictionary coverage, grid bbox, long-format integrity.
2. **plausibility** — physical-range bounds, completeness by year/variable,
   **per-cell coverage**, duplicate keys, date gaps, CAMS archive-start boundary.
3. **agreement** — CAMS grid vs OpenAQ Bishkek (Pearson r, bias, RMSE, MAE) and
   exceedance-day counts per source. Model is *expected* to under-read; a
   positive bias or low r is flagged.
4. **reference** — annual mean vs published band, exceedance days per heating
   season vs **Isaev et al. (2022) Table 4**, seasonal cycle, model-vs-ground gap.

### Headline results

- **No FAIL.** Every WARN is an adjudicated model/data characteristic, not a
  pipeline defect — the adjudications are appended to `qa/QA_REPORT.md`.
- **Positive validation:** the OpenAQ Bishkek ground series reproduces
  Isaev et al. (2022) Table 4 — full heating seasons 2019 / 2024 / 2025 show
  **92 / 79 / 74** days above the 35 µg/m³ Kyrgyz limit, all inside the published
  **52–93** range.
- **CAMS grid vs ground:** r ≈ 0.39, bias ≈ −12 µg/m³ over ~400 overlapping
  days — the coarse cell blends the city with cold clean mountains and under-reads,
  as expected. **The grid is a spatial/temporal context layer, not the PM2.5
  target.**

### Known limitations carried forward

1. **CAMS pollutants do not reach 2021** — Open-Meteo CAMS archive starts
   2022-08-04. ERA5 meteorology covers the full span. Any model consuming
   gridded pollutants must restrict its training window.
2. **Grid is 2° / 56 cells**, not the planned 1.0° / ~210 — the finer re-fetch
   was blocked by the Open-Meteo free-tier daily request limit. Re-run
   `fetch.fetch_open_meteo --mode grid --grid-spacing 1.0` on a fresh-quota day.
3. **12 of the 56 cells** (latitudes 49°/51°, the northern edge ~700 km from
   Bishkek) carry **no CAMS pollutant data at all** — the sweep was truncated
   mid-run by the same quota. ERA5 meteorology is present for them. Surfaced by
   the `plausibility.cell_coverage` check. Does not affect the Bishkek-centred
   analysis; the 1.0° re-run must refetch these cells.
4. **OpenAQ Bishkek has a 2021–2023 hole** — the aggregate jumps from 2020 to
   2024. Model-vs-ground overlap for the Bishkek cell is only ~400 days. For a
   next-day model on 2021–2023 the ground target needs the Zenodo US Embassy
   archive.
5. **Zenodo US Embassy / Clarity series not extracted** — the archive contains
   a `.rar` and this host has no `7z` / `unrar` / `bsdtar`. Install an
   extractor, then `fetch.parse_zenodo_bishkek`.
6. **AirNow direct 2025 gap-fill produced no usable µg/m³ PM2.5** (endpoint
   returned AQI only; likely hit the 500 req/hour cap). The Bishkek reference is
   covered by OpenAQ's own AirNow-provider station.
7. **Single reference monitor in Bishkek** — the entire ground truth rests on
   one US Embassy instrument in one location; it cannot represent
   neighbourhood-scale variation.
8. **Low-cost sensor calibration unknown** — grade-C networks (OpenAQ low-cost,
   MoveGreen, AirKaz) use Plantower-class sensors with no published local
   calibration; bias-correct against the reference before use.

---

## 7. Interactive maps

### Folium — `map/bishkek_air_quality_map.html`

Built by [`map/build_map.py`](../map/build_map.py) from
`catalog/stations.geojson`, `catalog/studies.csv` and `dataset/grid_daily.parquet`.
Open in any browser. Toggleable layers: reference monitors (green = grade A),
Kyrgyzhydromet sensors (orange = B), citizen/low-cost sensors (red = C),
comparison cities, study sites (book icons, DOI popups), airshed extent, and a
one-day CAMS PM2.5 grid snapshot on the worst region-mean day.

### kepler.gl

`.venv/Scripts/python -m kepler.build_kepler_map` writes:

| file | contents | tracked? |
|---|---|---|
| `kepler/ca_air_quality_grid.csv` | daily grid, 14 CAMS+ERA5 vars + 2 flags, ~102k rows | gitignored (bulky) |
| `kepler/ca_air_quality_stations.csv` | real OpenAQ/AirNow daily series with city coords | gitignored |
| `kepler/ca_air_quality_sensors.csv` | ~296 discovered sensor locations | gitignored |
| `kepler/kepler_config.json` | 3 point layers + 2 time-range filters | **committed** |
| `kepler/ca_air_quality_styling.json` | colours + time sliders bound to the CSVs by name | gitignored |

Load order and the 6-click manual fallback: [`kepler/HOW_TO_LOAD.md`](../kepler/HOW_TO_LOAD.md).
Drag the 3 CSVs into <https://kepler.gl/demo>, then the styling JSON **after**
them; add a `date` filter for the time-playback slider.

> **Open item (raised 2026-09-10):** rendering the grid as filled **polygon
> blocks** (choropleth) instead of point circles. Feasible via a GeoJSON grid
> export (one square polygon per cell) or kepler's in-UI Grid/Hexbin layer type.
> True *administrative-district* colouring is not feasible at the current 2°
> (~200 km) cell size — the data has no district-level resolution.

---

## 8. How to reproduce

```bash
# 1. Environment (Python 3.14; .venv already provisioned)
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt

# 2. Config
cp fetch/config.example.yaml fetch/config.yaml      # then add the 2 free keys,
                                                    # or set OPENAQ_API_KEY / AIRNOW_API_KEY

# 3. Pipeline (from repo root, in order)
.venv/Scripts/python -m fetch.fetch_openaq
.venv/Scripts/python -m fetch.fetch_airnow
.venv/Scripts/python -m fetch.fetch_zenodo_bishkek
.venv/Scripts/python -m fetch.fetch_open_meteo --mode points
.venv/Scripts/python -m fetch.fetch_open_meteo --mode grid --grid-spacing 2.0
.venv/Scripts/python -m fetch.build_dataset
.venv/Scripts/python -m map.build_map
.venv/Scripts/python -m kepler.build_kepler_map

# 4. Quality gate
.venv/Scripts/python -m qa.report        # writes qa/QA_REPORT.md, exit 1 on any FAIL
.venv/Scripts/python -m pytest -q        # 72 passing
```

Free API keys: OpenAQ <https://explore.openaq.org/register>, AirNow
<https://docs.airnowapi.org/account/request/>. Neither is needed for Open-Meteo,
Zenodo, the build, the map, the kepler export or the QA gate.

**Watch the Open-Meteo quota.** `--mode grid` issues one AQ call + one weather
call per cell over the full date range; the free tier caps at ~10 000 calls/day
and rate-limits large sweeps. 2° / 56 cells is the safe fallback; 1.0° needs a
fresh quota day.

`fetch/config.yaml` and everything under `data/`, plus the bulky
`dataset/*.parquet`, `dataset/stations_daily.csv` and `kepler/ca_air_quality_*`
files are **gitignored** — they are regenerated per run. No API key has ever
been committed (verified against full history).

---

## 9. Engineering process

The work was executed in **two planned delivery phases**, each with a written
design spec, an implementation plan, subagent-driven implementation, task-level
review, a final whole-branch review, and a fix wave.

| Phase | Spec / plan | Delivered |
|---|---|---|
| **1 — collection + maps** (2026-08-28/29) | `docs/superpowers/specs/2026-08-28-*`, `plans/2026-08-28-*` | Catalog, fetch scripts, `build_dataset`, Folium map, first kepler export, initial test suite. |
| **2 — QA + standards + verified real run** (2026-08-29 → 09-04) | `docs/superpowers/specs/2026-08-29-*`, `plans/2026-08-29-*`, `plans/2026-08-29-real-run-record.md` | Standards module, 4-axis QA layer, `build_kepler_map.py`, a real end-to-end pipeline run on live data, and the committed `qa/QA_REPORT.md`. |

### Notable rulings (decisions made during the build)

- **Version pins → floor constraints** (`pandas>=2.2,<3` etc.) — Python 3.14 has
  no cp314 wheels for the originally pinned versions.
- **Thresholds narrowed to US EPA + Kyrgyz only** — WHO/EU considered and
  dropped; recorded in project memory and `catalog/standards.csv`.
- **Ship the 2° grid, defer 1.0°** — Open-Meteo free-tier daily quota wall
  (hit twice). Documented and re-runnable.
- **Controller ran Phase-2 Task 11 build steps directly** — an execute-and-record
  task whose subagent stalled against a hard deadline; no code was written, only
  pipeline commands + exports.
- **QA physical-range bounds widened** for `surface_pressure` (high-altitude
  Tian Shan/Pamir cells, ~534 hPa), `pm10` and `dust` (Aral/Karakum dust storms)
  — real values, not data defects.
- **Per-cell coverage check added** after final review caught the 12 un-fetched
  northern cells being shipped as if complete.
- **Ground-series selection got a 180-day minimum floor** so QA can't silently
  pick a near-empty candidate.

---

## 10. Status

| Item | State |
|---|---|
| Source catalog + validation | ✅ complete |
| Standards module + citations | ✅ complete |
| Fetch scripts (OpenAQ, AirNow, Zenodo, Open-Meteo) | ✅ complete |
| Dataset builder + data dictionary | ✅ complete |
| Real pipeline run on live data | ✅ complete (2° grid) |
| 4-axis QA layer + committed report | ✅ complete — 0 FAIL |
| Folium map | ✅ complete |
| kepler.gl exports + load guide | ✅ complete |
| Test suite | ✅ 72 passing |
| 1.0° grid re-fetch + 12 northern cells | ⏳ deferred — needs a fresh Open-Meteo quota day |
| Zenodo `.rar` extraction | ⏳ deferred — needs `7z`/`unrar` on the host |
| Sentinel-5P / CAMS-EAC4 automation | ⏳ documented only, by design |
| Polygon/choropleth kepler layer | ⏳ open item (§7) |

---

## 11. Licensing

Per-source licences and the CC BY 4.0 attribution lines for OpenAQ, Open-Meteo
(CAMS/ERA5) and the Zenodo archive are in [`README.md` §7](../README.md).
Grade-C networks with unclear terms (Kyrgyzhydromet, MoveGreen, AirKaz) require
explicit permission before redistributing raw data.
