# QA layer, threshold standards, and verified deliverables — Design

Date: 2026-08-29
Status: Draft for user review
Branch: feature/ca-air-quality-datasets (continues the dataset pipeline)
Predecessor spec: docs/superpowers/specs/2026-08-28-central-asia-air-quality-datasets-design.md

## 1. Purpose and scope

Three additions on top of the existing pipeline:

1. **A single source of truth for air-quality thresholds** — `catalog/standards.csv`
   with US EPA and Kyrgyz values only, cited. `build_dataset` reads thresholds
   from it instead of hard-coded literals.
2. **A data-quality (QA) layer** — `qa/` — that verifies the produced datasets
   on four axes (physical plausibility + completeness; cross-source agreement;
   correspondence with published numbers; structural correctness) and emits a
   committed `qa/QA_REPORT.md`. QA never modifies data.
3. **A real, budgeted full-pipeline run** producing verified final deliverables:
   non-empty ground dataset, a regional model grid, a **finished interactive
   map** rebuilt from the real data, refreshed kepler exports, and the QA report.

Hard constraints from the user:
- **Do not exhaust API rate limits / daily quotas.** Open-Meteo daily quota
  already broke a grid run in the predecessor work; AirNow has a 500 req/hour cap.
- **The map must be finished and correct at the end** — rebuilt from real data,
  all layers present, station popups populated, CAMS snapshot layer non-empty.

## 2. Thresholds

### 2.1 catalog/standards.csv (new)

Columns: `standard_id, authority, pollutant, averaging_period, value_ug_m3,
kind, citation, url, notes`.

`kind` in: `alert` (health-action category boundary, not a legal limit),
`limit` (regulatory maximum permissible concentration).

Rows — **US EPA and Kyrgyzstan only**. No WHO, no EU, no sensitivity thresholds.

| standard_id | authority | pollutant | period | value ug/m3 | kind |
|---|---|---|---|---|---|
| epa_aqi_unhealthy_pm25 | US EPA | pm2_5 | 24h | 55.4 | alert |
| kg_mpc_daily_pm25 | Kyrgyzstan (PP KR No.201, 2016, poz. 613) | pm2_5 | 24h | 35 | limit |
| kg_mpc_annual_pm25 | Kyrgyzstan (PP KR No.201) | pm2_5 | 1y | 25 | limit |
| kg_mpc_daily_pm10 | Kyrgyzstan (PP KR No.201, poz. 612) | pm10 | 24h | 60 | limit |
| kg_mpc_annual_pm10 | Kyrgyzstan (PP KR No.201) | pm10 | 1y | 40 | limit |
| kg_mpc_daily_so2 | Kyrgyzstan (PP KR No.201, poz. 463) | sulphur_dioxide | 24h | 50 | limit |
| kg_mpc_daily_no2 | Kyrgyzstan (PP KR No.201, poz. 4) | nitrogen_dioxide | 24h | 40 | limit |
| kg_mpc_daily_no  | Kyrgyzstan (PP KR No.201) | nitrogen_oxide | 24h | 60 | limit |
| kg_mpc_daily_co  | Kyrgyzstan (PP KR No.201, poz. 521) | carbon_monoxide | 24h | 3000 | limit |
| kg_mpc_daily_o3  | Kyrgyzstan (PP KR No.201, poz. 387) | ozone | 24h | 30 | limit |
| kg_mpc_daily_nh3 | Kyrgyzstan (PP KR No.201, poz. 103) | ammonia | 24h | 40 | limit |
| kg_mpc_daily_hcoh | Kyrgyzstan (PP KR No.201, poz. 541) | formaldehyde | 24h | 3 | limit |
| kg_mpc_daily_hcn | Kyrgyzstan (PP KR No.201) | hydrogen_cyanide | 24h | 1 | limit |

