# Central Asia air quality → kepler.gl

Open https://kepler.gl/demo.

## Recommended: drag the 3 CSVs, then the config (full detail, robust)

1. Drag **`ca_air_quality_grid.csv`**  (daily grid, all 14 CAMS+ERA5 variables, 2021‑2025, ~22 MB)
2. Drag **`ca_air_quality_stations.csv`**  (real OpenAQ daily PM2.5/PM10/O3 for Bishkek, Almaty, Tashkent, Astana)
3. Drag **`ca_air_quality_sensors.csv`**  (~290 individual sensor locations — AirGradient / Clarity / AirNow / StateAir)
4. Drag **`kepler_config.json`**  → applies the 3 layers, colour scales, and time sliders.
   (kepler applies a config dropped after the data. If it doesn't, build layers by hand — kepler auto-detects `lat`/`lon`; add Filters → `date` for the time slider.)

CSV is streamed by kepler and parses reliably even on a modest laptop.

## One file (needs a machine with some RAM)

**`ca_air_quality_map.json`** — all 3 datasets + config in one drag (~28 MB). If it
white‑screens, use the CSV route above instead.

## Using it

- ▶ on the time bar animates 2021‑2025.
- Change the coloured variable: Layers → a layer → **Color** → field. Grid has all 14:
  pm2_5, pm10, carbon_monoxide, nitrogen_dioxide, sulphur_dioxide, ozone,
  aerosol_optical_depth, dust, temperature_2m, relative_humidity_2m,
  wind_speed_10m, wind_direction_10m, surface_pressure, boundary_layer_height.
- The "sensors" layer is off by default — turn it on (eye icon) to see every
  discovered station location.

## What's real here

- **Grid**: CAMS air quality + ERA5 meteorology, daily, one row per grid cell per
  day. 2° spacing / 56 cells this iteration (1.0° / ~210 cells is quota‑blocked on
  Open‑Meteo's free tier — deferred to a fresh‑quota run). CAMS pollutants start
  **2022‑08‑04**; ERA5 meteorology covers all of 2021‑2025.
- **Stations**: live OpenAQ daily series — Bishkek 1237 days (mean PM2.5 ≈ 29,
  max 436), Almaty 1227 (mean 34), Tashkent 511 (mean 49), Astana 389 (mean 31).
- **Sensors**: 296 point locations OpenAQ knows in the region (163 AirGradient,
  128 Clarity, 3 AirNow, 2 StateAir).
- Flags: `dangerous_day` (>55.4 µg/m³, US EPA AQI "Unhealthy"), `exceeds_kg_limit`
  (>35, Kyrgyz ПДКсс).
