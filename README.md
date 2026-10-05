# Central Asia Air Quality Dataset Collection

A verified, reusable collection of air-quality and meteorological data for
**Bishkek** (core) and **Central Asia** (context), covering **2021–2025**, built to
support and enrich a machine-learning study that predicts **next-day PM2.5 in
Bishkek** and evaluates model error separately on ordinary days versus
*dangerous* days (daily-mean PM2.5 > 55.4 µg/m³, the US EPA "Unhealthy"
threshold). The collection catalogs every usable source with an explicit
A/B/C data-quality grade, produces two analysis-ready datasets (a ground-truth
station table and a Central-Asia-wide gridded surface), a layered Folium map,
kepler.gl exports, and a per-source quality report for every fetch script. It
deliberately does **not** build the ML pipeline itself, and it documents rather
than automates the heavy satellite stacks (Sentinel-5P, CAMS-EAC4).

> **Full project documentation** — what was built, how it maps to the research
> questions (RQ1–RQ3), the QA results and the engineering log:
> [`docs/PROJECT_DOCUMENTATION.md`](docs/PROJECT_DOCUMENTATION.md).

> **ML-ready dataset & data audit (2026-10).** A full audit of the ground-truth series found
> critical problems in the data this collection originally produced (a foreign stream interleaved in
> the US Embassy feed 2023-03-16 → 2025-01-16, `-999` sentinels averaged into daily means, UTC
> instead of local days, a duplicated feed with a shifting clock offset, and an OpenAQ fetcher that
> silently returned only the first 366 days per sensor). Read
> [`DATA_AUDIT_REPORT.md`](DATA_AUDIT_REPORT.md) before using anything below. The corrected,
> leakage-tested dataset with chronological train/validation/test splits is built by the `prep/`
> pipeline into [`data/prepared/`](data/prepared/) (`python -m prep.run_all [--fetch]`); every
> column is documented in [`data/prepared/FEATURE_DICTIONARY.md`](data/prepared/FEATURE_DICTIONARY.md).
> Sections 4–5 below describe the original collection and are kept for history.

---

## 1. What this is