`citation` carries the decree name + position; `url` the FAOLEX PDF
(https://faolex.fao.org/docs/pdf/kyr179875.pdf) for the Kyrgyz rows and the
EPA AQI technical assistance document for the EPA row.

Primary "dangerous day" for the paper's headline metrics = daily-mean pm2_5 >
`epa_aqi_unhealthy_pm25` (55.4). Secondary national-limit exceedance = >
`kg_mpc_daily_pm25` (35). These two only.

### 2.2 build_dataset.py rewire

- Add `load_standards(path="catalog/standards.csv") -> dict[str, float]` mapping
  `standard_id -> value_ug_m3`.
- `build_grid_dataset` and any station-side flagging read
  `STD["epa_aqi_unhealthy_pm25"]` and `STD["kg_mpc_daily_pm25"]` instead of the
  literals `55.4` / `35`. Flag columns keep their current names
  (`dangerous_day`, `exceeds_kg_limit`) and their current nullable-boolean
  semantics (NA where pm2_5 is null). No rename.
- `_DICT` caveats updated: `dangerous_day` cites "US EPA AQI Unhealthy lower
  bound (24-h PM2.5 55.4 ug/m3); NA where pm2_5 is missing";
  `exceeds_kg_limit` cites "Kyrgyz PDK srednesutochnaya, PP KR No.201 (2016)
  poz. 613, 35 ug/m3; NA where pm2_5 is missing".
- If `catalog/standards.csv` is absent or a needed id is missing, raise a clear
  error naming the missing id — never silently fall back to a literal.

## 3. QA layer (`qa/`)

```
qa/
  __init__.py
  loaders.py        # read dataset/*.{csv,parquet}, data/processed/*, standards.csv; return typed frames
  thresholds.yaml   # WARN/FAIL bounds for the CHECKS themselves (not pollutant limits)
  reference_values.yaml
  checks/
    __init__.py
    plausibility.py
    agreement.py
    reference.py
    structure.py
  report.py         # run all checks against real data -> qa/QA_REPORT.md
  QA_REPORT.md      # generated, committed
tests/
  test_data_quality.py
  fixtures/qa/       # small crafted csv/parquet per check
```

Every check function has the signature `check(ctx) -> list[Finding]` where
`Finding` is a dataclass with fields `check_id`, `level` (one of PASS / WARN /
FAIL / INFO), `summary`, and optional `table` (markdown string). `ctx` bundles
the loaded frames + `thresholds.yaml` + the standards map. Checks read; they
never write to `dataset/` or `data/`.

### 3.1 plausibility.py

- **Range check** per variable: physical bounds (pm2_5 in [0,1000], pm10 in
  [0,2000], so2/no2 in [0,5000], co in [0,100000] ug/m3, o3 in [0,1000], RH in
  [0,100], surface_pressure in [600,1050] hPa given Bishkek ~800 m and grid
  terrain, wind_speed in [0,60] m/s, wind_direction in [0,360], temperature in
  [-45,50] C, boundary_layer_height in [0,5000] m, aerosol_optical_depth in
  [0,5], dust in [0,2000]). FAIL if > 0.1% of non-null values are outside;
  WARN if any.
- **Completeness**: for each variable, % of expected daily rows present AND
  non-null, split by (a) full calendar year and (b) heating season
  (Nov 1 - Mar 31). Emit a table year x variable. WARN below
  `thresholds.completeness.warn_pct` (default 80), FAIL below
  `fail_pct` (default 50), EXCEPT variables/periods legitimately empty
  (CAMS gases before 2022-08-04) which are reported as INFO, not WARN.
- **Duplicate keys**: `(cell_id, date)` in grid, `(station_key, date)` in
  stations must be unique. FAIL on any duplicate; list them.
- **Date gaps**: within each cell/station, sorted dates; report count and the
  largest gap. WARN if a gap > `thresholds.gap.warn_days` (default 7) inside a
  period that should have data.
- **CAMS boundary**: assert gases (the 8 AQ vars) are ~all-null before
  2022-08-04 and mostly-present after, at the Bishkek grid cell. Reports the
  observed first non-null date per gas. FAIL if a gas is present before the
  boundary (would mean a merge/source bug) or absent for a long stretch after.

### 3.2 agreement.py

For Bishkek only. Build daily-aligned pm2_5 series from every available source:
CAMS grid (nearest cell to 42.8746, 74.5698), AirNow US Embassy, OpenAQ Bishkek,
Zenodo US Embassy archive. For each unordered pair with >= 30 overlapping days:
N, Pearson r, mean bias (`a - b`), RMSE, MAE. Emit one table.

Expectations encoded as check levels:
- Two ground sources (OpenAQ vs AirNow vs Zenodo, pairwise): WARN if r <
  `thresholds.agreement.ground_r_warn` (0.8) or |bias| >
  `ground_bias_warn` (10 ug/m3); FAIL if r < 0.5 (indicates station-matching
  or unit bug).
- Model vs any ground: INFO with the numbers; WARN only if r <
  `model_r_warn` (0.4) or the model *over*-estimates the mean (bias > 0) —
  the known failure mode is under-estimation of peaks, so a positive bias is
  the surprising one worth flagging.
- Also report, for the overlapping window, the count of days each source calls
  "dangerous" (> 55.4) and "> 35", side by side — this quantifies the grid's
  undercount directly.

### 3.3 reference.py

Published anchors live in `qa/reference_values.yaml` with citations. Checks:

- **Annual mean pm2_5, Bishkek ground series**: compare each year's mean to the
  published band `bishkek_annual_pm25: {low: 30, high: 70, cite: "WHO/IQAir/
  World Bank ~40-50 ug/m3 for the Bishkek airshed"}`. WARN outside [low, high];
  INFO with the value inside.
- **Exceedance days per heating season, Bishkek ground series**: count days >
  55.4 and days > 35, per heating season. Compare the > 35 count to
  `isaev_table4_exceed35: {low: 52, high: 93, cite: "Isaev et al. 2022, AAQR,
  Table 4"}`. WARN if a season with adequate coverage falls well outside; INFO
  otherwise. Emit the per-season table.
- **Seasonal cycle**: monthly mean pm2_5; assert winter (Dec-Feb) mean >=
  `thresholds.seasonality.min_winter_summer_ratio` (2.0) x summer (Jun-Aug)
  mean, for the ground series AND the grid Bishkek cell. WARN if the grid
  fails the ratio (muted seasonality is expected but not flatness); FAIL if
  the ground series fails (would indicate a date or sign bug).
- **Model-vs-ground gap, explicit**: for the grid Bishkek cell, count
  "dangerous" days per season and state the gap vs the ground count and vs
  Isaev. This is INFO — it documents the known limitation numerically, not a
  failure.

### 3.4 structure.py

- **Schema**: expected columns + dtypes present in `dataset/stations_daily.csv`
  and `dataset/grid_daily.parquet` (a fixed manifest in `qa/loaders.py`).
- **Key uniqueness**: `(cell_id, date)` / `(station_key, date)` — canonical
  here (plausibility also reports it; structure asserts it).
- **Flag consistency**: for non-null pm2_5, `dangerous_day == (pm2_5 >
  STD.epa_aqi_unhealthy_pm25)` and `exceeds_kg_limit == (pm2_5 >
  STD.kg_mpc_daily_pm25)`; where pm2_5 is null, both flags are NA. FAIL on
  any mismatch.
- **n_hours / sparse**: every `n_hours_<var>` in [0, 24] or NA; `sparse`
  is True iff any non-NA `n_hours_<var>` < 18.
- **Dictionary coverage**: every column of both datasets appears in
  `dataset/data_dictionary.md`; zero `TODO-REVIEW`.
- **Grid bbox**: all `lat` in [39, 52], all `lon` in [66, 80].
- **kepler long file**: `kepler/grid_daily_long.parquet` melt is consistent —
  variable set is a subset of AQ+WX vars; no row whose `value` is null; every
  `(cell_id, date, variable)` unique.

### 3.5 report.py and QA_REPORT.md

`report.py` loads the real artifacts, runs the 4 modules, writes
`qa/QA_REPORT.md`: a header line (`N PASS / M WARN / K FAIL / J INFO`), then a
section per module with each finding's level, summary, and table. Exit code 0
if no FAIL, 1 if any FAIL (so it can gate CI later). It also writes the run
date and the input file mtimes so a stale report is obvious.

### 3.6 tests/test_data_quality.py

pytest, fixture-based, deterministic. For each check: a crafted tiny frame
that should produce a known Finding level, plus a clean frame that should
produce PASS. Fixtures under `tests/fixtures/qa/`. These test the CHECK LOGIC,
not real data. Target: every check_id has at least one positive (catches the
defect) and one negative (passes clean) test.

## 4. Real pipeline run — API budget and discipline

Keys are in `fetch/config.yaml` (gitignored). The run is done ONCE, cleanly,
and every fetch is disk-cached so any re-run only re-requests misses.

### 4.1 Open-Meteo (no key; limits 10000/day, 5000/hour, 600/min)

- **Grid spacing = 1.0** for this iteration (NOT the config default 0.5).
  Bbox lon 66-80 (15 steps) x lat 39-52 (14 steps) = 210 cells x 2 endpoints
  (air-quality + archive) = **~420 calls**. Points mode ~= 12 calls. Total
  ~= 432 — well under the daily and hourly caps, ~2-3 min at a polite pace.
- 0.5 (~1566 calls) is deferred to a later dedicated run; 1.0 (~55 km) is
  sufficient for a regional context layer and keeps a wide quota margin.
- `_get()` already logs-and-skips on any HTTP error and continues; the cache
  makes a resumed run cheap. The controller runs the grid fetch as a single
  step and does not re-run it once the parquet exists.

### 4.2 OpenAQ (key; free tier ~60 req/min)

- 4 cities, all pollutants, 2021-2025, daily aggregation. Per-sensor requests,
  bounded by station count; well within the minute limit at default pacing.
- OpenAQ already carries the US Embassy Bishkek monitor (provider "AirNow"),
  so it is the primary Bishkek ground source.

### 4.3 AirNow (key; hard limit 500 req/hour)

- `fetch_airnow` issues one request per day -> 1826 requests for the full
  range, which would breach 500/hour if run naively.
- **Mitigation**: the primary Bishkek ground record comes from OpenAQ +
  the Zenodo US Embassy archive. AirNow direct is run ONLY to fill a
  residual 2025 gap if OpenAQ 2025 coverage is thin — at most ~365 requests,
  paced under 450/hour, and skipped entirely if not needed. The controller
  decides after inspecting OpenAQ Bishkek coverage.

### 4.4 Zenodo archive

- Already downloaded and checksum-verified (predecessor Task 5). This
  iteration additionally EXTRACTS `bishkek_monitoring_us.embassy2019-2024.rar`
  and reads `bishkek_monitoring_claritysensor_2021.xlsx` into tidy daily
  pm2_5 for use as a Bishkek ground source and QA cross-check. If no rar
  extractor (`7z` / `unrar` / `bsdtar`) is available on the machine, the step
  is skipped with a logged note and QA proceeds with OpenAQ + AirNow-2025.

### 4.5 Claude session budget

Execution is subagent-driven with a ledger (resumable across a usage-limit
interruption). Implementer model = cheapest tier that fits (haiku for
transcription tasks, sonnet for the QA modules and the pipeline-run task).
No speculative re-runs; the ledger records the real-run outputs so a resumed
session does not repeat fetches.

## 5. Acceptance gates (all must pass before "done")

1. `.venv/Scripts/python -m pytest -q` — all green (existing 27 + new QA tests).
2. `catalog/standards.csv` present; `build_dataset` reads thresholds from it
   (grep shows no `55.4` / `> 35` literal in the flag logic).
3. Real run completed: `dataset/stations_daily.csv` non-empty and covering
   Bishkek across the CAMS-independent range; `dataset/grid_daily.parquet` at
   1.0 with ~210 cells; `data_dictionary.md` zero `TODO-REVIEW`.
4. **Finished map**: `map/bishkek_air_quality_map.html` rebuilt from the real
   data; opened and verified to contain the six base layers + LayerControl +
   at least one non-empty CAMS grid snapshot layer; station markers carry
   populated popups (operator, pollutants, period, source URL); no
   `pm2_5=nan` markers. File committed.
5. `qa/QA_REPORT.md` committed; no `FAIL` findings, OR every `FAIL` is
   adjudicated in the report with an explicit, cited reason it is acceptable
   (e.g. CAMS pre-2022-08-04 gap).
6. `kepler/stations_kepler.csv` and `kepler/grid_daily_long.parquet`
   regenerated from the real data; `kepler_layers.md` still accurate.
7. No secret in any tracked file; `git status` clean; `fetch/config.yaml`
   untracked.

## 6. Non-goals

- No modification of measured data: no imputation, interpolation, smoothing,
  outlier removal. Missing stays missing (NaN; flags NA). Implausible values
  are counted and reported, not deleted.
- No WHO or EU thresholds anywhere.
- No 0.5 grid this iteration.
- No Sentinel-5P / CAMS-EAC4 automation.
- QA does not "fix" the dataset; it produces a verdict plus a documented
  exception list. If a layer is unfit, its role is narrowed with an explicit
  note (e.g. a low-coverage season is excluded from evaluation openly), never
  silently patched.

## 7. Execution phases

- **Phase A (no external calls)**: `catalog/standards.csv`; `build_dataset`
  rewire + tests; `qa/` module (loaders, 4 check modules, thresholds.yaml,
  reference_values.yaml, report.py) + `tests/test_data_quality.py` on
  fixtures. Fully testable offline.
- **Phase B (real run, keys in place)**: run fetch_openaq, fetch_open_meteo
  (points, then grid at 1.0), extract+parse Zenodo, optional AirNow-2025
  gap-fill, build_dataset, build_map, build_kepler. Then `qa/report.py`
  against the real data -> `QA_REPORT.md`. Verify acceptance gates 3-6.
  Commit.
- **Phase C**: final whole-branch review of the Phase A+B diff; fix wave;
  then finishing-a-development-branch.

## 8. Open items to resolve during implementation

- Exact OpenAQ 2025 coverage for Bishkek — determines whether AirNow-2025
  gap-fill runs at all.
- Whether a rar extractor is present on the machine for the Zenodo US Embassy
  archive; fallback is OpenAQ + AirNow-2025.
- The Zenodo Clarity xlsx sheet/column layout (needs a peek to parse into
  daily pm2_5).
- Nearest grid cell to Bishkek at 1.0 spacing (likely 43.0, 75.0) — QA and
  map both need the same choice; centralize it in `qa/loaders.py` and reuse
  in `build_map`.
- Whether `build_map`'s CAMS snapshot should pick the worst grid day (may be
  a summer dust day) or the worst *heating-season* day — pick heating-season
  worst for relevance.
