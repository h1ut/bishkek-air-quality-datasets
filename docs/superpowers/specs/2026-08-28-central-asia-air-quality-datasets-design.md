# Central Asia Air Quality Dataset Collection — Design

Date: 2026-08-28
Status: Approved (expanded scope: ground + CA-wide gridded layer)
Owner: research on next-day PM2.5 prediction in Bishkek

## 1. Purpose

Assemble a verified, reusable collection of air quality and meteorological
data for Bishkek (core) and Central Asia (context), covering 2021-2025, to
support and enrich a machine-learning study that predicts next-day PM2.5 in
Bishkek and evaluates error separately on ordinary vs. dangerous
(>55.4 ug/m3 daily) days.

The collection must:

- Catalog every usable source with an explicit data-quality grade.
- Cover pollutants beyond PM2.5 (PM10, SO2, NO2, CO, O3, BC, plus dust and
  aerosol optical depth) and meteorology (temperature, wind speed and
  direction, relative humidity, surface pressure, boundary-layer height).
- Produce **two datasets**:
  - `stations_daily` — real ground measurements at point stations
    (Bishkek + CA cities), the ground truth.
  - `grid_daily` — a Central-Asia-wide gridded surface of every variable,
    every day 2021-2025, sampled from the CAMS model via Open-Meteo.
- Produce a Folium (Python) layered interactive map: ground-station layers
  plus the gridded pollutant surface.
- Produce flat / long files ready to drag into kepler.gl, including a
  long-format grid file for kepler's time slider.
- Include runnable fetch scripts for the highest-value, low-friction
  sources, each emitting a data-quality report.

Non-goals: building the ML pipeline itself; wrapping every possible source;
full satellite retrieval stacks (Sentinel-5P, CAMS via CDS API are
documented with snippets, not automated); large-scale HTML/PDF scraping
(only targeted gap-fill, only where no API exists).

## 2. Approach

Two layers, one merge.

**Ground layer** — real measurements at points, for truth and validation:

1. OpenAQ v3 API — stations in Bishkek, Almaty, Tashkent, Astana.
2. AirNow API — US Embassy Bishkek reference monitor (PM2.5).
3. Zenodo record 12720883 (Guttikunda 2024) — Bishkek US Embassy 2019-2024,
   Clarity sensor network 2021, meteorology stats, gridded 2018 emissions.

**Gridded layer** — every variable, everywhere in the region:

4. Open-Meteo Air Quality API (CAMS-global) — pm2_5, pm10, carbon_monoxide,
   nitrogen_dioxide, sulphur_dioxide, ozone, aerosol_optical_depth, dust.
5. Open-Meteo Historical Weather API (ERA5) — temperature_2m,
   relative_humidity_2m, wind_speed_10m, wind_direction_10m,
   surface_pressure, boundary_layer_height.

Both 4 and 5 are queried:
- at every ground-station coordinate (for direct model-vs-measurement
  comparison), and
- on a regular grid over the region bounding box.

Neither API needs a key beyond OpenAQ and AirNow. Sentinel-5P TROPOMI and
CAMS EAC4 (CDS API) are documented in the catalog with ready-to-run
snippets and account requirements, not wired as automated fetchers in this
iteration.

### Region and grid

- Region bbox (config, default): lon 66.0-80.0, lat 39.0-48.0 — covers
  Kyrgyzstan, Almaty region, Tashkent, southern Kazakhstan up to Astana is
  outside this box, so Astana is included as an explicit extra point plus a
  small box around it (or bbox north edge raised to 52.0; decided in
  implementation based on call volume).
- Grid spacing (config, default): 0.5 degrees (~40-55 km). At 0.5 deg the
  default box is ~29 x 19 = 551 points. 2021-2025 daily = ~1826 days.
  `grid_daily` ~ 551 * 1826 ~ 1.0M rows, 13+ variable columns.
- One Open-Meteo call per grid point covering the full date range and all
  variables, hourly, aggregated to daily locally. ~551 + ~551 calls total
  (AQ + weather), well within the free non-commercial limit
  (~10k calls/day). Calls are cached to disk so re-runs are cheap.

## 3. Deliverable structure

