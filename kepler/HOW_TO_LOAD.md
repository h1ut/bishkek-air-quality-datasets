# Central Asia air quality → kepler.gl

## Fastest: one file, one drag

1. Open https://kepler.gl/demo
2. Drag **`kepler/ca_air_quality_map.json`** onto the map.
   Data + layer + colour scale + time filter load together.
3. Press ▶ on the time bar (bottom) to animate 2021‑01‑01 → 2025‑12‑31.
4. Change the coloured variable: left panel → Layers → "CAMS grid" → **Color** →
   pick any of pm2_5, pm10, carbon_monoxide, nitrogen_dioxide, sulphur_dioxide,
   ozone, aerosol_optical_depth, dust, temperature_2m, relative_humidity_2m,
   wind_speed_10m, wind_direction_10m, surface_pressure, boundary_layer_height.

## Alternative: CSV (if you want to build layers yourself)

Drag **`kepler/ca_air_quality_grid.csv`** onto kepler.gl/demo. kepler auto‑creates
a Point layer from `lat`/`lon`. Then: Filters → + → field `date` → drag the
range → the time slider appears.

## What's in the dataset

- Grid: CAMS air‑quality (8 pollutants/aerosol) + ERA5 meteorology (6 vars),
  **daily**, **2021‑01‑01 … 2025‑12‑31**, one row per grid cell per day.
- Spatial: regular grid over the Kyrgyzstan–Kazakhstan–Uzbekistan corridor
  (currently 2° ≈ 220 km spacing / 56 cells; the run in progress upgrades this
  to 1.0° ≈ 55 km / ~210 cells).
- Flags: `dangerous_day` (daily‑mean PM2.5 > 55.4 µg/m³, US EPA AQI "Unhealthy"),
  `exceeds_kg_limit` (> 35 µg/m³, Kyrgyz ПДКсс), `sparse` (thin day).
- `*_max` and `n_hours_*` columns are dropped here for a lean kepler file; the
  full dataset is `dataset/grid_daily.parquet`.

## Known limitation

The CAMS pollutant archive on Open‑Meteo begins **2022‑08‑04** — pollutant
columns are blank before that date; the ERA5 meteorology covers the full
2021‑2025. Ground stations (OpenAQ + US Embassy) will arrive as a second
dataset (`ca_air_quality_stations.csv`) once the live fetch finishes.
