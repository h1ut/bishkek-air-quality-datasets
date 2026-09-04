# Central Asia air quality → kepler.gl

Open https://kepler.gl/demo and drop ONE of these onto the page.

## If the big file gave a white screen — use these (light, fast)

| file | rows | what |
|---|---|---|
| **`ca_air_quality_monthly_map.json`** | 3 360 | **best first try.** One drag: data + point layer + colour + time slider, all preconfigured. Monthly means, 0.5 MB. Loads instantly. |
| `ca_air_quality_monthly.csv` | 3 360 | same monthly data as a plain CSV (0.4 MB). Drag it, kepler auto-builds a Point layer from `lat`/`lon`; then Filters → + → `date` for the time slider. |
| `ca_air_quality_daily_2022plus.csv` | 69 776 | full **daily** detail, but only the pollutant era (2022‑08‑04 → 2025‑12‑31, 8.5 MB). CSV, robust parser. Add the `date` filter yourself. |

## Full-detail options (heavier — only on a machine with RAM to spare)

| file | rows | note |
|---|---|---|
| `ca_air_quality_grid.csv` | 102 256 | daily, full 2021‑2025 (22 MB). Pollutant columns blank before 2022‑08‑04. |
| `ca_air_quality_map.json` | 102 256 | one-drag daily map, 26 MB — this is the one that can white-screen a weak laptop. |

## Using it

- Press **▶** on the time bar (bottom) → animation across the date range.
- Change the coloured variable: left panel → **Layers** → the grid layer → **Color** →
  pick pm2_5 / pm10 / carbon_monoxide / nitrogen_dioxide / sulphur_dioxide / ozone /
  aerosol_optical_depth / dust / temperature_2m / relative_humidity_2m /
  wind_speed_10m / wind_direction_10m / surface_pressure / boundary_layer_height.
- If a load fails: open the browser console (F12 → Console) — a red error line there
  says exactly what kepler choked on; send me that line.

## Contents

CAMS air quality (8 pollutants/aerosol) + ERA5 meteorology (6 vars), one row per
grid cell per period, over the Kyrgyzstan–Kazakhstan–Uzbekistan corridor.
Currently a 2° grid (56 cells); the run in progress upgrades it to 1.0° (~210
cells) and adds ground stations. CAMS pollutants start 2022‑08‑04; ERA5 met
covers all of 2021‑2025.