```
datasets/
  README.md                 Source catalog: access, quality grade A/B/C, ML relevance
  catalog/
    sources.csv             One row per dataset/network (machine-readable)
    stations.geojson        Every monitoring point: network, operator, pollutants, period, lat/lon, precision
    studies.csv             Case studies: DOI, region, data exposed, notes
  map/
    build_map.py            Folium map builder (station layers + gridded surface snapshots)
    bishkek_air_quality_map.html   Rendered output (committed)
  fetch/
    common.py               region bbox, city list, grid builder, date/units helpers,
                            disk cache, hourly->daily aggregation, quality-report writer
    fetch_openaq.py         OpenAQ v3 -> station daily CSVs
    fetch_airnow.py         AirNow -> Bishkek US Embassy PM2.5 daily
    fetch_zenodo_bishkek.py Download + unpack record 12720883
    fetch_open_meteo.py     CAMS AQ + ERA5 weather; mode = points | grid
    build_dataset.py        Merge processed outputs -> master datasets + data dictionary
    config.example.yaml     region bbox, grid spacing, cities, date range, API-key slots
  data/
    raw/                    Downloads and cached API responses (gitignored)
    processed/
      openaq_<city>_daily.csv
      airnow_bishkek_daily.csv
      openmeteo_points_daily.csv
      openmeteo_grid_daily.parquet
      *_quality_report.md
  dataset/
    stations_daily.csv              Master ground dataset (wide: one row per station-date)
    grid_daily.parquet             Master gridded dataset (wide: one row per gridcell-date)
    data_dictionary.md             Every column: source, units, aggregation, caveats
  kepler/
    stations_kepler.csv            Flat station points for kepler.gl
    grid_daily_long.parquet        Long format (gridcell-date-variable-value) for kepler time slider
    kepler_layers.md               Load instructions + suggested layer configs
  requirements.txt
  .gitignore
```

## 4. Component detail

### 4.1 catalog/sources.csv

Columns: `source_id, name, type, operator, access_method, endpoint_or_url,
auth_required, spatial_coverage, pollutants, met_variables, temporal_coverage,
temporal_resolution, license, quality_grade, quality_notes, ml_relevance`.

`type` in: ground_reference, ground_lowcost, ground_network, satellite,
reanalysis, model_output, emission_inventory, study_table, meteorology.

`quality_grade`:
- A — reference-grade or peer-reviewed, documented methods, machine-accessible.
- B — low-cost network or model/reanalysis product; usable with caveats,
  needs bias-awareness or ground validation.
- C — aggregate-only, PDF-only, or approximate; context not modeling input.

Every satellite / reanalysis / model row is at most B and its
`quality_notes` must state "column vs surface" or "model, needs ground
validation" explicitly. The Open-Meteo/CAMS grid is grade B and its row
says so.

### 4.2 catalog/stations.geojson

FeatureCollection of Point features. Properties: `station_id, name, network,
operator, pollutants, met_variables, period_start, period_end, status,
location_precision (exact|approx|city-centroid), access_url, quality_grade,
coord_source, notes`.

Coordinates only from verifiable sources (OpenAQ locations endpoint, AirNow,
published papers, operator pages). Approximate points get
`location_precision != exact` rather than a fabricated precise coordinate.
`coord_source` records where each coordinate came from.

### 4.3 catalog/studies.csv

Columns: `study_id, citation, year, doi_or_url, region, open_access,
data_made_available, variables, method, relevance_notes`.

Seed rows (verified during implementation):
- Guttikunda 2024, "Mapping PM2.5 Sources ... Bishkek" (MDPI Air) + Zenodo 12720883.
- Kulkarni et al. 2023, "Cities of Central Asia: new hotspots of air pollution".
- Kazakhstan PMF/HYSPLIT source apportionment, 2025.
- Dust and fine-aerosol PM2.5 mortality burden in Central Asia, 2025.
- "Air pollution in Bishkek, Kyrgyzstan: driving factors and state response" (PMC12039649).
- Isaev et al., "Impact of Climate Change and Air Pollution Forecasting Using
  ML Techniques in Bishkek" (AAQR, doi:10.4209/aaqr.210336) — the baseline
  this research extends.

### 4.4 fetch/common.py

- `REGION_BBOX`, `GRID_SPACING`, `DATE_START=2021-01-01`, `DATE_END=2025-12-31`
  from config.
- `CITIES`: dict name -> (lat, lon) for Bishkek, Almaty, Tashkent, Astana.
- `build_grid(bbox, spacing) -> list[(lat, lon, cell_id)]`.
- `daterange`, `to_daily(df, how, min_count=18)` — hourly to daily with a
  minimum-hours-present rule so sparse days are flagged not silently averaged.
- `cached_get(url, params)` — GET with disk cache keyed by URL+params
  (JSON under `data/raw/_cache/`), retry/backoff on 429/5xx (3 tries,
  exponential).