The research this feeds extends Isaev et al. (2022, *Aerosol Air Qual. Res.*,
[doi:10.4209/aaqr.210336](https://doi.org/10.4209/aaqr.210336)), the first
published ML forecast of Bishkek air pollution. That baseline reported a single
averaged error with no breakdown by concentration and used no lagged PM2.5
features. To do better you need (a) a clean ground-truth PM2.5 series for
Bishkek, (b) multi-pollutant and meteorological context — especially
boundary-layer height, which drives the winter inversions that trap smoke over
the city — and (c) a spatial/regional view so transported dust and
cross-border smoke can be reasoned about. This repository assembles all three
from open sources, grades each one, and merges them into two datasets plus a
map. Everything here is data collection, cataloging and QA; the forecasting
model lives in a separate project.

---

## 2. Quick start

```bash
# 1. Environment (Python 3.14; a .venv is already provisioned in this repo)
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt      # Windows
# .venv/bin/python -m pip install -r requirements.txt        # POSIX

# 2. Config — copy the example and (optionally) add the two free API keys
cp fetch/config.example.yaml fetch/config.yaml
```

`fetch/config.yaml` is gitignored. It holds the region bounding box, grid
spacing, city coordinates, date range and two key slots. You can also supply
the keys as environment variables `OPENAQ_API_KEY` / `AIRNOW_API_KEY`, which
take precedence over the file.

**Where to get the two free keys** (neither is needed for Open-Meteo, Zenodo,
or the build/map/kepler steps):

| Key | Register at | Used by |
|---|---|---|
| `OPENAQ_API_KEY` | <https://explore.openaq.org/register> | `fetch_openaq.py` |
| `AIRNOW_API_KEY` | <https://docs.airnowapi.org/account/request/> | `fetch_airnow.py` |

**Run the pipeline** from the repo root, in order:

```bash
.venv/Scripts/python -m fetch.fetch_openaq                       # ground: OpenAQ v3 (needs key)
.venv/Scripts/python -m fetch.fetch_airnow                       # ground: US Embassy Bishkek (needs key)
.venv/Scripts/python -m fetch.fetch_zenodo_bishkek               # ground: Zenodo 12720883 archive
.venv/Scripts/python -m fetch.fetch_open_meteo --mode points     # model: CAMS+ERA5 at station coords
.venv/Scripts/python -m fetch.fetch_open_meteo --mode grid       # model: CAMS+ERA5 on the region grid
.venv/Scripts/python -m fetch.build_dataset                      # merge -> dataset/ + kepler/ + data dictionary
.venv/Scripts/python -m map.build_map                            # -> map/bishkek_air_quality_map.html
.venv/Scripts/python -m kepler.build_kepler                      # -> kepler/stations_kepler.csv
```

Every fetch script writes to `data/processed/` (gitignored) plus a
`*_quality_report.md` next to its output. All HTTP responses are cached under
`data/raw/_cache/` (30-day TTL), so re-runs are cheap and offline-friendly.

### Grid spacing and the Open-Meteo call budget

`--mode grid` issues **one Open-Meteo air-quality call and one weather call per
grid cell**, each covering the full 2021–2025 range. The region bbox is
lon 66–80 / lat 39–52.

| `--grid-spacing` | Cells | Calls (AQ + WX) | Notes |
|---|---|---|---|
| `0.5` | ~780 (29 × 27) | ~1 560 | Supported (`--grid-spacing 0.5`); slow — Open-Meteo's public API rate-limits large sweeps and enforces a ~10 000 calls/day cap. Expect the run to span more than one calendar day. |
| `1.0` | 210 (15 × 14) | ~420 | Usable when the daily quota is fresh. |
| `2.0` | 56 (8 × 7) | 112 | Robust fallback; the shipped `dataset/grid_daily.parquet` was built at this spacing. |

Pass the spacing explicitly, e.g.
`.venv/Scripts/python -m fetch.fetch_open_meteo --mode grid --grid-spacing 2.0`.
On an HTTP failure for a single cell the fetcher logs and skips that cell so the
sweep continues; the resulting parquet simply has fewer cells.

---

## 3. Source catalog

The machine-readable catalog is [`catalog/sources.csv`](catalog/sources.csv)
(12 rows, schema-validated by `catalog/validate_catalog.py`). Companion files:
[`catalog/studies.csv`](catalog/studies.csv) (8 case studies) and
[`catalog/stations.geojson`](catalog/stations.geojson) (monitoring points with
`location_precision` + `coord_source`).

| source_id | name | type | operator | access_method | auth_required | temporal_coverage | temporal_resolution | license | quality_grade |
|---|---|---|---|---|---|---|---|---|---|
| openaq | OpenAQ | ground_network | OpenAQ Inc | REST API v3 | yes (free key) | 2016-present (varies by station) | hourly | CC BY 4.0 | B |
| airnow_bishkek | AirNow - US Embassy Bishkek | ground_reference | US EPA / US Dept of State | REST API | yes (free key) | 2019-10 to present | hourly | US Gov public domain | A |
| zenodo_12720883 | Guttikunda 2024 Bishkek inventory + monitoring | emission_inventory | Sarath Guttikunda (UrbanEmissions.info) | File download | no | 2018 emissions; 2019-2024 monitoring | annual grid + daily monitoring | CC BY 4.0 | B |
| kyrgyzhydromet | Kyrgyzhydromet air monitoring | ground_network | Agency for Hydrometeorology (MoES KR) | Web map + PDF bulletins | no | quarterly bulletins; live map | quarterly (PDF) / live | Government - terms unclear | C |
| movegreen_aqkg | MoveGreen AQ.kg citizen network | ground_lowcost | MoveGreen (NGO) | App / web | unknown | ~2019-present | 20-minute | Unknown - contact NGO | C |
| airkaz | AirKaz.org | ground_lowcost | AirKaz.org | REST API | unknown | 2017-present (Almaty bulk CSV covers Mar 2017-Sep 2020) | hourly | Unknown | C |
| open_meteo_aq | Open-Meteo Air Quality API | model_output | Open-Meteo / Copernicus CAMS | REST API | no | 2022-08-04 to present | hourly | CC BY 4.0 (Open-Meteo) / CAMS licence | B |
| open_meteo_era5 | Open-Meteo Historical Weather (ERA5) | reanalysis | Open-Meteo / ECMWF ERA5 | REST API | no | 1940-present (used from 2021 onward) | hourly | CC BY 4.0 / ERA5 licence | B |
| sentinel5p | Sentinel-5P TROPOMI | satellite | ESA / Copernicus | openEO / GEE / Data Space | yes (free account) | 2018-present | daily overpass | Copernicus free/open | B |
| cams_eac4 | CAMS Global Reanalysis EAC4 | reanalysis | ECMWF / Copernicus ADS | CDS API (cdsapi) | yes (free account) | 2003-present | 3-hourly | Copernicus/Licence to use Copernicus Products | B |
| who_aap_db | WHO Ambient Air Quality Database | study_table | World Health Organization | File download | no | updated ~2024 | annual | WHO terms | C |
| worldbank_bishkek_2023 | World Bank Air Quality Analysis for Bishkek (2023) | study_table | World Bank | Report + figures | no | 2019-2022 | report | World Bank open access | C |

### Measurements vs model output

**Direct measurements (instruments on the ground):**

- **openaq** — programmatic aggregator of reference and low-cost monitors in
  Bishkek, Almaty, Tashkent, Astana. *ML relevance:* the primary automated
  source of lagged-PM2.5 features and multi-pollutant context. *Grade **B*** —
  it mixes reference-grade and low-cost instruments and the instrument mix
  varies per station, so per-station provenance must be checked before use.
- **airnow_bishkek** — the US Embassy Bishkek reference monitor (PM2.5 only),
  an EPA-approved FEM instrument. *ML relevance:* the ground-truth target and
  the yardstick for validating the CAMS grid over Bishkek. *Grade **A*** —
  reference-grade QA/QC; the only caveats are that it is a single point and has
  occasional data gaps.
- **zenodo_12720883** (Guttikunda 2024) — a downloadable archive containing the
  US Embassy 2019–2024 series, a Clarity low-cost network (2021), meteorology
  statistics and a gridded 2018 emissions inventory. *ML relevance:* the
  offline fallback for the Bishkek ground record when no API key is available,
  and the emissions grid is a static spatial predictor. *Grade **B*** — the
  monitoring series are solid, but the emissions layer is WRF-CAMx model
  output, not measurement, and the bundle is a periodic research release rather
  than a live feed.
- **kyrgyzhydromet** — the national hydrometeorological agency's network
  (Bishkek + ~14 stations + ~50 Clarity Node-S). *ML relevance:* historical
  context and, with manual effort, extra pollutant coverage (SO2, NO2, NH3,
  formaldehyde). *Grade **C*** — history is published only as quarterly PDF
  bulletin tables and the live Clarity map is not archived, so ingestion means
  digitising PDFs.
- **movegreen_aqkg** — the MoveGreen citizen network (100+ low-cost sensors
  across 10 Kyrgyz cities, dense in Bishkek). *ML relevance:* the only source
  with the spatial density to resolve within-city variation. *Grade **C*** —
  low-cost sensors with no published calibration; treat as indicative until
  co-located against the reference monitor.
- **airkaz** — AirKaz.org dual-Plantower low-cost network for Kazakhstan
  (~15 sensors in Almaty). *ML relevance:* an Almaty comparison layer. *Grade
  **C*** — low-cost hardware; the downloadable archive only covers
  Mar 2017–Sep 2020, so recent data needs scraping.

**Study tables derived from measurements** (annual/aggregate, not raw):

- **who_aap_db** — WHO Ambient Air Quality Database, city-year PM2.5/PM10/NO2
  aggregates. *ML relevance:* an annual benchmark to sanity-check levels.
  *Grade **C*** — aggregate-only: city-year values, not a raw or station-level
  series.
- **worldbank_bishkek_2023** — World Bank source-apportionment analysis for
  Bishkek. *ML relevance:* priors on which sources drive Bishkek PM2.5.
  *Grade **C*** — published as report tables derived from Clarity sensors, not
  raw data.

**Model output / reanalysis / satellite (estimates, not measurements):**

- **open_meteo_aq** — the Copernicus CAMS global model surfaced through the
  Open-Meteo Air Quality API: pm2_5, pm10, CO, NO2, SO2, O3, aerosol optical
  depth, dust. *ML relevance:* region-wide gridded predictors and the map's
  pollutant surface. *Grade **B*** — a modelled surface estimate on a coarse
  (~0.4°) grid; it needs ground validation and, per the grading rule, a
  model/satellite source cannot be graded A.
- **open_meteo_era5** — ECMWF ERA5 reanalysis via Open-Meteo: temperature_2m,
  relative_humidity_2m, wind_speed_10m, wind_direction_10m, surface_pressure,
  **boundary_layer_height**. *ML relevance:* the meteorological feature block;
  boundary-layer height is the key winter-inversion driver. *Grade **B*** —
  reanalysis, reliable for synoptic conditions but not for local extremes.
- **sentinel5p** — Sentinel-5P TROPOMI column densities (NO2, SO2, CO, O3,
  aerosol index, HCHO). *ML relevance:* an independent trace-gas signal not
  tied to the CAMS model. *Grade **B*** — column, not surface, concentration;
  cloud gaps; **documented with a ready-to-run snippet only, not automated**
  in this iteration.
- **cams_eac4** — CAMS Global Reanalysis EAC4 via the Copernicus ADS CDS API.
  *ML relevance:* an alternative gridded backbone if the Open-Meteo path is
  unavailable. *Grade **B*** — coarse (~0.75°) model reanalysis; **documented
  with a snippet only, not automated**.

---

## 4. The two datasets

Full column reference: [`dataset/data_dictionary.md`](dataset/data_dictionary.md)
(auto-generated by `build_dataset.py`; **0 `TODO-REVIEW` rows** for shipped
columns). A committed 63-row preview of the grid lives at
[`dataset/grid_daily_sample.csv`](dataset/grid_daily_sample.csv) (the Bishkek
grid cell + its 8 neighbours, a 7-day window from the first date with CAMS PM2.5).

### 4.1 `dataset/stations_daily.csv` — ground truth (wide, one row per station-date)

| column group | columns | meaning |
|---|---|---|
| keys | `station_key`, `date`, `lat`, `lon`, `city` | station id + UTC calendar day |
| pollutants | `pm2_5`, `pm10`, `carbon_monoxide`, `nitrogen_dioxide`, `sulphur_dioxide`, `ozone` (+ `<var>_max`) | hourly→daily mean; daily max kept |
| counts / flags | `n_hours_<var>`, `sparse` | hours present that day; `sparse` = any variable had < 18 h |
| provenance | `<var>_source` | `openaq` or `airnow` — which feed supplied that value (AirNow wins for Bishkek PM2.5) |

Built from `data/processed/openaq_*_daily.csv` and
`data/processed/airnow_bishkek_daily.csv`. **In this reference build the file is
empty (header only)** because no OpenAQ or AirNow key was available — see
§5. With keys, `build_stations` yields one row per station-date for Bishkek,
Almaty, Tashkent and Astana, with AirNow taking precedence for the Bishkek
`pm2_5` column.

### 4.2 `dataset/grid_daily.parquet` — regional gridded surface (wide, one row per cell-date)

| column group | columns | meaning |
|---|---|---|
| keys | `cell_id` (`<lat:.4f>_<lon:.4f>`), `lat`, `lon`, `date` | grid cell + UTC calendar day |
| CAMS pollutants | `pm2_5`, `pm10`, `carbon_monoxide`, `nitrogen_dioxide`, `sulphur_dioxide`, `ozone`, `aerosol_optical_depth`, `dust` (+ `<var>_max`) | Open-Meteo / CAMS global; daily mean + max |
| ERA5 meteorology | `temperature_2m`, `relative_humidity_2m`, `wind_speed_10m`, `wind_direction_10m`, `surface_pressure`, `boundary_layer_height` (+ `<var>_max`; wind direction is a vector mean) | Open-Meteo / ERA5; daily mean + max |
| counts / flags | `n_hours_<var>`, `sparse` | as above |
| derived | `dangerous_day` (`pm2_5 > 55.4`), `exceeds_kg_limit` (`pm2_5 > 35`) | EPA "Unhealthy" daily; Kyrgyz national daily limit |

The long-format twin for kepler's time slider is
`kepler/grid_daily_long.parquet` (`cell_id, lat, lon, date, variable, value`,
null values dropped).

### 4.3 CAMS archive start date (observed)

**The Open-Meteo CAMS global air-quality archive starts 2022-08-04.** Verified
in this build at every station point and every grid cell: all eight CAMS
gas/aerosol variables (`pm2_5`, `pm10`, `carbon_monoxide`, `nitrogen_dioxide`,
`sulphur_dioxide`, `ozone`, `aerosol_optical_depth`, `dust`) are **null before
2022-08-04**. The ERA5 meteorology block (`temperature_2m`,
`relative_humidity_2m`, `wind_speed_10m`, `wind_direction_10m`,
`surface_pressure`, `boundary_layer_height`) is complete for the whole
2021-01-01 → 2025-12-31 window. So `grid_daily.parquet` has meteorology for all
1826 days but CAMS pollutants for only the ~1245 days from 2022-08-04 onward.

---

## 5. Known limitations

Read this section before using the data for anything.

1. **CAMS air quality does not reach 2021.** The Open-Meteo CAMS global archive
   begins **2022-08-04**. Every gridded gas/aerosol variable is null before
   that date; only ERA5 meteorology covers the full 2021–2025 span (see §4.3).
   Any model that consumes gridded pollutants must restrict its training window
   accordingly.

2. **The grid is a context layer, not a substitute for the ground PM2.5
   target.** The CAMS grid (~0.4° native, sampled here on a 1°–2° grid)
   produces a daily-mean PM2.5 for the Bishkek cell that **peaks well below the
   55.4 µg/m³ "dangerous" threshold**, so grid `dangerous_day` counts for the
   Bishkek cell are **≈ 0 per heating season** (this build: 0 in every season
   2020–2025; cell peak daily-mean 48.8 µg/m³ in the 2022 season). Ground
   reality is far worse: Isaev et al. (2022, *AAQR*,
   [doi:10.4209/aaqr.210336](https://doi.org/10.4209/aaqr.210336), Table 4)
   report **52–93 days per season** over the 35 µg/m³ Kyrgyz national limit for
   Bishkek. The gap is spatial and temporal averaging in a coarse model cell —
   a ~1–2° cell blends the city with cold, clean mountains. **Use the grid for
   regional and temporal context (dust intrusions, cross-border smoke, synoptic
   setup); use the ground station for the PM2.5 target and for any
   exceedance-day analysis.**

3. **This reference build has no OpenAQ or AirNow key**, so
   `dataset/stations_daily.csv` from the automated run is empty. Until keys are
   supplied, the ground record for Bishkek comes from the **Zenodo 12720883**
   archive (US Embassy 2019–2024) fetched by `fetch_zenodo_bishkek.py`. Get the
   two free keys at <https://explore.openaq.org/register> and
   <https://docs.airnowapi.org/account/request/>, then re-run `fetch_openaq`,
   `fetch_airnow` and `build_dataset`.

4. **Low-cost sensor calibration is unknown.** OpenAQ low-cost providers,
   MoveGreen / AQ.kg and AirKaz all use Plantower-class sensors with no
   published local calibration. They are graded **C** and should be
   bias-corrected against the US Embassy reference before use as features or
   labels.

5. **Kyrgyzhydromet history is PDF-only.** The national network's back-catalogue
   exists only as tables inside quarterly PDF bulletins; the live Clarity map is
   not archived. Incorporating it means manual digitisation.

6. **Single reference monitor in Bishkek.** The entire ground truth for a city
   of ~1 million rests on one US Embassy instrument in one location. It cannot
   represent neighbourhood-scale variation, and its gaps are unrecoverable from
   other reference-grade data.

7. **CAMS and ERA5 are modelled, not measured.** `open_meteo_aq` is a CAMS
   model surface estimate and `open_meteo_era5` is a reanalysis. Both need
   ground validation, especially for local extremes (inversion nights, dust
   events). Neither can be graded A by the catalog's own rules.

8. **Grid resolution does not resolve intra-city variation.** Even at the
   supported 0.5° spacing (~50 km) a single cell covers all of Bishkek and much
   of its surroundings. Within-city gradients (valley floor vs. foothills,
   roadside vs. background) are invisible in `grid_daily.parquet`.

9. **Acceptance-run grid provenance.** The `dataset/grid_daily.parquet` shipped
   with this task was built at **`--grid-spacing 2.0`** (56 cells, lon 66–80 /
   lat 39–51, 2021–2025). A fresh 0.5°/1.0° re-fetch during the acceptance run
   was blocked by Open-Meteo's **daily request-limit** (`"Daily API request
   limit exceeded"`) after the earlier full-pipeline task runs; the quota
   resets on the next UTC day. The 2.0° grid is real CAMS + ERA5 data and is
   the documented robust fallback (§2). 44 of 56 cells carry CAMS pollutants;
   12 cells have ERA5 meteorology only, from mid-sweep rate-limit skips.

---

## Real-run coverage (2026-09-04)

What the shipped `dataset/` actually contains after the latest real pipeline run:

- **Grid** — `grid_daily.parquet`, 2021-01-01 → 2025-12-31 on the 2° / 56-cell
  grid. CAMS pollutants populate only from **2022-08-04** (archive start); ERA5
  meteorology is complete. **12 of the 56 cells (latitudes 49° and 51°, the
  northern edge ~700 km from Bishkek) were never fetched** — the Open-Meteo
  free-tier daily quota truncated the sweep, so they carry no CAMS pollutant
  data at all. The `plausibility.cell_coverage` QA check surfaces this; the
  1.0° re-run must refetch those cells.
- **Stations** — `stations_daily.csv`, OpenAQ Bishkek ≈ 1237 days but with a
  **2021–2023 hole**, so the annual-mean series jumps from 2020 straight to
  2024. Model-vs-ground PM2.5 overlap for the Bishkek cell is only **~400 days**.
- **Reference agreement** — ground exceedance-day counts for the full heating
  seasons (2019 / 2024 / 2025 = **92 / 79 / 74** days > 35 µg/m³) sit inside
  Isaev et al. (2022) Table 4's published **52–93** range.

## 6. Map & kepler

### Folium map — [`map/bishkek_air_quality_map.html`](map/bishkek_air_quality_map.html)

Built by `map/build_map.py` from `catalog/stations.geojson`,
`catalog/studies.csv` and `dataset/grid_daily.parquet`. Open the HTML file in
any browser. Layer groups, each toggleable from the top-left layer control:

| layer | contents |
|---|---|
| Reference monitors | US Embassy Bishkek (and any AirNow/reference points), coloured green (grade A) |
| Kyrgyzhydromet sensors | national-agency station(s), orange (grade B) |
| Citizen/low-cost sensors | OpenAQ low-cost / MoveGreen / AirKaz / Clarity points, red (grade C) |
| Comparison cities | Almaty, Tashkent, Astana markers |
| Study & campaign sites | the 8 rows of `studies.csv` as book icons, popups link to each DOI |
| Airshed extent | dashed Bishkek airshed bbox rectangle |
| CAMS grid: pm2_5 &lt;date&gt; | one-day snapshot of the gridded PM2.5 surface on the worst region-mean day (off by default) |

Marker colour encodes the quality grade (green = A, orange = B, red = C).
Station popups show operator, pollutants, period, `location_precision` and a
source link.

> **Screenshot:** the deliverable is an interactive Leaflet/Folium page, not a
> static image. Open [`map/bishkek_air_quality_map.html`](map/bishkek_air_quality_map.html)
> in a browser: you get a CARTO Positron basemap centred on Bishkek at zoom 7,
> coloured monitoring dots (green US Embassy, orange Kyrgyzhydromet, red
> low-cost), blue book icons for the study sites, the dashed airshed rectangle,
> and an expanded layer-control panel top-left listing the seven layers above.

### kepler.gl — [`kepler/kepler_layers.md`](kepler/kepler_layers.md)

`kepler/build_kepler.py` writes `kepler/stations_kepler.csv` (2 rows, 9 columns:
`name, latitude, longitude, network, operator, pollutants, period_start,
period_end, quality_grade`). Together with `kepler/grid_daily_long.parquet` from
`build_dataset.py`, drag both into <https://kepler.gl/demo>. Add a filter on
`variable` (pick e.g. `pm2_5`) and a filter on `date` — the latter gives you the
time-playback slider to scrub 2021–2025 and watch regional winter build-ups.
`kepler_layers.md` has the full per-layer config, including the emissions grid
from the Zenodo archive.

---

## 7. Licences

Per-source, from the `license` column of `catalog/sources.csv`:

| source | licence |
|---|---|
| OpenAQ | CC BY 4.0 |
| AirNow – US Embassy Bishkek | US Government public domain |
| Zenodo 12720883 (Guttikunda 2024) | CC BY 4.0 |
| Kyrgyzhydromet | Government – terms unclear (treat as all-rights-reserved; seek permission) |
| MoveGreen / AQ.kg | Unknown – contact the NGO before redistributing |
| AirKaz.org | Unknown – contact the operator before redistributing |
| Open-Meteo Air Quality (CAMS) | CC BY 4.0 (Open-Meteo) + underlying CAMS licence |
| Open-Meteo Historical Weather (ERA5) | CC BY 4.0 (Open-Meteo) + ERA5 / Copernicus licence |
| Sentinel-5P TROPOMI | Copernicus free and open data |
| CAMS Global Reanalysis EAC4 | Licence to use Copernicus Products |
| WHO Ambient Air Quality Database | WHO data terms |
| World Bank Bishkek analysis (2023) | World Bank open-access terms |

### CC BY 4.0 attribution

Redistributing data from **OpenAQ**, **Open-Meteo** (CAMS and ERA5), or the
**Zenodo 12720883** archive requires attribution under CC BY 4.0. Suggested
credit lines:

- **OpenAQ** — "Air quality data from OpenAQ (openaq.org), CC BY 4.0."
- **Open-Meteo / CAMS / ERA5** — "Weather and air-quality data from Open-Meteo
  (open-meteo.com), CC BY 4.0; derived from Copernicus CAMS and ECMWF ERA5."
- **Zenodo 12720883** — Guttikunda, S. (2024). *Mapping PM2.5 Sources and
  Emission Management Options for Bishkek, Kyrgyzstan.* Air, 2(4).
  [doi:10.3390/air2040021](https://doi.org/10.3390/air2040021); dataset
  [doi:10.5281/zenodo.12720883](https://doi.org/10.5281/zenodo.12720883),
  CC BY 4.0.

Copernicus products (Sentinel-5P, CAMS EAC4) additionally require a "Contains
modified Copernicus … data [year]" notice. AirNow / US Embassy data are US
Government public domain but a courtesy credit to the US Department of State /
US EPA AirNow program is expected. For the grade-C low-cost networks with
unknown terms (Kyrgyzhydromet, MoveGreen, AirKaz), obtain explicit permission
before redistributing their raw data; using them only to derive
bias-correction factors or aggregate statistics is lower-risk.

---

## Appendix — repository layout

```
catalog/     sources.csv, studies.csv, stations.geojson, validate_catalog.py
fetch/       common.py + fetch_openaq / fetch_airnow / fetch_zenodo_bishkek /
             fetch_open_meteo / build_dataset ; config.example.yaml
dataset/     data_dictionary.md, grid_daily_sample.csv (committed);
             stations_daily.csv, grid_daily.parquet (generated, gitignored)
kepler/      build_kepler.py, kepler_layers.md, stations_kepler.csv (committed);
             grid_daily_long.parquet (generated, gitignored)
map/         build_map.py, bishkek_air_quality_map.html (committed)
data/        raw/ (HTTP cache) + processed/ (per-source outputs) — all gitignored
tests/       pytest suite (22 tests)
docs/        design spec + implementation plan
```

### Acceptance run summary (2026-08-28/29)

| check | result |
|---|---|
| `pytest -q` | 22 passed |
| `catalog.validate_catalog` | exit 0 |
| `data_dictionary.md` `TODO-REVIEW` rows | 0 |
| `grid_daily.parquet` rows | 102 256 = 56 cells × 1826 days (2.0° grid; CAMS pollutants populated only from 2022-08-04) |
| `grid_daily_sample.csv` | 63 rows, 9 Bishkek-area cells, 7-day window, `pm2_5` fully populated |
| `bishkek_air_quality_map.html` | written; all 6 base layers + CAMS grid snapshot + layer control present |
| `stations_kepler.csv` | 2 rows, 9 columns in order |
| Bishkek-cell `dangerous_day` per heating season | 0 for every season 2020–2025 (vs Isaev 52–93 over 35 µg/m³) — the documented model-vs-ground gap (§5.2) |
| `fetch_openaq` (no key) | graceful per-city failure messages, no traceback; exits 1 (all cities failed) |
| `fetch_airnow` (no key) | prints Zenodo 12720883 fallback, exits 0 |
| grid re-fetch at 0.5°/1.0° | blocked by Open-Meteo daily request limit; shipped 2.0° grid used (§5.9) |
