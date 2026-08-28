# Loading the data into kepler.gl

Go to https://kepler.gl/demo and drag each file in.

## 1. Monitoring stations — `stations_kepler.csv`
- Layer type: **Point**
- Lat: `latitude`, Lon: `longitude`
- Colour by: `quality_grade` (A/B/C) or `network`
- Use for: where the ground truth is, network coverage.

## 2. Region-wide pollutant grid over time — `grid_daily_long.parquet`
  (kepler reads Parquet; if your build lacks it, export CSV from the same file)
- Layer type: **Point** (or **Grid**/**Hexbin** aggregation off)
- Lat: `lat`, Lon: `lon`
- Filter: add a filter on `variable`, pick one (e.g. `pm2_5`)
- Time: add a filter on `date` → kepler shows the time-playback slider
- Colour by: `value`, scale `quantile`
- Note: the gridded pollutant variables (pm2_5, pm10, so2, no2, co, o3, aerosol_optical_depth, dust) only have values from 2022-08-04 onward — the CAMS air-quality archive start; the meteorology variables (temperature_2m, etc.) cover 2021-01-01 onward.
- Use for: scrub 2021–2025, watch winter build-ups across the region.

## 3. Modelling dataset (wide) — `dataset/grid_daily.parquet`
- Same lat/lon; every variable is its own column plus `dangerous_day`.
- Colour by `dangerous_day` for a quick "how often is each cell over 55.4" view
  after aggregating by cell.

## 4. Emissions grid — from Zenodo 12720883 `bishkek_gridded_emissions_2018`
- After extracting the archive, load the shapefile/CSV.
- Layer type: **Polygon** (grid cells) or **Point** (cell centroids)
- Colour by the pollutant column (PM2.5, SO2, NO2, CO...).