- `write_quality_report(name, df, reference=None)` — emits
  `data/processed/<name>_quality_report.md`: row count, columns, date span,
  % missing per variable, count of days failing min_count, duplicate
  timestamps, min/max/percentiles per pollutant, count of physically
  implausible values (negative concentrations, PM2.5 > 1000, RH > 100,
  wind < 0), and if `reference` is given, Pearson r and mean bias vs it.
- `load_config()` — reads `config.yaml`, falls back to
  `config.example.yaml`; env vars override API keys.

### 4.5 fetch/fetch_openaq.py

- OpenAQ v3, header `X-API-Key` from config/env.
- Per city: GET `/v3/locations` by bbox -> location + sensor ids.
- Per sensor: pull daily aggregate if the endpoint offers it
  (`/v3/sensors/{id}/measurements/daily` or equivalent), else raw
  measurements aggregated locally via `to_daily`.
- Output `data/processed/openaq_<city>_daily.csv` — one row per date,
  columns per pollutant + met var, plus `n_hours_<var>`.
- Quality report per city; Bishkek cross-checks vs the AirNow series.
- Appends proposed station rows to `data/processed/_stations_staging.csv`
  (never writes catalog/stations.geojson directly).

### 4.6 fetch/fetch_airnow.py

- AirNow API, key from config/env.
- Historical observation endpoint for the Bishkek US Embassy monitor
  (site id if exposed, else bbox), PM2.5, hourly -> daily with `n_hours_pm25`.
- Output `data/processed/airnow_bishkek_daily.csv`. This series is the
  reference for cross-checks elsewhere.
- No key configured -> exit cleanly, message pointing at the Zenodo US
  Embassy archive as offline fallback.

### 4.7 fetch/fetch_zenodo_bishkek.py

- Download record 12720883 files via Zenodo REST API
  (`/api/records/12720883`), verify MD5 checksums.
- Unpack monitoring and emissions archives into
  `data/raw/zenodo_12720883/`. `.rar` needs `unrar`/`rarfile`; if missing,
  print the manual step and continue.
- Emit a manifest markdown: each file, size, checksum ok, one-line content
  description. No transformation beyond unpacking.

### 4.8 fetch/fetch_open_meteo.py

- `--mode points` — query every station coordinate from
  `_stations_staging.csv` + `CITIES`.
- `--mode grid` — query every cell from `build_grid`.
- Air Quality API: the 8 pollutant/aerosol variables, `domains=cams_global`,
  full date range, hourly.
- Historical Weather API: the 6 met variables, full date range, hourly.
- Aggregate to daily locally (mean for concentrations and temp/RH/pressure/
  BLH; vector mean for wind direction; also keep daily max for pollutants).
- Outputs:
  - points mode -> `data/processed/openmeteo_points_daily.csv`
  - grid mode  -> `data/processed/openmeteo_grid_daily.parquet`
- Quality report; points-mode Bishkek row cross-checked vs OpenAQ and AirNow
  (this quantifies CAMS bias at Bishkek — a headline number for the writeup).

### 4.9 fetch/build_dataset.py

- Reads all `data/processed/*` outputs.
- `stations_daily.csv` — union of OpenAQ + AirNow (+ Zenodo US Embassy where
  it extends the record), one row per `station_id, date`, wide columns per
  variable, provenance columns (`pm25_source`, ...), `n_hours_*` retained.
- `grid_daily.parquet` — `openmeteo_grid_daily` with `cell_id, lat, lon,
  date` keys; wide variable columns; adds `dangerous_day` flag
  (pm2_5_mean > 55.4) and `exceeds_kg_limit` (> 35).
- `data_dictionary.md` — every column: long name, source, units,
  aggregation, min_count rule, known caveats.
- `kepler/grid_daily_long.parquet` — melt to
  `cell_id, lat, lon, date, variable, value`.
- Prints a summary table: rows, date coverage, missing %, dangerous-day
  counts per season for the Bishkek cell and station.

### 4.10 map/build_map.py

- Reads `catalog/stations.geojson`, `catalog/studies.csv`, and
  `dataset/grid_daily.parquet`.
