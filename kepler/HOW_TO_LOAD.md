# Central Asia air quality → kepler.gl

First: `.venv/Scripts/python -m kepler.build_kepler_map` (regenerates the files
below from `dataset/`). It writes `ca_air_quality_grid.csv`,
`ca_air_quality_stations.csv`, `ca_air_quality_sensors.csv` (all gitignored,
bulky), plus the committed `kepler_config.json` and a small
`ca_air_quality_styling.json`.

kepler.gl/demo reads the CSVs fine; the big embedded‑JSON does not. So:

## Load (CSV route — works)

1. Open https://kepler.gl/demo
2. Drag **`ca_air_quality_grid.csv`**   → daily grid, all 14 CAMS+ERA5 variables, 2021‑2025
3. Drag **`ca_air_quality_stations.csv`**   → real OpenAQ/AirNow daily PM2.5/PM10/O3, 5 city keys
4. Drag **`ca_air_quality_sensors.csv`**   → ~290 sensor locations
5. Drag **`ca_air_quality_styling.json`** (~400 KB)   → applies colours + the time sliders to
   all three layers. It only carries the styling (plus the station/sensor rows embedded);
   it binds to the CSV datasets by name, so it must go in **after** the CSVs.

If step 5 errors, skip it and set the map up by hand — 6 clicks:

- Each layer is auto‑created from `lat`/`lon`. For the grid layer: **Color** → field
  `pm2_5`, scale `quantile`.
- **Filters** (left panel) → **+ Add Filter** → dataset `ca_air_quality_grid`, field
  `date` → the time bar appears at the bottom. Repeat for `ca_air_quality_stations`.
- Press **▶** on the time bar to animate 2021‑2025.

## Change the mapped variable

Layers → the layer → **Color** → field. The grid has all 14:
pm2_5, pm10, carbon_monoxide, nitrogen_dioxide, sulphur_dioxide, ozone,
aerosol_optical_depth, dust, temperature_2m, relative_humidity_2m,
wind_speed_10m, wind_direction_10m, surface_pressure, boundary_layer_height.

## What's in it

- **Grid** — CAMS air quality + ERA5 meteorology, daily, one row per grid cell per
  day. 2° spacing / 56 cells (1.0° is Open‑Meteo quota‑blocked — deferred). CAMS
  pollutants start **2022‑08‑04**; ERA5 meteorology covers all of 2021‑2025.
  Note: 12 of the 56 cells (latitudes 49° and 51°) carry **no CAMS pollutants at
  all** — the grid fetch was truncated by the free‑tier daily quota
  (`qa` check `plausibility.cell_coverage`).
- **Stations** — live OpenAQ/AirNow daily series with city coordinates joined in:
  Bishkek, Almaty, Tashkent, Astana, plus the US Embassy key. Note: OpenAQ has a
  2021‑2023 hole for Bishkek.
- **Sensors** — discovered sensor point locations (AirGradient, Clarity, AirNow,
  StateAir), filtered to lat 35‑56 / lon 60‑85.
- Flags: `dangerous_day` (>55.4 µg/m³, US EPA AQI "Unhealthy"), `exceeds_kg_limit`
  (>35, Kyrgyz ПДКсс).