- Folium map centered on Bishkek. `folium.FeatureGroup` per layer, all
  toggleable via `LayerControl`:
  1. Reference monitors (Kyrgyzhydromet ref + US Embassy)
  2. Kyrgyzhydromet Clarity Node-S sensors
  3. MoveGreen / citizen low-cost sensors
  4. CA comparison-city stations (Almaty, Tashkent, Astana)
  5. Study / campaign sites (popup -> DOI + data notes)
  6. Bishkek airshed / 2018 emissions-grid extent (polygon from Zenodo GIS
     if parseable, else documented bbox)
  7. Gridded pollutant surface — CircleMarkers or a raster overlay for the
     grid, coloured by a chosen variable on a chosen date (config: default
     PM2.5 on the single worst Bishkek day in the record). 2-3 snapshot
     dates as separate sub-layers; full time animation is delegated to
     kepler.gl.
- Marker colour by `quality_grade`, icon by `network`. Popup: operator,
  pollutants, period, precision, access URL.
- Writes `map/bishkek_air_quality_map.html`.

### 4.11 kepler/

- `stations_kepler.csv` — `name, latitude, longitude, network, operator,
  pollutants, period_start, period_end, quality_grade`.
- `grid_daily_long.parquet` — long format for kepler's time playback.
- `kepler_layers.md` — for each file: kepler layer type (Point / Grid /
  Polygon), colour-by field, and for the grid the timestamp column + filter
  setup for scrubbing 2021-2025 and switching variable.

## 5. Data flow

```
config.yaml
  -> fetch_openaq / fetch_airnow / fetch_zenodo  -> data/processed/* (+ station staging)
  -> fetch_open_meteo --mode points               -> openmeteo_points_daily.csv
  -> fetch_open_meteo --mode grid                  -> openmeteo_grid_daily.parquet
  -> build_dataset.py -> dataset/stations_daily.csv
                         dataset/grid_daily.parquet
                         dataset/data_dictionary.md
                         kepler/grid_daily_long.parquet

_stations_staging.csv --(hand-checked)--> catalog/stations.geojson
catalog/studies.csv, catalog/stations.geojson, dataset/grid_daily.parquet
  -> map/build_map.py -> map/bishkek_air_quality_map.html
  -> kepler/stations_kepler.csv
```

The catalog GeoJSON is hand-verified from source metadata and the staging
file; fetch scripts propose rows, never overwrite it.

## 6. Error handling

- Fetch scripts: retry/backoff on 429/5xx; one-line failure per
  city/sensor/cell, continue; non-zero exit only if every unit failed.
- Disk cache means an interrupted grid run resumes without re-calling
  succeeded cells.
- Missing API key -> skip that source with an explanatory message and an
  offline-fallback pointer; batch continues.
- Unexpected payload -> raw response dumped to `data/raw/_errors/`.
- Quality report always written, even on partial data.

## 7. Testing

- `common.py`: unit tests for `build_grid` (corner/spacing/count),
  `to_daily` (min_count boundary, daily grouping), `write_quality_report`
  (implausible-value counts, bias/r on synthetic series), `cached_get`
  (cache hit skips network, backoff on injected 429), config + env override.
- Each fetch script: one test against a saved fixture JSON (no live
  network) asserting the tidy daily schema and that a quality report is
  produced.
- `build_dataset.py`: fixture processed files -> assert master schema,
  `dangerous_day` flag correctness, long-format melt shape, data dictionary
  lists every column.
- `build_map.py`: fixture GeoJSON + studies + tiny grid -> assert HTML
  written, one FeatureGroup per expected layer, LayerControl present.
- Manual acceptance: run points mode + a coarse grid (spacing 2.0) for a
  60-day window; open the HTML map; load `grid_daily_long.parquet` and
  `stations_kepler.csv` into kepler.gl and scrub the time slider.

## 8. Dependencies

`requirements.txt`: requests, pandas, pyarrow, folium, PyYAML, pytest.
Optional (documented, not imported by default): rarfile + system `unrar`
for the Zenodo `.rar` archives.

## 9. Open items to resolve during implementation

- Astana: raise region bbox north edge vs. treat as an extra point + small
  box — decide by total grid-call count at 0.5 deg.
- AirNow historical endpoint shape and whether the Bishkek monitor is
  exposed by site id or only bbox.
- OpenAQ v3 daily-aggregate endpoint availability for these sensors.
- Open-Meteo: confirm 2021 is inside the CAMS Air Quality archive (it
  historically starts ~2022 for some domains; if so, gases before the
  archive start come only from reanalysis and the catalog notes the gap).
- Zenodo GIS archive: clean airshed polygon vs. raster only; fallback bbox.
- Published coordinates for Kyrgyzhydromet Clarity and MoveGreen sensors —
  how many are individually available vs. live-map only.
- Final `grid_daily.parquet` size and whether to ship it in-repo or provide
  a generator + small sample.
```
