# Central Asia Air Quality Dataset Collection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a verified, reusable collection of air quality + meteorology data for Bishkek and Central Asia (2021–2025) — a source catalog, runnable API fetch scripts, two merged datasets (ground stations + a region-wide model grid), an interactive Folium map, and kepler.gl-ready exports.

**Architecture:** Two data layers. A *ground layer* pulls real measurements from OpenAQ, AirNow, and a Zenodo archive. A *gridded layer* samples the CAMS model via Open-Meteo at every station and on a regular grid over the region. A merge step produces `stations_daily.csv` and `grid_daily.parquet` with a data dictionary. A hand-verified catalog (`sources.csv`, `stations.geojson`, `studies.csv`) drives a Folium map and kepler exports. Fetch scripts propose station rows into a staging file; they never overwrite the curated catalog.

**Tech Stack:** Python 3.10+, `requests`, `pandas`, `pyarrow`, `folium`, `PyYAML`, `pytest`. Optional `rarfile` + system `unrar` for Zenodo archives.

**Spec:** `docs/superpowers/specs/2026-08-28-central-asia-air-quality-datasets-design.md`

## Global Constraints

- Time span: `DATE_START = 2021-01-01`, `DATE_END = 2025-12-31` (inclusive), daily resolution.
- Cities (name → lat, lon): `Bishkek (42.8746, 74.5698)`, `Almaty (43.2380, 76.9450)`, `Tashkent (41.2995, 69.2401)`, `Astana (51.1605, 71.4704)`.
- Region bbox default: `lon 66.0 … 80.0`, `lat 39.0 … 52.0`. Grid spacing default: `0.5` degrees.
- Dangerous-day threshold: daily mean PM2.5 `> 55.4` µg/m³ (EPA "Unhealthy"). National limit: `> 35` µg/m³.
- Daily aggregation rule: a day needs ≥ `18` of 24 hours present or it is flagged (`n_hours_<var>` retained in every processed file).
- All concentrations in µg/m³ except CO (mg/m³ — record the unit explicitly in the data dictionary). Wind direction aggregated as vector mean, never arithmetic mean.
- Every model/reanalysis/satellite source is quality grade at most `B`, and its `quality_notes` must state "model, needs ground validation" or "column vs surface" verbatim.
- Station coordinates only from verifiable sources; unverified points get `location_precision` in `{approx, city-centroid}` and a `coord_source` value — never a fabricated precise coordinate.
- Secrets (`OPENAQ_API_KEY`, `AIRNOW_API_KEY`) come from env vars or `config.yaml` (gitignored), never `config.example.yaml`, never committed.
- Commit after every task. Keep `data/raw/`, `data/processed/`, `config.yaml`, and large `dataset/` binaries out of git (see Task 1 `.gitignore`).

---

## File Structure

```
datasets/
  README.md                         Task 11 — human-readable catalog + usage
  requirements.txt                  Task 1
  .gitignore                        Task 1
  fetch/
    config.example.yaml             Task 1
    common.py                       Task 2  — grid, daily agg, cached HTTP, quality report, config
    fetch_openaq.py                 Task 3
    fetch_airnow.py                 Task 4
    fetch_zenodo_bishkek.py         Task 5
    fetch_open_meteo.py             Task 6  — --mode points | grid
    build_dataset.py                Task 7  — merge → dataset/ + kepler long file
  catalog/
    sources.csv                     Task 8  (hand-authored, validated by test)
    studies.csv                     Task 8
    stations.geojson                Task 8
    validate_catalog.py             Task 8  — schema + rule checks
  map/
    build_map.py                    Task 9
    bishkek_air_quality_map.html    Task 9 output (committed)
  kepler/
    build_kepler.py                 Task 10
    stations_kepler.csv             Task 10 output
    kepler_layers.md                Task 10 (hand-authored)
  dataset/                          Task 7 outputs (gitignored except a small sample + dictionary)
    stations_daily.csv
    grid_daily.parquet
    data_dictionary.md              committed
    grid_daily_sample.csv           committed (1 week, Bishkek cell + neighbours)
  data/
    raw/                            gitignored
    processed/                      gitignored
  tests/
    conftest.py                     Task 2
    fixtures/                       fixture JSON per fetcher
    test_common.py                  Task 2
    test_fetch_openaq.py            Task 3
    test_fetch_airnow.py            Task 4
    test_fetch_zenodo.py            Task 5
    test_fetch_open_meteo.py        Task 6
    test_build_dataset.py           Task 7
    test_validate_catalog.py        Task 8
    test_build_map.py               Task 9
    test_build_kepler.py            Task 10
  docs/superpowers/
    specs/2026-08-28-central-asia-air-quality-datasets-design.md
    plans/2026-08-28-central-asia-air-quality-datasets.md
```

---

## Task 1: Project scaffold

**Files:**
- Create: `.gitignore`, `requirements.txt`, `fetch/config.example.yaml`, `fetch/__init__.py`, `tests/__init__.py`
- Run: `git init` (repo does not exist yet)

**Interfaces:**
- Consumes: nothing.
- Produces: `fetch/config.example.yaml` with keys `date_start, date_end, region_bbox {min_lon,max_lon,min_lat,max_lat}, grid_spacing_deg, cities {name: [lat, lon]}, openaq_api_key, airnow_api_key`. `requirements.txt` pinning the stack.

- [ ] **Step 1: Initialise the repo and folders**

```bash
cd /d/source/datasets
git init
mkdir -p fetch catalog map kepler dataset data/raw data/processed tests/fixtures
touch fetch/__init__.py tests/__init__.py
```

- [ ] **Step 2: Write `requirements.txt`**

```
requests==2.32.3
pandas==2.2.2
pyarrow==17.0.0
folium==0.17.0
PyYAML==6.0.2
pytest==8.3.2
```

- [ ] **Step 3: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
fetch/config.yaml
data/raw/
data/processed/
dataset/stations_daily.csv
dataset/grid_daily.parquet
dataset/grid_daily_long.parquet
.venv/
```

- [ ] **Step 4: Write `fetch/config.example.yaml`**

```yaml
# Copy to fetch/config.yaml and fill secrets. config.yaml is gitignored.
date_start: "2021-01-01"
date_end: "2025-12-31"
region_bbox:
  min_lon: 66.0
  max_lon: 80.0
  min_lat: 39.0
  max_lat: 52.0
grid_spacing_deg: 0.5
cities:
  Bishkek: [42.8746, 74.5698]
  Almaty: [43.2380, 76.9450]
  Tashkent: [41.2995, 69.2401]
  Astana: [51.1605, 71.4704]
openaq_api_key: ""     # or set env OPENAQ_API_KEY
airnow_api_key: ""     # or set env AIRNOW_API_KEY
```

- [ ] **Step 5: Create the venv and install**

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore requirements.txt fetch/ tests/ docs/
git commit -m "chore: scaffold central asia air quality dataset project"
```

---

## Task 2: `fetch/common.py` — shared utilities

**Files:**
- Create: `fetch/common.py`, `tests/conftest.py`, `tests/test_common.py`

**Interfaces:**
- Consumes: `fetch/config.example.yaml` shape from Task 1.
- Produces:
  - `load_config(path: str | None = None) -> dict` — reads `fetch/config.yaml` if present else `fetch/config.example.yaml`; env `OPENAQ_API_KEY` / `AIRNOW_API_KEY` override the file values.
  - `build_grid(bbox: dict, spacing: float) -> list[dict]` — each dict `{"cell_id": str, "lat": float, "lon": float}`; `cell_id` = `f"{lat:.4f}_{lon:.4f}"`; lats/lons inclusive of both bounds, rounded to 4 dp.
  - `to_daily(df: pd.DataFrame, value_cols: list[str], time_col: str = "time", how: str = "mean", min_count: int = 18) -> pd.DataFrame` — groups by calendar date (UTC), returns one row per date with aggregated `value_cols`, plus `n_hours_<col>` for each, plus `<col>_max` when `how == "mean"`. `how` in `{"mean", "sum"}`. Wind direction columns (name contains `wind_direction`) always use vector mean regardless of `how`.
  - `cached_get(url: str, params: dict, headers: dict | None = None, cache_dir: str = "data/raw/_cache", ttl_days: int = 30) -> dict` — GET returning parsed JSON; on 429/5xx retry 3× with backoff `2**n` seconds; caches JSON body to `cache_dir/<sha1(url+params)>.json`; a fresh cache hit skips the network.
  - `write_quality_report(name: str, df: pd.DataFrame, value_cols: list[str], out_dir: str = "data/processed", reference: pd.Series | None = None) -> str` — writes `<out_dir>/<name>_quality_report.md`, returns its path.

- [ ] **Step 1: Write failing tests for `build_grid`**

```python
# tests/test_common.py
import math
import json
import pandas as pd
import pytest
from fetch import common


def test_build_grid_corners_and_count():
    bbox = {"min_lon": 66.0, "max_lon": 68.0, "min_lat": 39.0, "max_lat": 40.0}
    grid = common.build_grid(bbox, spacing=1.0)
    coords = {(c["lat"], c["lon"]) for c in grid}
    assert (39.0, 66.0) in coords
    assert (40.0, 68.0) in coords
    assert len(grid) == 3 * 2  # lats 39,40 ; lons 66,67,68
    assert grid[0]["cell_id"] == "39.0000_66.0000"


def test_build_grid_ids_unique():
    bbox = {"min_lon": 66.0, "max_lon": 80.0, "min_lat": 39.0, "max_lat": 52.0}
    grid = common.build_grid(bbox, spacing=0.5)
    assert len({c["cell_id"] for c in grid}) == len(grid)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_common.py -q`
Expected: FAIL — `AttributeError: module 'fetch.common' has no attribute 'build_grid'`

- [ ] **Step 3: Implement `build_grid` and `load_config`**

```python
# fetch/common.py
from __future__ import annotations
import hashlib
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
import yaml

_CFG_DIR = Path(__file__).parent


def load_config(path: str | None = None) -> dict:
    if path is None:
        real = _CFG_DIR / "config.yaml"
        path = real if real.exists() else _CFG_DIR / "config.example.yaml"
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cfg["openaq_api_key"] = os.environ.get("OPENAQ_API_KEY") or cfg.get("openaq_api_key", "")
    cfg["airnow_api_key"] = os.environ.get("AIRNOW_API_KEY") or cfg.get("airnow_api_key", "")
    return cfg


def _frange(start: float, stop: float, step: float) -> list[float]:
    n = int(round((stop - start) / step))
    return [round(start + i * step, 4) for i in range(n + 1)]


def build_grid(bbox: dict, spacing: float) -> list[dict]:
    cells = []
    for lat in _frange(bbox["min_lat"], bbox["max_lat"], spacing):
        for lon in _frange(bbox["min_lon"], bbox["max_lon"], spacing):
            cells.append({"cell_id": f"{lat:.4f}_{lon:.4f}", "lat": lat, "lon": lon})
    return cells
```

- [ ] **Step 4: Run grid tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_common.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Write failing tests for `to_daily`**

```python
def _hourly_frame(hours, value):
    idx = pd.date_range("2021-01-01", periods=hours, freq="h", tz="UTC")
    return pd.DataFrame({"time": idx, "pm2_5": [value] * hours,
                         "wind_direction_10m": [90.0] * hours})


def test_to_daily_flags_sparse_day():
    df = _hourly_frame(10, 20.0)          # only 10 of 24 hours
    out = common.to_daily(df, ["pm2_5", "wind_direction_10m"])
    assert len(out) == 1
    assert out.iloc[0]["n_hours_pm2_5"] == 10
    assert out.iloc[0]["pm2_5_max"] == 20.0


def test_to_daily_full_day_mean():
    df = _hourly_frame(24, 30.0)
    out = common.to_daily(df, ["pm2_5", "wind_direction_10m"])
    assert out.iloc[0]["pm2_5"] == 30.0
    assert out.iloc[0]["n_hours_pm2_5"] == 24


def test_to_daily_wind_direction_is_vector_mean():
    idx = pd.date_range("2021-01-01", periods=2, freq="h", tz="UTC")
    df = pd.DataFrame({"time": idx, "wind_direction_10m": [0.0, 180.0]})
    out = common.to_daily(df, ["wind_direction_10m"])
    # opposite directions cancel → undefined; implementation returns NaN, not 90
    assert pd.isna(out.iloc[0]["wind_direction_10m"])
```

- [ ] **Step 6: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_common.py -k to_daily -q`
Expected: FAIL — `AttributeError: ... 'to_daily'`

- [ ] **Step 7: Implement `to_daily`**

```python
import numpy as np


def _vector_mean_deg(series: pd.Series) -> float:
    rad = np.deg2rad(series.dropna().to_numpy())
    if rad.size == 0:
        return np.nan
    s, c = np.sin(rad).mean(), np.cos(rad).mean()
    if abs(s) < 1e-9 and abs(c) < 1e-9:
        return np.nan
    return float(np.rad2deg(np.arctan2(s, c)) % 360)


def to_daily(df, value_cols, time_col="time", how="mean", min_count=18):
    if how not in {"mean", "sum"}:
        raise ValueError(f"unsupported how={how!r}")
    d = df.copy()
    d[time_col] = pd.to_datetime(d[time_col], utc=True)
    d["_date"] = d[time_col].dt.date
    rows = []
    for date, g in d.groupby("_date"):
        row = {"date": pd.Timestamp(date)}
        for col in value_cols:
            vals = g[col]
            n = int(vals.notna().sum())
            row[f"n_hours_{col}"] = n
            if "wind_direction" in col:
                row[col] = _vector_mean_deg(vals)
                continue
            agg = vals.sum() if how == "sum" else vals.mean()
            row[col] = float(agg) if n else np.nan
            if how == "mean":
                row[f"{col}_max"] = float(vals.max()) if n else np.nan
        row["sparse"] = any(row[f"n_hours_{c}"] < min_count for c in value_cols)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
```

- [ ] **Step 8: Run to_daily tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_common.py -k to_daily -q`
Expected: PASS (3 passed)

- [ ] **Step 9: Write failing tests for `cached_get` and `write_quality_report`**

```python
def test_cached_get_uses_cache(tmp_path, monkeypatch):
    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        def json(self): return {"ok": True}
        def raise_for_status(self): pass

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        return FakeResp()

    monkeypatch.setattr(common.requests, "get", fake_get)
    for _ in range(3):
        out = common.cached_get("https://x/y", {"a": 1}, cache_dir=str(tmp_path))
    assert out == {"ok": True}
    assert calls["n"] == 1  # network hit once, then cache


def test_cached_get_retries_on_429(tmp_path, monkeypatch):
    seq = [429, 429, 200]

    class FakeResp:
        def __init__(self, code): self.status_code = code
        def json(self): return {"tries": "done"}
        def raise_for_status(self): pass

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResp(seq.pop(0))

    monkeypatch.setattr(common.requests, "get", fake_get)
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    out = common.cached_get("https://x/z", {}, cache_dir=str(tmp_path))
    assert out == {"tries": "done"}


def test_quality_report_counts_implausible(tmp_path):
    df = pd.DataFrame({
        "date": pd.date_range("2021-01-01", periods=3),
        "pm2_5": [10.0, -5.0, 3000.0],
        "n_hours_pm2_5": [24, 24, 5],
    })
    path = common.write_quality_report("demo", df, ["pm2_5"], out_dir=str(tmp_path))
    text = pd.io.common.get_handle(path, "r").handle.read()
    assert "implausible" in text.lower()
    assert "2" in text  # -5 and 3000 both implausible
```

- [ ] **Step 10: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_common.py -k "cached_get or quality" -q`
Expected: FAIL — attributes missing

- [ ] **Step 11: Implement `cached_get` and `write_quality_report`**

```python
def _key(url, params):
    raw = url + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params or {}))
    return hashlib.sha1(raw.encode()).hexdigest()


def cached_get(url, params, headers=None, cache_dir="data/raw/_cache", ttl_days=30):
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    fp = Path(cache_dir) / f"{_key(url, params)}.json"
    if fp.exists() and (time.time() - fp.stat().st_mtime) < ttl_days * 86400:
        return json.loads(fp.read_text(encoding="utf-8"))
    delay = 1
    for attempt in range(4):
        resp = requests.get(url, params=params, headers=headers, timeout=60)
        if resp.status_code == 200:
            body = resp.json()
            fp.write_text(json.dumps(body), encoding="utf-8")
            return body
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < 3:
            time.sleep(delay); delay *= 2; continue
        resp.raise_for_status()
        raise RuntimeError(f"GET {url} -> {resp.status_code}")
    raise RuntimeError(f"GET {url} failed after retries")


_LIMITS = {"pm2_5": (0, 1000), "pm10": (0, 2000), "sulphur_dioxide": (0, 5000),
           "nitrogen_dioxide": (0, 5000), "carbon_monoxide": (0, 100000),
           "ozone": (0, 1000), "relative_humidity_2m": (0, 100),
           "wind_speed_10m": (0, 120), "surface_pressure": (300, 1100)}


def write_quality_report(name, df, value_cols, out_dir="data/processed", reference=None):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = Path(out_dir) / f"{name}_quality_report.md"
    lines = [f"# Quality report: {name}", "",
             f"- rows: {len(df)}",
             f"- date span: {df['date'].min()} → {df['date'].max()}" if "date" in df else "- no date column",
             ""]
    for col in value_cols:
        if col not in df:
            lines.append(f"- **{col}**: column absent"); continue
        s = pd.to_numeric(df[col], errors="coerce")
        lo, hi = _LIMITS.get(col, (-1e12, 1e12))
        implausible = int(((s < lo) | (s > hi)).sum())
        lines += [f"## {col}",
                  f"- missing: {s.isna().sum()} ({s.isna().mean():.1%})",
                  f"- min/median/max: {s.min():.3g} / {s.median():.3g} / {s.max():.3g}",
                  f"- implausible values (outside [{lo}, {hi}]): {implausible}", ""]
        nh = f"n_hours_{col}"
        if nh in df:
            lines.append(f"- days below min_count: {int((df[nh] < 18).sum())}\n")
    if reference is not None and "pm2_5" in df:
        merged = pd.to_numeric(df["pm2_5"], errors="coerce").reset_index(drop=True)
        ref = pd.to_numeric(reference, errors="coerce").reset_index(drop=True)
        m = pd.concat([merged, ref], axis=1).dropna()
        if len(m) > 2:
            r = m.iloc[:, 0].corr(m.iloc[:, 1])
            bias = (m.iloc[:, 0] - m.iloc[:, 1]).mean()
            lines += ["## vs reference (pm2_5)", f"- Pearson r: {r:.3f}",
                      f"- mean bias (this - ref): {bias:.2f}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
```

- [ ] **Step 12: Run the full common test file**

Run: `.venv/Scripts/python -m pytest tests/test_common.py -q`
Expected: PASS (all)

- [ ] **Step 13: Commit**

```bash
git add fetch/common.py tests/test_common.py tests/conftest.py
git commit -m "feat: shared fetch utilities (grid, daily agg, cached http, quality report)"
```

---

## Task 3: `fetch/fetch_openaq.py` — OpenAQ v3 ground stations

**Files:**
- Create: `fetch/fetch_openaq.py`, `tests/fixtures/openaq_locations.json`, `tests/fixtures/openaq_measurements.json`, `tests/test_fetch_openaq.py`

**Interfaces:**
- Consumes: `common.load_config`, `common.cached_get`, `common.to_daily`, `common.write_quality_report`.
- Produces:
  - `fetch_city(city: str, lat: float, lon: float, cfg: dict) -> pandas.DataFrame` — daily wide frame: `date`, one column per pollutant present (`pm2_5, pm10, sulphur_dioxide, nitrogen_dioxide, carbon_monoxide, ozone, relative_humidity, temperature`), `n_hours_*`, plus `city`.
  - `main(argv=None)` — writes `data/processed/openaq_<city>_daily.csv` per city and appends station rows to `data/processed/_stations_staging.csv` with columns `station_id,name,network,operator,lat,lon,pollutants,period_start,period_end,location_precision,coord_source,access_url`.
- OpenAQ v3 base `https://api.openaq.org/v3`; header `X-API-Key`. Endpoints used: `GET /locations?coordinates=<lat>,<lon>&radius=25000&limit=1000`, then per sensor `GET /sensors/{id}/measurements/daily?date_from=...&date_to=...&limit=366` (fall back to `/sensors/{id}/measurements` + `common.to_daily` if `/daily` 404s).
- Parameter name mapping OpenAQ→canonical: `pm25→pm2_5`, `pm10→pm10`, `so2→sulphur_dioxide`, `no2→nitrogen_dioxide`, `co→carbon_monoxide`, `o3→ozone`, `relativehumidity→relative_humidity`, `temperature→temperature`.

- [ ] **Step 1: Save fixture files**

`tests/fixtures/openaq_locations.json` — trimmed real shape:

```json
{"results": [
  {"id": 2178, "name": "US Diplomatic Post: Bishkek",
   "coordinates": {"latitude": 42.8746, "longitude": 74.5698},
   "sensors": [{"id": 4021, "parameter": {"name": "pm25", "units": "µg/m³"}}],
   "datetimeFirst": {"utc": "2021-01-01T00:00:00Z"},
   "datetimeLast": {"utc": "2025-12-31T23:00:00Z"},
   "provider": {"name": "AirNow"}}
]}
```

`tests/fixtures/openaq_measurements.json`:

```json
{"results": [
  {"value": 60.0, "period": {"datetimeFrom": {"utc": "2021-01-01T00:00:00Z"}}},
  {"value": 80.0, "period": {"datetimeFrom": {"utc": "2021-01-02T00:00:00Z"}}}
]}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_fetch_openaq.py
import json, pandas as pd, pytest
from pathlib import Path
from fetch import fetch_openaq, common

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_api(monkeypatch):
    loc = json.loads((FIX / "openaq_locations.json").read_text())
    meas = json.loads((FIX / "openaq_measurements.json").read_text())

    def fake_cached_get(url, params, headers=None, **kw):
        if "/locations" in url:
            return loc
        return meas

    monkeypatch.setattr(fetch_openaq.common, "cached_get", fake_cached_get)


def test_fetch_city_returns_daily_schema(fake_api):
    cfg = {"date_start": "2021-01-01", "date_end": "2021-01-31", "openaq_api_key": "x"}
    df = fetch_openaq.fetch_city("Bishkek", 42.8746, 74.5698, cfg)
    assert {"date", "pm2_5", "n_hours_pm2_5", "city"}.issubset(df.columns)
    assert df["city"].unique().tolist() == ["Bishkek"]
    assert len(df) == 2
    assert df.iloc[0]["pm2_5"] == 60.0
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_openaq.py -q`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `fetch/fetch_openaq.py`**

```python
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from fetch import common

BASE = "https://api.openaq.org/v3"
PARAM_MAP = {"pm25": "pm2_5", "pm10": "pm10", "so2": "sulphur_dioxide",
             "no2": "nitrogen_dioxide", "co": "carbon_monoxide", "o3": "ozone",
             "relativehumidity": "relative_humidity", "temperature": "temperature"}
STAGING = "data/processed/_stations_staging.csv"


def _sensor_daily(sensor_id, cfg, headers):
    url = f"{BASE}/sensors/{sensor_id}/measurements/daily"
    params = {"date_from": cfg["date_start"], "date_to": cfg["date_end"], "limit": 366}
    try:
        body = common.cached_get(url, params, headers=headers)
    except Exception:
        url = f"{BASE}/sensors/{sensor_id}/measurements"
        body = common.cached_get(url, params, headers=headers)
    rows = []
    for r in body.get("results", []):
        ts = (r.get("period", {}).get("datetimeFrom", {}) or {}).get("utc")
        rows.append({"time": ts, "value": r.get("value")})
    return pd.DataFrame(rows)


def fetch_city(city, lat, lon, cfg) -> pd.DataFrame:
    headers = {"X-API-Key": cfg.get("openaq_api_key", "")}
    loc_body = common.cached_get(f"{BASE}/locations",
                                 {"coordinates": f"{lat},{lon}", "radius": 25000, "limit": 1000},
                                 headers=headers)
    frames, station_rows = [], []
    for loc in loc_body.get("results", []):
        params_present = []
        for sensor in loc.get("sensors", []):
            raw = sensor.get("parameter", {}).get("name")
            canon = PARAM_MAP.get(raw)
            if not canon:
                continue
            sdf = _sensor_daily(sensor["id"], cfg, headers)
            if sdf.empty:
                continue
            sdf = sdf.rename(columns={"value": canon})
            daily = common.to_daily(sdf, [canon])
            frames.append(daily[["date", canon, f"n_hours_{canon}"]])
            params_present.append(canon)
        c = loc.get("coordinates", {})
        station_rows.append({
            "station_id": f"openaq-{loc.get('id')}", "name": loc.get("name"),
            "network": f"OpenAQ:{loc.get('provider', {}).get('name', 'unknown')}",
            "operator": loc.get("provider", {}).get("name", "unknown"),
            "lat": c.get("latitude"), "lon": c.get("longitude"),
            "pollutants": "|".join(sorted(params_present)),
            "period_start": (loc.get("datetimeFirst") or {}).get("utc", ""),
            "period_end": (loc.get("datetimeLast") or {}).get("utc", ""),
            "location_precision": "exact", "coord_source": "OpenAQ /locations",
            "access_url": f"https://explore.openaq.org/locations/{loc.get('id')}"})
    if not frames:
        out = pd.DataFrame(columns=["date", "city"])
    else:
        out = frames[0]
        for f in frames[1:]:
            out = out.merge(f, on="date", how="outer")
        out = out.sort_values("date").reset_index(drop=True)
    out["city"] = city
    fetch_city._stations = station_rows  # picked up by main()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    cfg = common.load_config(args.config)
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    all_stations = []
    for city, (lat, lon) in cfg["cities"].items():
        try:
            df = fetch_city(city, lat, lon, cfg)
        except Exception as e:  # noqa: BLE001
            print(f"[openaq] {city} FAILED: {e}")
            continue
        df.to_csv(f"data/processed/openaq_{city.lower()}_daily.csv", index=False)
        value_cols = [c for c in df.columns if c not in ("date", "city") and not c.startswith("n_hours_")]
        common.write_quality_report(f"openaq_{city.lower()}", df, value_cols)
        all_stations.extend(getattr(fetch_city, "_stations", []))
        print(f"[openaq] {city}: {len(df)} days, params {value_cols}")
    if all_stations:
        sdf = pd.DataFrame(all_stations).drop_duplicates("station_id")
        p = Path(STAGING)
        if p.exists():
            sdf = pd.concat([pd.read_csv(p), sdf]).drop_duplicates("station_id")
        sdf.to_csv(p, index=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_openaq.py -q`
Expected: PASS

- [ ] **Step 6: Live smoke run (needs `OPENAQ_API_KEY`; skip if unset)**

```bash
.venv/Scripts/python -m fetch.fetch_openaq --config fetch/config.yaml
```

Expected: `data/processed/openaq_bishkek_daily.csv` exists with a `pm2_5` column and > 300 rows; `_stations_staging.csv` created. If the key is unset, note it and move on.

- [ ] **Step 7: Commit**

```bash
git add fetch/fetch_openaq.py tests/fixtures/openaq_*.json tests/test_fetch_openaq.py
git commit -m "feat: OpenAQ v3 ground-station fetcher with daily aggregation"
```

---

## Task 4: `fetch/fetch_airnow.py` — Bishkek US Embassy reference monitor

**Files:**
- Create: `fetch/fetch_airnow.py`, `tests/fixtures/airnow_obs.json`, `tests/test_fetch_airnow.py`

**Interfaces:**
- Consumes: `common.load_config`, `common.cached_get`, `common.to_daily`, `common.write_quality_report`.
- Produces:
  - `fetch_bishkek(cfg: dict) -> pandas.DataFrame` — daily frame `date, pm2_5, n_hours_pm2_5` (µg/m³), sorted, one row per date.
  - `main(argv=None)` — writes `data/processed/airnow_bishkek_daily.csv`; if `airnow_api_key` empty, prints the offline-fallback message (`use fetch_zenodo_bishkek.py; Zenodo record 12720883 archive bishkek_monitoring_us.embassy2019-2024`) and exits 0.
- AirNow API base `https://www.airnowapi.org`. Historical observations by lat/lon:
  `GET /aq/observation/latLong/historical/?format=application/json&latitude=42.8746&longitude=74.5698&date=<YYYY-MM-DDT00-0000>&distance=25&API_KEY=<key>`.
  One request per day of the range; cache makes re-runs cheap. Keep only `Parameter == "PM2.5"`, field `AQI`→ convert? No: AirNow returns `Value` in the reporting unit for `RAW`? Use the `Value` field with `Unit == "UG/M3"`; if only `AQI` is present for a day, store `pm2_5 = NaN` and count it missing.

- [ ] **Step 1: Save fixture `tests/fixtures/airnow_obs.json`**

```json
[
  {"DateObserved": "2021-01-01", "HourObserved": 6, "ParameterName": "PM2.5",
   "Value": 55.4, "Unit": "UG/M3", "Latitude": 42.87, "Longitude": 74.57},
  {"DateObserved": "2021-01-01", "HourObserved": 7, "ParameterName": "PM2.5",
   "Value": 70.0, "Unit": "UG/M3", "Latitude": 42.87, "Longitude": 74.57}
]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_fetch_airnow.py
import json, pandas as pd, pytest
from pathlib import Path
from fetch import fetch_airnow

FIX = Path(__file__).parent / "fixtures"


def test_fetch_bishkek_daily_mean(monkeypatch):
    obs = json.loads((FIX / "airnow_obs.json").read_text())
    monkeypatch.setattr(fetch_airnow.common, "cached_get", lambda *a, **k: obs)
    cfg = {"date_start": "2021-01-01", "date_end": "2021-01-01",
           "cities": {"Bishkek": [42.8746, 74.5698]}, "airnow_api_key": "x"}
    df = fetch_airnow.fetch_bishkek(cfg)
    assert list(df.columns) == ["date", "pm2_5", "n_hours_pm2_5"]
    assert df.iloc[0]["pm2_5"] == pytest.approx(62.7)
    assert df.iloc[0]["n_hours_pm2_5"] == 2


def test_missing_key_exits_clean(monkeypatch, capsys):
    cfg = {"date_start": "2021-01-01", "date_end": "2021-01-01",
           "cities": {"Bishkek": [42.8746, 74.5698]}, "airnow_api_key": ""}
    monkeypatch.setattr(fetch_airnow, "load_config", lambda *_: cfg)
    rc = fetch_airnow.main([])
    assert rc == 0
    assert "12720883" in capsys.readouterr().out
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_airnow.py -q`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `fetch/fetch_airnow.py`**

```python
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from fetch import common
from fetch.common import load_config

BASE = "https://www.airnowapi.org/aq/observation/latLong/historical/"
FALLBACK = ("[airnow] no API key. Offline fallback: run fetch_zenodo_bishkek.py "
            "and use Zenodo record 12720883 archive "
            "'bishkek_monitoring_us.embassy2019-2024'.")


def fetch_bishkek(cfg) -> pd.DataFrame:
    lat, lon = cfg["cities"]["Bishkek"]
    days = pd.date_range(cfg["date_start"], cfg["date_end"], freq="D")
    rows = []
    for day in days:
        params = {"format": "application/json", "latitude": lat, "longitude": lon,
                  "date": day.strftime("%Y-%m-%dT00-0000"), "distance": 25,
                  "API_KEY": cfg["airnow_api_key"]}
        try:
            body = common.cached_get(BASE, params)
        except Exception as e:  # noqa: BLE001
            print(f"[airnow] {day.date()} failed: {e}")
            continue
        for rec in body:
            if rec.get("ParameterName") != "PM2.5":
                continue
            val = rec.get("Value") if str(rec.get("Unit", "")).upper() == "UG/M3" else None
            ts = f"{rec['DateObserved']}T{int(rec.get('HourObserved', 0)):02d}:00:00Z"
            rows.append({"time": ts, "pm2_5": val})
    if not rows:
        return pd.DataFrame(columns=["date", "pm2_5", "n_hours_pm2_5"])
    daily = common.to_daily(pd.DataFrame(rows), ["pm2_5"])
    return daily[["date", "pm2_5", "n_hours_pm2_5"]]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if not cfg.get("airnow_api_key"):
        print(FALLBACK)
        return 0
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    df = fetch_bishkek(cfg)
    df.to_csv("data/processed/airnow_bishkek_daily.csv", index=False)
    common.write_quality_report("airnow_bishkek", df, ["pm2_5"])
    print(f"[airnow] Bishkek: {len(df)} days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: the test patches `fetch_airnow.load_config`, so import it by name as shown.

- [ ] **Step 5: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_airnow.py -q`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add fetch/fetch_airnow.py tests/fixtures/airnow_obs.json tests/test_fetch_airnow.py
git commit -m "feat: AirNow historical fetcher for Bishkek US Embassy PM2.5"
```

---

## Task 5: `fetch/fetch_zenodo_bishkek.py` — Guttikunda 2024 archive

**Files:**
- Create: `fetch/fetch_zenodo_bishkek.py`, `tests/fixtures/zenodo_record.json`, `tests/test_fetch_zenodo.py`

**Interfaces:**
- Consumes: `common` (only `Path`/`requests` via `common.requests`).
- Produces:
  - `list_files(record_id: str = "12720883") -> list[dict]` — each `{"key": str, "size": int, "checksum": str, "url": str}` from `https://zenodo.org/api/records/<id>`.
  - `download_all(record_id="12720883", dest="data/raw/zenodo_12720883") -> str` — downloads each file, verifies `md5:` checksum, writes `dest/manifest.md`, returns `dest`.
  - `main(argv=None)`.
- `.rar` extraction: attempt `import rarfile`; on ImportError or missing `unrar` binary, print a one-line manual-step note and leave the `.rar` in place (still counts as success).

- [ ] **Step 1: Save fixture `tests/fixtures/zenodo_record.json`**

```json
{"files": [
  {"key": "bishkek_monitoring_us.embassy2019-2024.rar", "size": 402963,
   "checksum": "md5:0123456789abcdef0123456789abcdef",
   "links": {"self": "https://zenodo.org/api/records/12720883/files/bishkek_monitoring_us.embassy2019-2024.rar/content"}},
  {"key": "bishkek_camx_pm25_monthlyavg.csv", "size": 151800,
   "checksum": "md5:ffffffffffffffffffffffffffffffff",
   "links": {"self": "https://zenodo.org/api/records/12720883/files/bishkek_camx_pm25_monthlyavg.csv/content"}}
]}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_fetch_zenodo.py
import json, hashlib
from pathlib import Path
import pytest
from fetch import fetch_zenodo_bishkek as fz

FIX = Path(__file__).parent / "fixtures"


def test_list_files_parses_record(monkeypatch):
    rec = json.loads((FIX / "zenodo_record.json").read_text())
    monkeypatch.setattr(fz.common, "cached_get", lambda *a, **k: rec)
    files = fz.list_files("12720883")
    assert {f["key"] for f in files} == {
        "bishkek_monitoring_us.embassy2019-2024.rar", "bishkek_camx_pm25_monthlyavg.csv"}
    assert files[0]["checksum"].startswith("md5:")


def test_download_all_verifies_checksum(monkeypatch, tmp_path):
    payload = b"hello world"
    md5 = hashlib.md5(payload).hexdigest()
    rec = {"files": [{"key": "x.csv", "size": len(payload),
                      "checksum": f"md5:{md5}",
                      "links": {"self": "https://zenodo.org/x.csv"}}]}
    monkeypatch.setattr(fz.common, "cached_get", lambda *a, **k: rec)

    class R:
        status_code = 200
        content = payload
        def raise_for_status(self): pass

    monkeypatch.setattr(fz.common.requests, "get", lambda *a, **k: R())
    dest = fz.download_all("12720883", dest=str(tmp_path))
    assert (Path(dest) / "x.csv").read_bytes() == payload
    assert "x.csv" in (Path(dest) / "manifest.md").read_text()
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_zenodo.py -q`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `fetch/fetch_zenodo_bishkek.py`**

```python
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
from fetch import common

API = "https://zenodo.org/api/records"


def list_files(record_id: str = "12720883") -> list[dict]:
    body = common.cached_get(f"{API}/{record_id}", {})
    out = []
    for f in body.get("files", []):
        out.append({"key": f["key"], "size": f.get("size", 0),
                    "checksum": f.get("checksum", ""),
                    "url": f.get("links", {}).get("self", "")})
    return out


def _download(url: str) -> bytes:
    resp = common.requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def download_all(record_id="12720883", dest="data/raw/zenodo_12720883") -> str:
    d = Path(dest)
    d.mkdir(parents=True, exist_ok=True)
    lines = [f"# Zenodo {record_id} manifest", ""]
    for f in list_files(record_id):
        target = d / f["key"]
        blob = _download(f["url"])
        ok = ""
        if f["checksum"].startswith("md5:"):
            got = hashlib.md5(blob).hexdigest()
            ok = "checksum OK" if got == f["checksum"][4:] else f"CHECKSUM MISMATCH ({got})"
        target.write_bytes(blob)
        lines.append(f"- `{f['key']}` — {f['size']} bytes — {ok}")
        if f["key"].endswith(".rar"):
            lines.append(f"  - RAR: extract manually with `unrar x {target}` "
                         f"(rarfile/unrar not required by this script)")
    (d / "manifest.md").write_text("\n".join(lines), encoding="utf-8")
    return str(d)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default="12720883")
    ap.add_argument("--dest", default="data/raw/zenodo_12720883")
    args = ap.parse_args(argv)
    path = download_all(args.record, args.dest)
    print(f"[zenodo] downloaded to {path}; see manifest.md")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_zenodo.py -q`
Expected: PASS (2 passed)

- [ ] **Step 6: Live smoke run**

```bash
.venv/Scripts/python -m fetch.fetch_zenodo_bishkek
```

Expected: `data/raw/zenodo_12720883/manifest.md` lists ~10 files, each `checksum OK`.

- [ ] **Step 7: Commit**

```bash
git add fetch/fetch_zenodo_bishkek.py tests/fixtures/zenodo_record.json tests/test_fetch_zenodo.py
git commit -m "feat: Zenodo 12720883 downloader with checksum verification and manifest"
```

---

## Task 6: `fetch/fetch_open_meteo.py` — CAMS air quality + ERA5 weather (points & grid)

**Files:**
- Create: `fetch/fetch_open_meteo.py`, `tests/fixtures/open_meteo_aq.json`, `tests/fixtures/open_meteo_weather.json`, `tests/test_fetch_open_meteo.py`

**Interfaces:**
- Consumes: `common.load_config`, `common.build_grid`, `common.cached_get`, `common.to_daily`, `common.write_quality_report`.
- Produces:
  - `AQ_VARS = ["pm2_5","pm10","carbon_monoxide","nitrogen_dioxide","sulphur_dioxide","ozone","aerosol_optical_depth","dust"]`
  - `WX_VARS = ["temperature_2m","relative_humidity_2m","wind_speed_10m","wind_direction_10m","surface_pressure","boundary_layer_height"]`
  - `fetch_point(lat: float, lon: float, cfg: dict) -> pandas.DataFrame` — merged daily frame keyed on `date`; columns: every AQ var (mean) + `<var>_max`, every WX var (mean; wind dir vector mean), `n_hours_<var>` for each, plus `lat`, `lon`.
  - `run_points(cfg) -> pandas.DataFrame` — concat of `fetch_point` over `cfg["cities"]` values and every station in `data/processed/_stations_staging.csv` (dedupe on rounded lat/lon); adds `site` column (`city:<name>` or `station:<id>`). Writes `data/processed/openmeteo_points_daily.csv`.
  - `run_grid(cfg) -> None` — `fetch_point` over `build_grid`; adds `cell_id`; writes `data/processed/openmeteo_grid_daily.parquet`.
  - `main(argv=None)` — `--mode {points,grid}` required, `--config`, `--grid-spacing` override.
- Endpoints: AQ `https://air-quality-api.open-meteo.com/v1/air-quality`; weather `https://archive-api.open-meteo.com/v1/archive`. Common params: `latitude, longitude, start_date, end_date, hourly=<comma vars>, timezone=UTC`. AQ adds `domains=cams_global`.
- If a response has `error: true`, log `reason`, return an empty frame for that call, continue.

- [ ] **Step 1: Save fixtures**

`tests/fixtures/open_meteo_aq.json`:

```json
{"hourly": {"time": ["2021-01-01T00:00", "2021-01-01T01:00"],
  "pm2_5": [50.0, 70.0], "pm10": [60.0, 80.0],
  "carbon_monoxide": [900.0, 1100.0], "nitrogen_dioxide": [30.0, 40.0],
  "sulphur_dioxide": [10.0, 12.0], "ozone": [20.0, 22.0],
  "aerosol_optical_depth": [0.3, 0.4], "dust": [5.0, 6.0]}}
```

`tests/fixtures/open_meteo_weather.json`:

```json
{"hourly": {"time": ["2021-01-01T00:00", "2021-01-01T01:00"],
  "temperature_2m": [-5.0, -4.0], "relative_humidity_2m": [80.0, 82.0],
  "wind_speed_10m": [2.0, 3.0], "wind_direction_10m": [90.0, 90.0],
  "surface_pressure": [1010.0, 1011.0], "boundary_layer_height": [200.0, 250.0]}}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_fetch_open_meteo.py
import json, pandas as pd, pytest
from pathlib import Path
from fetch import fetch_open_meteo as fom

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_apis(monkeypatch):
    aq = json.loads((FIX / "open_meteo_aq.json").read_text())
    wx = json.loads((FIX / "open_meteo_weather.json").read_text())

    def fake_cached_get(url, params, headers=None, **kw):
        return aq if "air-quality" in url else wx

    monkeypatch.setattr(fom.common, "cached_get", fake_cached_get)


def test_fetch_point_merges_aq_and_weather(fake_apis):
    cfg = {"date_start": "2021-01-01", "date_end": "2021-01-01"}
    df = fom.fetch_point(42.87, 74.57, cfg)
    assert len(df) == 1
    assert df.iloc[0]["pm2_5"] == 60.0
    assert df.iloc[0]["pm2_5_max"] == 70.0
    assert df.iloc[0]["temperature_2m"] == -4.5
    assert df.iloc[0]["wind_direction_10m"] == pytest.approx(90.0)
    assert df.iloc[0]["lat"] == 42.87 and df.iloc[0]["lon"] == 74.57
    assert df.iloc[0]["n_hours_pm2_5"] == 2


def test_run_grid_writes_parquet(fake_apis, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/processed").mkdir(parents=True)
    cfg = {"date_start": "2021-01-01", "date_end": "2021-01-01",
           "region_bbox": {"min_lon": 74.0, "max_lon": 74.5,
                           "min_lat": 42.5, "max_lat": 43.0},
           "grid_spacing_deg": 0.5}
    fom.run_grid(cfg)
    out = pd.read_parquet(tmp_path / "data/processed/openmeteo_grid_daily.parquet")
    assert {"cell_id", "lat", "lon", "date", "pm2_5"}.issubset(out.columns)
    assert out["cell_id"].nunique() == 4   # 2x2 grid
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_open_meteo.py -q`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `fetch/fetch_open_meteo.py`**

```python
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from fetch import common

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WX_URL = "https://archive-api.open-meteo.com/v1/archive"
AQ_VARS = ["pm2_5", "pm10", "carbon_monoxide", "nitrogen_dioxide",
           "sulphur_dioxide", "ozone", "aerosol_optical_depth", "dust"]
WX_VARS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
           "wind_direction_10m", "surface_pressure", "boundary_layer_height"]


def _hourly_frame(body, varlist):
    h = body.get("hourly")
    if not h or body.get("error"):
        if body.get("error"):
            print(f"[open-meteo] error: {body.get('reason')}")
        return pd.DataFrame(columns=["time"] + varlist)
    df = pd.DataFrame({"time": h["time"]})
    for v in varlist:
        df[v] = h.get(v)
    return df


def fetch_point(lat, lon, cfg) -> pd.DataFrame:
    base = {"latitude": lat, "longitude": lon, "start_date": cfg["date_start"],
            "end_date": cfg["date_end"], "timezone": "UTC"}
    aq = _hourly_frame(common.cached_get(
        AQ_URL, {**base, "hourly": ",".join(AQ_VARS), "domains": "cams_global"}), AQ_VARS)
    wx = _hourly_frame(common.cached_get(
        WX_URL, {**base, "hourly": ",".join(WX_VARS)}), WX_VARS)
    frames = []
    if not aq.empty:
        frames.append(common.to_daily(aq, AQ_VARS))
    if not wx.empty:
        frames.append(common.to_daily(wx, WX_VARS))
    if not frames:
        return pd.DataFrame()
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on=["date", "sparse"], how="outer", suffixes=("", "_dup"))
    out = out.loc[:, ~out.columns.str.endswith("_dup")]
    out["lat"], out["lon"] = lat, lon
    return out.sort_values("date").reset_index(drop=True)


def _dedup_points(cfg):
    pts = [(f"city:{n}", lat, lon) for n, (lat, lon) in cfg["cities"].items()]
    staging = Path("data/processed/_stations_staging.csv")
    if staging.exists():
        s = pd.read_csv(staging).dropna(subset=["lat", "lon"])
        for _, r in s.iterrows():
            pts.append((f"station:{r['station_id']}", float(r["lat"]), float(r["lon"])))
    seen, out = set(), []
    for site, lat, lon in pts:
        key = (round(lat, 3), round(lon, 3))
        if key in seen:
            continue
        seen.add(key)
        out.append((site, lat, lon))
    return out


def run_points(cfg) -> pd.DataFrame:
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    frames = []
    for site, lat, lon in _dedup_points(cfg):
        df = fetch_point(lat, lon, cfg)
        if df.empty:
            print(f"[open-meteo] {site}: no data")
            continue
        df["site"] = site
        frames.append(df)
        print(f"[open-meteo] {site}: {len(df)} days")
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_csv("data/processed/openmeteo_points_daily.csv", index=False)
    if not out.empty:
        common.write_quality_report("openmeteo_points", out, AQ_VARS + WX_VARS)
    return out


def run_grid(cfg) -> None:
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    cells = common.build_grid(cfg["region_bbox"], cfg["grid_spacing_deg"])
    frames = []
    for i, c in enumerate(cells, 1):
        df = fetch_point(c["lat"], c["lon"], cfg)
        if df.empty:
            continue
        df["cell_id"] = c["cell_id"]
        frames.append(df)
        if i % 25 == 0:
            print(f"[open-meteo grid] {i}/{len(cells)} cells")
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_parquet("data/processed/openmeteo_grid_daily.parquet", index=False)
    if not out.empty:
        common.write_quality_report("openmeteo_grid", out, AQ_VARS + WX_VARS)
    print(f"[open-meteo grid] wrote {len(out)} rows from {len(frames)} cells")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["points", "grid"], required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--grid-spacing", type=float, default=None)
    args = ap.parse_args(argv)
    cfg = common.load_config(args.config)
    if args.grid_spacing:
        cfg["grid_spacing_deg"] = args.grid_spacing
    if args.mode == "points":
        run_points(cfg)
    else:
        run_grid(cfg)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_fetch_open_meteo.py -q`
Expected: PASS (2 passed). If `merge on ["date","sparse"]` raises because `sparse` differs, change the merge to `on="date"` and drop the extra `sparse_dup`/`sparse` columns explicitly — keep a single `sparse` = logical OR. Adjust the implementation and re-run until green.

- [ ] **Step 6: Live smoke run (coarse grid, short window)**

```bash
.venv/Scripts/python -m fetch.fetch_open_meteo --mode points --config fetch/config.yaml
.venv/Scripts/python -m fetch.fetch_open_meteo --mode grid --grid-spacing 2.0 --config fetch/config.yaml
```

Expected: `openmeteo_points_daily.csv` has a `site == "city:Bishkek"` block spanning 2021–2025; `openmeteo_grid_daily.parquet` written. Inspect `openmeteo_points_quality_report.md` — confirm whether `pm2_5` has data back to 2021-01-01 or the CAMS archive starts later (record the first non-null date in the README, Task 11).

- [ ] **Step 7: Commit**

```bash
git add fetch/fetch_open_meteo.py tests/fixtures/open_meteo_*.json tests/test_fetch_open_meteo.py
git commit -m "feat: Open-Meteo CAMS + ERA5 fetcher, points and grid modes"
```

---

## Task 7: `fetch/build_dataset.py` — merge to master datasets

**Files:**
- Create: `fetch/build_dataset.py`, `tests/fixtures/proc/` (small processed CSV/parquet fixtures), `tests/test_build_dataset.py`
- Create (outputs): `dataset/stations_daily.csv`, `dataset/grid_daily.parquet`, `dataset/data_dictionary.md`, `dataset/grid_daily_sample.csv`, `kepler/grid_daily_long.parquet`

**Interfaces:**
- Consumes: files under `data/processed/` from Tasks 3–6.
- Produces:
  - `build_stations(proc_dir="data/processed") -> pandas.DataFrame` — union of `openaq_*_daily.csv` + `airnow_bishkek_daily.csv`; one row per `station_key,date` where `station_key` is `city` for OpenAQ city files and `bishkek_us_embassy` for AirNow; wide pollutant columns; provenance column `<var>_source`; keeps `n_hours_*`. AirNow `pm2_5` wins over OpenAQ for Bishkek when both exist (reference monitor), with `pm2_5_source = "airnow"`.
  - `build_grid_dataset(proc_dir="data/processed") -> pandas.DataFrame` — reads `openmeteo_grid_daily.parquet`; adds `dangerous_day = pm2_5 > 55.4`, `exceeds_kg_limit = pm2_5 > 35`; column order `cell_id,lat,lon,date,<AQ vars>,<WX vars>,n_hours_*,flags`.
  - `write_data_dictionary(cols: list[str], path="dataset/data_dictionary.md") -> None` — one table row per column: name, source, unit, aggregation, caveat. Unknown columns get `TODO-REVIEW` so the reviewer catches omissions (acceptable here — it is a review signal, not shipped ambiguity).
  - `to_long(grid_df) -> pandas.DataFrame` — melt to `cell_id,lat,lon,date,variable,value` over the AQ+WX vars only.
  - `main(argv=None)`.

- [ ] **Step 1: Create fixture processed files**

```
tests/fixtures/proc/openaq_bishkek_daily.csv
  date,pm2_5,n_hours_pm2_5,city
  2021-01-01,60.0,24,Bishkek
  2021-01-02,90.0,24,Bishkek
tests/fixtures/proc/airnow_bishkek_daily.csv
  date,pm2_5,n_hours_pm2_5
  2021-01-01,58.0,22
  2021-01-02,120.0,23
```

Grid parquet fixture — create it in the test with pandas (2 cells × 2 dates, a `pm2_5` of 40 and 70).

- [ ] **Step 2: Write the failing test**

```python
# tests/test_build_dataset.py
import pandas as pd, pytest
from pathlib import Path
from fetch import build_dataset as bd

FIX = Path(__file__).parent / "fixtures" / "proc"


def test_build_stations_prefers_airnow_for_bishkek():
    df = bd.build_stations(str(FIX))
    b = df[(df["station_key"] == "bishkek_us_embassy") & (df["date"] == "2021-01-01")]
    assert b.iloc[0]["pm2_5"] == 58.0
    assert b.iloc[0]["pm2_5_source"] == "airnow"


def test_grid_flags(tmp_path):
    g = pd.DataFrame({"cell_id": ["a", "a"], "lat": [42.5, 42.5], "lon": [74.0, 74.0],
                      "date": pd.to_datetime(["2021-01-01", "2021-01-02"]),
                      "pm2_5": [40.0, 70.0], "n_hours_pm2_5": [24, 24]})
    (tmp_path / "openmeteo_grid_daily.parquet").write_bytes(b"")  # placeholder
    g.to_parquet(tmp_path / "openmeteo_grid_daily.parquet", index=False)
    out = bd.build_grid_dataset(str(tmp_path))
    assert out.set_index("date").loc["2021-01-02", "dangerous_day"] == True
    assert out.set_index("date").loc["2021-01-01", "dangerous_day"] == False
    assert out.set_index("date").loc["2021-01-01", "exceeds_kg_limit"] == True


def test_to_long_shape():
    g = pd.DataFrame({"cell_id": ["a"], "lat": [1.0], "lon": [2.0],
                      "date": pd.to_datetime(["2021-01-01"]),
                      "pm2_5": [40.0], "pm10": [50.0], "n_hours_pm2_5": [24]})
    long = bd.to_long(g)
    assert set(long["variable"]) == {"pm2_5", "pm10"}
    assert len(long) == 2
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_build_dataset.py -q`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `fetch/build_dataset.py`**

```python
from __future__ import annotations
import argparse
import glob
from pathlib import Path
import pandas as pd

AQ_VARS = ["pm2_5", "pm10", "carbon_monoxide", "nitrogen_dioxide",
           "sulphur_dioxide", "ozone", "aerosol_optical_depth", "dust"]
WX_VARS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
           "wind_direction_10m", "surface_pressure", "boundary_layer_height"]

_DICT = {
    "pm2_5": ("OpenAQ/AirNow or CAMS", "µg/m³", "hourly→daily mean; _max kept",
              "ground = measured; grid = model, needs validation"),
    "pm10": ("OpenAQ or CAMS", "µg/m³", "daily mean", "as pm2_5"),
    "carbon_monoxide": ("OpenAQ or CAMS", "µg/m³ (OpenAQ) / µg/m³ (CAMS)",
                        "daily mean", "check unit per source; CAMS is µg/m³"),
    "nitrogen_dioxide": ("OpenAQ or CAMS", "µg/m³", "daily mean", "as pm2_5"),
    "sulphur_dioxide": ("OpenAQ or CAMS", "µg/m³", "daily mean", "as pm2_5"),
    "ozone": ("OpenAQ or CAMS", "µg/m³", "daily mean", "as pm2_5"),
    "aerosol_optical_depth": ("CAMS", "unitless", "daily mean", "model; column property"),
    "dust": ("CAMS", "µg/m³", "daily mean", "model surface dust estimate"),
    "temperature_2m": ("ERA5", "°C", "daily mean; _max kept", "reanalysis"),
    "relative_humidity_2m": ("ERA5", "%", "daily mean", "reanalysis"),
    "wind_speed_10m": ("ERA5", "m/s", "daily mean", "reanalysis"),
    "wind_direction_10m": ("ERA5", "° from N", "daily vector mean", "reanalysis"),
    "surface_pressure": ("ERA5", "hPa", "daily mean", "reanalysis"),
    "boundary_layer_height": ("ERA5", "m", "daily mean", "reanalysis; key for winter inversions"),
    "dangerous_day": ("derived", "bool", "pm2_5 > 55.4", "EPA Unhealthy daily"),
    "exceeds_kg_limit": ("derived", "bool", "pm2_5 > 35", "Kyrgyz national daily limit"),
}


def build_stations(proc_dir="data/processed") -> pd.DataFrame:
    frames = []
    for fp in sorted(glob.glob(f"{proc_dir}/openaq_*_daily.csv")):
        df = pd.read_csv(fp)
        city = Path(fp).stem.replace("openaq_", "").replace("_daily", "")
        df["station_key"] = city
        for v in [c for c in df.columns if c in AQ_VARS]:
            df[f"{v}_source"] = "openaq"
        frames.append(df)
    air = Path(proc_dir) / "airnow_bishkek_daily.csv"
    if air.exists():
        a = pd.read_csv(air)
        a["station_key"] = "bishkek_us_embassy"
        a["pm2_5_source"] = "airnow"
        frames.append(a)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.sort_values(["station_key", "date"]).reset_index(drop=True)


def build_grid_dataset(proc_dir="data/processed") -> pd.DataFrame:
    g = pd.read_parquet(Path(proc_dir) / "openmeteo_grid_daily.parquet")
    g["date"] = pd.to_datetime(g["date"])
    if "pm2_5" in g:
        g["dangerous_day"] = g["pm2_5"] > 55.4
        g["exceeds_kg_limit"] = g["pm2_5"] > 35
    front = [c for c in ["cell_id", "lat", "lon", "date"] if c in g]
    rest = [c for c in g.columns if c not in front]
    return g[front + rest]


def to_long(grid_df) -> pd.DataFrame:
    vars_present = [v for v in AQ_VARS + WX_VARS if v in grid_df.columns]
    id_cols = [c for c in ["cell_id", "lat", "lon", "date"] if c in grid_df.columns]
    return grid_df.melt(id_vars=id_cols, value_vars=vars_present,
                        var_name="variable", value_name="value").dropna(subset=["value"])


def write_data_dictionary(cols, path="dataset/data_dictionary.md") -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    rows = ["# Data dictionary", "",
            "| column | source | unit | aggregation | caveat |",
            "|---|---|---|---|---|"]
    for c in cols:
        if c.startswith("n_hours_"):
            rows.append(f"| {c} | derived | count | hours present that day | <18 ⇒ day flagged |")
            continue
        s, u, agg, cav = _DICT.get(c, ("TODO-REVIEW", "TODO-REVIEW", "TODO-REVIEW", "TODO-REVIEW"))
        rows.append(f"| {c} | {s} | {u} | {agg} | {cav} |")
    Path(path).write_text("\n".join(rows), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--proc-dir", default="data/processed")
    args = ap.parse_args(argv)
    Path("dataset").mkdir(exist_ok=True)
    Path("kepler").mkdir(exist_ok=True)

    stations = build_stations(args.proc_dir)
    stations.to_csv("dataset/stations_daily.csv", index=False)

    grid = build_grid_dataset(args.proc_dir)
    grid.to_parquet("dataset/grid_daily.parquet", index=False)
    to_long(grid).to_parquet("kepler/grid_daily_long.parquet", index=False)

    # small committed sample: Bishkek cell + neighbours, first ISO week available
    if not grid.empty:
        bcell = grid.assign(d=((grid["lat"] - 42.8746) ** 2 + (grid["lon"] - 74.5698) ** 2)) \
                    .sort_values("d")["cell_id"].iloc[0]
        near = grid[grid["cell_id"].isin(grid["cell_id"].unique()[:9])]
        first_week = sorted(grid["date"].unique())[:7]
        near[near["date"].isin(first_week)].to_csv("dataset/grid_daily_sample.csv", index=False)

    write_data_dictionary(list(dict.fromkeys(list(stations.columns) + list(grid.columns))))

    print(f"stations_daily: {len(stations)} rows; grid_daily: {len(grid)} rows")
    if not grid.empty and "dangerous_day" in grid:
        bg = grid[grid["cell_id"] == bcell]
        bg = bg.assign(season=bg["date"].dt.year.where(bg["date"].dt.month >= 7, bg["date"].dt.year - 1))
        print(bg.groupby("season")["dangerous_day"].sum())


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_build_dataset.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Live run after fetchers**

```bash
.venv/Scripts/python -m fetch.build_dataset
```

Expected: `dataset/stations_daily.csv`, `dataset/grid_daily.parquet`, `dataset/data_dictionary.md` (no `TODO-REVIEW` rows for known vars), `kepler/grid_daily_long.parquet`, `dataset/grid_daily_sample.csv`. Console prints dangerous-day counts per heating season for the Bishkek cell — sanity-check against Isaev Table 4 (52–93 days/season).

- [ ] **Step 7: Commit**

```bash
git add fetch/build_dataset.py tests/fixtures/proc/ tests/test_build_dataset.py dataset/data_dictionary.md dataset/grid_daily_sample.csv
git commit -m "feat: merge processed data into master station + grid datasets"
```

---

## Task 8: `catalog/` — hand-authored source catalog + validator

**Files:**
- Create: `catalog/sources.csv`, `catalog/studies.csv`, `catalog/stations.geojson`, `catalog/validate_catalog.py`, `tests/test_validate_catalog.py`

**Interfaces:**
- Consumes: nothing at runtime (data is authored). Executor MUST verify each URL/DOI resolves with a quick `WebFetch`/browser check before committing; fix any dead link.
- Produces:
  - `validate_catalog.py`: `validate() -> list[str]` returning a list of problems (empty = OK); `main()` prints them and exits non-zero if any. Checks: required columns present; every `quality_grade` in `{A,B,C}`; every row whose `type` is in `{satellite,reanalysis,model_output}` has grade ≠ A and `quality_notes` containing `"needs ground validation"` or `"column"`; `stations.geojson` is valid GeoJSON with each feature carrying `location_precision` in `{exact,approx,city-centroid}` and a non-empty `coord_source`; every `sources.csv` `endpoint_or_url` is syntactically a URL.

- [ ] **Step 1: Author `catalog/sources.csv`**

Header: `source_id,name,type,operator,access_method,endpoint_or_url,auth_required,spatial_coverage,pollutants,met_variables,temporal_coverage,temporal_resolution,license,quality_grade,quality_notes,ml_relevance`

Rows (verify each URL before commit; adjust wording, keep grades):

```
openaq,OpenAQ,ground_network,OpenAQ Inc,REST API v3,https://api.openaq.org/v3,yes (free key),Global incl. Bishkek/Almaty/Tashkent/Astana,pm2_5|pm10|so2|no2|co|o3|bc,relative_humidity|temperature,2016-present (varies by station),hourly,CC BY 4.0,Aggregates reference + low-cost; provider mix per station - check provider field,Primary programmatic ground source for lagged-PM2.5 features and multi-pollutant context
airnow_bishkek,AirNow - US Embassy Bishkek,ground_reference,US EPA / US Dept of State,REST API,https://docs.airnowapi.org/,yes (free key),Bishkek (Leninskoye district),pm2_5,,2019-10 to present,hourly,US Gov public domain,EPA-approved monitor; single point; occasional gaps,Reference truth for Bishkek PM2.5 target and for validating CAMS grid
zenodo_12720883,Guttikunda 2024 Bishkek inventory + monitoring,emission_inventory,Sarath Guttikunda (UrbanEmissions.info),File download,https://zenodo.org/records/12720883,no,Bishkek airshed,pm2_5|bc|oc|no|no2|co|so2 (emissions); pm2_5 (monitoring),meteorology stats,2018 emissions; 2019-2024 monitoring,annual grid + daily monitoring,CC BY 4.0,Contains US Embassy 2019-2024 and Clarity 2021 series + gridded emissions,Offline fallback for US Embassy series; emissions grid as spatial predictor
kyrgyzhydromet,Kyrgyzhydromet air monitoring,ground_network,Agency for Hydrometeorology (MoES KR),Web map + PDF bulletins,https://meteo.kg/,no,Kyrgyzstan (Bishkek + 14 stations + ~50 Clarity Node-S),so2|no2|nox|co|formaldehyde|nh3|pm10|pm2_5|pm1|tsp,,quarterly bulletins; live map,quarterly (PDF) / live,Government - terms unclear,Historical only via PDF tables; live Clarity map not archived,Context + possible manual digitisation of bulletin tables
movegreen_aqkg,MoveGreen AQ.kg citizen network,ground_lowcost,MoveGreen (NGO),App / web,https://aq.kg/,unknown,10 Kyrgyz cities incl. Bishkek (100+ sensors),pm2_5|pm10|no2,,~2019-present,20-minute,Unknown - contact NGO,Low-cost sensors; no published calibration; coverage dense in Bishkek,Spatial density for within-city variation; treat as grade C until calibrated
airkaz,AirKaz.org,ground_lowcost,AirKaz.org,REST API,https://airkaz.org/,unknown,Kazakhstan (Almaty ~15 + other cities),pm2_5|pm10,,2020-present,hourly,Unknown,Dual Plantower PMS5003; certified in KZ/KG as a measuring tool,Almaty comparison layer
open_meteo_aq,Open-Meteo Air Quality API,model_output,Open-Meteo / Copernicus CAMS,REST API,https://open-meteo.com/en/docs/air-quality-api,no,Global grid (CAMS ~0.4deg),pm2_5|pm10|co|no2|so2|o3|aerosol_optical_depth|dust,,rolling archive (confirm 2021 start),hourly,CC BY 4.0 (Open-Meteo) / CAMS licence,model needs ground validation; surface estimate not measurement; confirm archive start year,Region-wide gridded predictors + spatial map layer
open_meteo_era5,Open-Meteo Historical Weather (ERA5),reanalysis,Open-Meteo / ECMWF ERA5,REST API,https://open-meteo.com/en/docs/historical-weather-api,no,Global grid (ERA5 ~0.25deg),,temperature_2m|relative_humidity_2m|wind_speed_10m|wind_direction_10m|surface_pressure|boundary_layer_height,1940-present,hourly,CC BY 4.0 / ERA5 licence,reanalysis needs ground validation for local extremes,Meteorological features incl. boundary-layer height for winter inversions
sentinel5p,Sentinel-5P TROPOMI,satellite,ESA / Copernicus,openEO / GEE / Data Space,https://dataspace.copernicus.eu/,yes (free account),Global ~5.5x3.5 km,no2|so2|co|o3|aerosol_index|hcho,,2018-present,daily overpass,Copernicus free/open,column densities not surface concentration; needs ground validation; cloud gaps,Documented snippet only this iteration; independent NO2/SO2/CO signal
cams_eac4,CAMS Global Reanalysis EAC4,reanalysis,ECMWF / Copernicus ADS,CDS API (cdsapi),https://ads.atmosphere.copernicus.eu/datasets/cams-global-reanalysis-eac4,yes (free account),Global ~0.75deg,pm2_5|pm10|no2|so2|co|o3,plus met,2003-present,3-hourly,Copernicus/Licence to use Copernicus Products,model needs ground validation; coarse resolution,Documented snippet only this iteration; alternative gridded backbone
who_aap_db,WHO Ambient Air Quality Database,study_table,World Health Organization,File download,https://www.who.int/data/gho/data/themes/air-pollution,no,Global cities incl. Bishkek/Almaty/Tashkent,pm2_5|pm10|no2,,updated ~2024,annual,WHO terms,city-year aggregates only,Context / annual benchmark
worldbank_bishkek_2023,World Bank Air Quality Analysis for Bishkek (2023),study_table,World Bank,Report + figures,https://documents.worldbank.org/,no,Bishkek,pm2_5 (source apportionment),,2019-2022,report,World Bank open access,tables derived from Clarity sensors; not raw data,Source-apportionment priors; validation of pollution levels
```

- [ ] **Step 2: Author `catalog/studies.csv`**

Header: `study_id,citation,year,doi_or_url,region,open_access,data_made_available,variables,method,relevance_notes`

```
isaev_aaqr_2022,"Isaev E. et al. Impact of Climate Change and Air Pollution Forecasting Using Machine Learning Techniques in Bishkek. Aerosol Air Qual. Res.",2022,https://doi.org/10.4209/aaqr.210336,Bishkek,yes,no raw data; Table 4 dangerous-day counts; Table 7 error metrics,pm1|pm2_5|pm10|synoptic types,Random Forest + others; single averaged error,The baseline this research extends - no error breakdown by concentration; no lagged PM2.5
guttikunda_air_2024,"Guttikunda S. Mapping PM2.5 Sources and Emission Management Options for Bishkek, Kyrgyzstan. Air.",2024,https://doi.org/10.3390/air2040021,Bishkek,yes,yes - Zenodo 12720883,pm2_5|emissions|meteorology,WRF-CAMx source apportionment,Emissions inventory + monitoring archive + GIS; primary open dataset
kulkarni_atmenv_2023,"Cities of Central Asia: New hotspots of air pollution in the world. Atmospheric Environment.",2023,https://doi.org/10.1016/j.atmosenv.2023.119946,Central Asia,partial,summary tables,pm2_5,satellite + ground synthesis,Regional context: winter peaks Almaty/Bishkek/Astana; dust in south
kazakhstan_pmf_2025,"Dominant sources of PM2.5 in Kazakhstan's urban cities: A PMF and HYSPLIT-based study.",2025,https://www.sciencedirect.com/science/article/abs/pii/S2212095525004225,Kazakhstan,partial,PMF factor tables,pm2_5|chemical species,PMF + HYSPLIT back-trajectories,Method template for source attribution + transport
centralasia_dust_mortality_2025,"Assessing the short-term exposure risk and mortality burden of dust and fine aerosol PM2.5 in Central Asia.",2025,https://www.sciencedirect.com/science/article/abs/pii/S0048969725015050,Central Asia,partial,exposure-response tables,pm2_5|dust,reanalysis + health model,Quantifies dust vs anthropogenic PM2.5 split - relevant to feature design
bishkek_drivers_pmc_2025,"Air pollution in Bishkek, Kyrgyzstan: Driving factors and state response.",2025,https://pmc.ncbi.nlm.nih.gov/articles/PMC12039649/,Bishkek,yes,narrative + cited figures,pm2_5,policy analysis,Governance context + monitoring-network history
acm_aiaai_2023,"An Effective Approach for Air Quality Prediction in Bishkek Based on Machine Learning.",2023,https://doi.org/10.1145/3633598.3633606,Bishkek,no,none,aqi|pm2_5|pm10|pm1,ML regression/classification,Second ML precedent for Bishkek - compare framing
arxiv_asia_2025,"Assessing and Predicting Air Pollution in Asia: A Regional and Temporal Study (2018-2023).",2025,https://arxiv.org/pdf/2501.15590,Asia incl. Central Asia,yes,derived country series,pm2_5,trend + forecasting,Cross-country PM2.5 trend numbers incl. Kyrgyzstan
```

- [ ] **Step 3: Author `catalog/stations.geojson`**

Minimum viable set (executor adds OpenAQ-discovered points from `_stations_staging.csv` after Task 3, marking `location_precision` per the staging `coord_source`):

```json
{"type": "FeatureCollection", "features": [
  {"type": "Feature", "geometry": {"type": "Point", "coordinates": [74.5936, 42.9006]},
   "properties": {"station_id": "us-embassy-bishkek", "name": "US Embassy Bishkek",
     "network": "AirNow", "operator": "US EPA / State Dept",
     "pollutants": "pm2_5", "met_variables": "",
     "period_start": "2019-10-01", "period_end": "present", "status": "active",
     "location_precision": "approx", "access_url": "https://www.airnow.gov/international/us-embassies-and-consulates/#Kyrgyzstan$Bishkek",
     "coord_source": "US Embassy Bishkek street address geocode (171 Prospekt Mira)",
     "quality_grade": "A", "notes": "Reference monitor; exact sensor location not published"}},
  {"type": "Feature", "geometry": {"type": "Point", "coordinates": [74.6122, 42.8760]},
   "properties": {"station_id": "kghm-ref-bishkek", "name": "Kyrgyzhydromet reference station (Bishkek)",
     "network": "Kyrgyzhydromet", "operator": "Agency for Hydrometeorology (MoES KR)",
     "pollutants": "so2|no2|co|pm10|pm2_5|tsp", "met_variables": "",
     "period_start": "", "period_end": "present", "status": "active",
     "location_precision": "city-centroid", "access_url": "https://meteo.kg/",
     "coord_source": "approx - Kyrgyzhydromet HQ area; confirm during implementation",
     "quality_grade": "B", "notes": "Historical data only via quarterly PDF bulletins"}}
]}
```

- [ ] **Step 4: Write the failing test**

```python
# tests/test_validate_catalog.py
from catalog import validate_catalog as vc


def test_catalog_is_valid():
    problems = vc.validate()
    assert problems == [], "\n".join(problems)
```

Create `catalog/__init__.py` (empty).

- [ ] **Step 5: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_validate_catalog.py -q`
Expected: FAIL — module missing.

- [ ] **Step 6: Implement `catalog/validate_catalog.py`**

```python
from __future__ import annotations
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
URL_RE = re.compile(r"^https?://")
SRC_COLS = ["source_id", "name", "type", "operator", "access_method",
            "endpoint_or_url", "auth_required", "spatial_coverage", "pollutants",
            "met_variables", "temporal_coverage", "temporal_resolution",
            "license", "quality_grade", "quality_notes", "ml_relevance"]
MODEL_TYPES = {"satellite", "reanalysis", "model_output"}


def validate() -> list[str]:
    problems: list[str] = []
    with open(HERE / "sources.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if rows and list(rows[0].keys()) != SRC_COLS:
        problems.append(f"sources.csv columns != expected: {list(rows[0].keys())}")
    for r in rows:
        sid = r.get("source_id", "?")
        if r.get("quality_grade") not in {"A", "B", "C"}:
            problems.append(f"{sid}: bad quality_grade {r.get('quality_grade')!r}")
        if not URL_RE.match(r.get("endpoint_or_url", "")):
            problems.append(f"{sid}: endpoint_or_url not a URL")
        if r.get("type") in MODEL_TYPES:
            if r.get("quality_grade") == "A":
                problems.append(f"{sid}: model/satellite source must not be grade A")
            note = r.get("quality_notes", "").lower()
            if "needs ground validation" not in note and "column" not in note:
                problems.append(f"{sid}: model/satellite source missing validation caveat")
    with open(HERE / "studies.csv", encoding="utf-8") as fh:
        srows = list(csv.DictReader(fh))
    for s in srows:
        if not URL_RE.match(s.get("doi_or_url", "")):
            problems.append(f"study {s.get('study_id')}: doi_or_url not a URL")
    geo = json.loads((HERE / "stations.geojson").read_text(encoding="utf-8"))
    if geo.get("type") != "FeatureCollection":
        problems.append("stations.geojson: not a FeatureCollection")
    for f in geo.get("features", []):
        p = f.get("properties", {})
        sid = p.get("station_id", "?")
        if p.get("location_precision") not in {"exact", "approx", "city-centroid"}:
            problems.append(f"{sid}: bad location_precision")
        if not p.get("coord_source"):
            problems.append(f"{sid}: empty coord_source")
        g = f.get("geometry", {})
        if g.get("type") != "Point" or len(g.get("coordinates", [])) != 2:
            problems.append(f"{sid}: geometry not a 2-coord Point")
    return problems


def main():
    problems = validate()
    for p in problems:
        print("PROBLEM:", p)
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Verify each source URL and DOI resolves**

For every `endpoint_or_url` in `sources.csv` and `doi_or_url` in `studies.csv`, do a quick fetch/browser check. Fix dead or redirected links. For DOIs, confirm the resolved title matches the citation; correct year/citation text as needed. This step has no code — it is manual verification, and it is required before the commit.

- [ ] **Step 8: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_validate_catalog.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add catalog/ tests/test_validate_catalog.py
git commit -m "feat: hand-authored source catalog, studies list, station geojson + validator"
```

---

## Task 9: `map/build_map.py` — Folium layered map

**Files:**
- Create: `map/build_map.py`, `tests/test_build_map.py`
- Output: `map/bishkek_air_quality_map.html`

**Interfaces:**
- Consumes: `catalog/stations.geojson`, `catalog/studies.csv`, optionally `dataset/grid_daily.parquet` (skipped gracefully if absent).
- Produces:
  - `build(stations_path, studies_path, grid_path=None, out_path="map/bishkek_air_quality_map.html", snapshot_var="pm2_5", snapshot_dates=None) -> str` — returns `out_path`.
  - Layer groups added in this order, each a `folium.FeatureGroup` toggled by `folium.LayerControl`: `"Reference monitors"`, `"Kyrgyzhydromet sensors"`, `"Citizen/low-cost sensors"`, `"Comparison cities"`, `"Study & campaign sites"`, `"Airshed extent"`, and when a grid is supplied one `"CAMS grid: <var> <date>"` group per snapshot date.
  - Station → group mapping by `properties.network`: contains `AirNow` or `reference` → Reference monitors; contains `Kyrgyzhydromet` → Kyrgyzhydromet sensors; contains `MoveGreen`/`AirKaz`/`OpenAQ` low-cost → Citizen/low-cost; city names in {Almaty,Tashkent,Astana} → Comparison cities; else Reference monitors.
  - Marker colour by `quality_grade`: A→green, B→orange, C→red. Popup HTML lists operator, pollutants, period, precision, access_url link.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_map.py
import json, pandas as pd
from pathlib import Path
from map import build_map


def _mini_catalog(tmp_path):
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [74.59, 42.90]},
         "properties": {"station_id": "a", "name": "US Embassy", "network": "AirNow",
           "operator": "EPA", "pollutants": "pm2_5", "period_start": "2019", "period_end": "now",
           "location_precision": "approx", "access_url": "https://x", "coord_source": "geocode",
           "quality_grade": "A", "notes": ""}}]}
    (tmp_path / "stations.geojson").write_text(json.dumps(geo))
    pd.DataFrame([{"study_id": "s1", "citation": "C", "year": 2024,
                   "doi_or_url": "https://doi.org/x", "region": "Bishkek",
                   "open_access": "yes", "data_made_available": "yes",
                   "variables": "pm2_5", "method": "RF", "relevance_notes": "n"}]
                 ).to_csv(tmp_path / "studies.csv", index=False)
    return tmp_path / "stations.geojson", tmp_path / "studies.csv"


def test_build_writes_html_with_layers(tmp_path):
    sp, stp = _mini_catalog(tmp_path)
    out = build_map.build(str(sp), str(stp), out_path=str(tmp_path / "m.html"))
    html = Path(out).read_text(encoding="utf-8")
    assert "Reference monitors" in html
    assert "Study &amp; campaign sites" in html or "Study & campaign sites" in html
    assert "LayerControl" in html or "leaflet-control-layers" in html
```

Create `map/__init__.py` (empty).

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_build_map.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `map/build_map.py`**

```python
from __future__ import annotations
import argparse
import json
from pathlib import Path
import folium
import pandas as pd

GRADE_COLOR = {"A": "green", "B": "orange", "C": "red"}
COMPARISON = {"Almaty", "Tashkent", "Astana"}


def _group_for(props: dict) -> str:
    net = (props.get("network") or "").lower()
    name = props.get("name") or ""
    if any(c in name for c in COMPARISON):
        return "Comparison cities"
    if "airnow" in net or "reference" in net:
        return "Reference monitors"
    if "kyrgyzhydromet" in net:
        return "Kyrgyzhydromet sensors"
    if any(k in net for k in ("movegreen", "airkaz", "openaq", "purpleair", "clarity")):
        return "Citizen/low-cost sensors"
    return "Reference monitors"


def _popup(props: dict) -> str:
    return (f"<b>{props.get('name','')}</b><br>"
            f"operator: {props.get('operator','')}<br>"
            f"pollutants: {props.get('pollutants','')}<br>"
            f"period: {props.get('period_start','')} → {props.get('period_end','')}<br>"
            f"precision: {props.get('location_precision','')}<br>"
            f"<a href='{props.get('access_url','')}' target='_blank'>source</a>")


def build(stations_path, studies_path, grid_path=None,
          out_path="map/bishkek_air_quality_map.html",
          snapshot_var="pm2_5", snapshot_dates=None) -> str:
    m = folium.Map(location=[42.87, 74.59], zoom_start=7, tiles="cartodbpositron")
    geo = json.loads(Path(stations_path).read_text(encoding="utf-8"))

    groups = {name: folium.FeatureGroup(name=name, show=True) for name in
              ["Reference monitors", "Kyrgyzhydromet sensors", "Citizen/low-cost sensors",
               "Comparison cities", "Study & campaign sites", "Airshed extent"]}

    for f in geo.get("features", []):
        props = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        folium.CircleMarker(
            [lat, lon], radius=6, color=GRADE_COLOR.get(props.get("quality_grade"), "gray"),
            fill=True, fill_opacity=0.85, popup=folium.Popup(_popup(props), max_width=300),
        ).add_to(groups[_group_for(props)])

    studies = pd.read_csv(studies_path)
    for _, s in studies.iterrows():
        # place study markers at Bishkek unless a lat/lon column exists
        lat = s["lat"] if "lat" in studies.columns and pd.notna(s.get("lat")) else 42.87
        lon = s["lon"] if "lon" in studies.columns and pd.notna(s.get("lon")) else 74.59
        html = (f"<b>{s['citation']}</b> ({s['year']})<br>"
                f"region: {s['region']}<br>data: {s['data_made_available']}<br>"
                f"<a href='{s['doi_or_url']}' target='_blank'>{s['doi_or_url']}</a><br>"
                f"{s['relevance_notes']}")
        folium.Marker([lat, lon], icon=folium.Icon(color="blue", icon="book"),
                      popup=folium.Popup(html, max_width=340)
                      ).add_to(groups["Study & campaign sites"])

    # Airshed extent: documented bbox rectangle (replace with Zenodo polygon if parsed)
    folium.Rectangle([[42.75, 74.45], [43.00, 74.75]], color="black", weight=1,
                     dash_array="5,5", fill=False, popup="Bishkek airshed (approx bbox)"
                     ).add_to(groups["Airshed extent"])

    for g in groups.values():
        g.add_to(m)

    if grid_path and Path(grid_path).exists():
        grid = pd.read_parquet(grid_path)
        grid["date"] = pd.to_datetime(grid["date"])
        if snapshot_dates is None:
            if "dangerous_day" in grid:
                worst = (grid.groupby("date")[snapshot_var].mean().idxmax())
                snapshot_dates = [worst]
            else:
                snapshot_dates = [grid["date"].max()]
        vmax = grid[snapshot_var].quantile(0.98)
        for d in snapshot_dates:
            sub = grid[grid["date"] == pd.Timestamp(d)]
            fg = folium.FeatureGroup(name=f"CAMS grid: {snapshot_var} {pd.Timestamp(d).date()}",
                                     show=False)
            for _, r in sub.iterrows():
                val = r[snapshot_var]
                frac = 0 if pd.isna(val) else min(val / vmax, 1.0)
                folium.CircleMarker(
                    [r["lat"], r["lon"]], radius=8, weight=0, fill=True,
                    fill_opacity=0.55,
                    fill_color=f"#{int(255*frac):02x}00{int(255*(1-frac)):02x}",
                    popup=f"{snapshot_var}={val:.1f} µg/m³ @ {r['cell_id']}").add_to(fg)
            fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    m.save(out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", default="catalog/stations.geojson")
    ap.add_argument("--studies", default="catalog/studies.csv")
    ap.add_argument("--grid", default="dataset/grid_daily.parquet")
    ap.add_argument("--out", default="map/bishkek_air_quality_map.html")
    args = ap.parse_args(argv)
    path = build(args.stations, args.studies,
                 grid_path=args.grid if Path(args.grid).exists() else None,
                 out_path=args.out)
    print(f"[map] wrote {path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_build_map.py -q`
Expected: PASS. If Folium's saved HTML escapes the ampersand, the test already accepts either form.

- [ ] **Step 5: Live build + eyeball**

```bash
.venv/Scripts/python -m map.build_map
```

Open `map/bishkek_air_quality_map.html` in a browser: six base layers toggle; markers have working source links; if the grid exists, the CAMS snapshot layer colours vary across the region.

- [ ] **Step 6: Commit**

```bash
git add map/build_map.py map/__init__.py tests/test_build_map.py map/bishkek_air_quality_map.html
git commit -m "feat: Folium layered air-quality map for Bishkek + Central Asia"
```

---

## Task 10: `kepler/` — kepler.gl exports + load guide

**Files:**
- Create: `kepler/build_kepler.py`, `kepler/kepler_layers.md`, `tests/test_build_kepler.py`
- Output: `kepler/stations_kepler.csv` (and relies on `kepler/grid_daily_long.parquet` from Task 7)

**Interfaces:**
- Consumes: `catalog/stations.geojson`.
- Produces:
  - `stations_to_csv(geojson_path, out_path="kepler/stations_kepler.csv") -> str` — flat columns `name,latitude,longitude,network,operator,pollutants,period_start,period_end,quality_grade`.
  - `main(argv=None)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_kepler.py
import json, pandas as pd
from pathlib import Path
from kepler import build_kepler


def test_stations_to_csv_flat(tmp_path):
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [74.59, 42.90]},
         "properties": {"station_id": "a", "name": "US Embassy", "network": "AirNow",
           "operator": "EPA", "pollutants": "pm2_5", "period_start": "2019",
           "period_end": "now", "location_precision": "approx", "coord_source": "x",
           "access_url": "https://x", "quality_grade": "A", "notes": ""}}]}
    p = tmp_path / "s.geojson"
    p.write_text(json.dumps(geo))
    out = build_kepler.stations_to_csv(str(p), str(tmp_path / "k.csv"))
    df = pd.read_csv(out)
    assert list(df.columns) == ["name", "latitude", "longitude", "network",
        "operator", "pollutants", "period_start", "period_end", "quality_grade"]
    assert df.iloc[0]["latitude"] == 42.90 and df.iloc[0]["longitude"] == 74.59
```

Create `kepler/__init__.py` (empty).

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_build_kepler.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `kepler/build_kepler.py`**

```python
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd

COLS = ["name", "latitude", "longitude", "network", "operator", "pollutants",
        "period_start", "period_end", "quality_grade"]


def stations_to_csv(geojson_path, out_path="kepler/stations_kepler.csv") -> str:
    geo = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    rows = []
    for f in geo.get("features", []):
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        rows.append({"name": p.get("name"), "latitude": lat, "longitude": lon,
                     "network": p.get("network"), "operator": p.get("operator"),
                     "pollutants": p.get("pollutants"),
                     "period_start": p.get("period_start"),
                     "period_end": p.get("period_end"),
                     "quality_grade": p.get("quality_grade")})
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=COLS).to_csv(out_path, index=False)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", default="catalog/stations.geojson")
    ap.add_argument("--out", default="kepler/stations_kepler.csv")
    args = ap.parse_args(argv)
    print(f"[kepler] wrote {stations_to_csv(args.stations, args.out)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write `kepler/kepler_layers.md`**

```markdown
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
- Use for: scrub 2021–2025, watch winter build-ups across the region.

## 3. Modelling dataset (wide) — `dataset/grid_daily.parquet`
- Same lat/lon; every variable is its own column plus `dangerous_day`.
- Colour by `dangerous_day` for a quick "how often is each cell over 55.4" view
  after aggregating by cell.

## 4. Emissions grid — from Zenodo 12720883 `bishkek_gridded_emissions_2018`
- After extracting the archive, load the shapefile/CSV.
- Layer type: **Polygon** (grid cells) or **Point** (cell centroids)
- Colour by the pollutant column (PM2.5, SO2, NO2, CO...).
```

- [ ] **Step 5: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_build_kepler.py -q`
Expected: PASS.

- [ ] **Step 6: Live run**

```bash
.venv/Scripts/python -m kepler.build_kepler
```

Expected: `kepler/stations_kepler.csv` has one row per catalog feature.

- [ ] **Step 7: Commit**

```bash
git add kepler/ tests/test_build_kepler.py
git commit -m "feat: kepler.gl station export and layer load guide"
```

---

## Task 11: `README.md` + full acceptance run

**Files:**
- Create: `README.md`
- Modify: none (verification task)

**Interfaces:**
- Consumes: every prior artefact.
- Produces: `README.md` — the human-facing catalog and runbook.

- [ ] **Step 1: Write `README.md`**

Sections, in order:

1. **What this is** — one paragraph tying it to the Bishkek next-day PM2.5 research.
2. **Quick start** — venv, `cp fetch/config.example.yaml fetch/config.yaml`, where to get the two free keys (OpenAQ: `https://explore.openaq.org/register`; AirNow: `https://docs.airnowapi.org/account/request/`), then the command sequence:
   ```bash
   .venv/Scripts/python -m fetch.fetch_openaq
   .venv/Scripts/python -m fetch.fetch_airnow
   .venv/Scripts/python -m fetch.fetch_zenodo_bishkek
   .venv/Scripts/python -m fetch.fetch_open_meteo --mode points
   .venv/Scripts/python -m fetch.fetch_open_meteo --mode grid
   .venv/Scripts/python -m fetch.build_dataset
   .venv/Scripts/python -m map.build_map
   .venv/Scripts/python -m kepler.build_kepler
   ```
3. **Source catalog** — render `catalog/sources.csv` as a Markdown table; under it, one sentence per source on *why it matters for the ML* and its **quality grade with the reason**. Explicitly state which sources are measurements and which are model output.
4. **The two datasets** — schema of `stations_daily.csv` and `grid_daily.parquet`, link to `dataset/data_dictionary.md`, and the CAMS archive start date actually observed in Task 6 Step 6 (state plainly if gases don't reach 2021).
5. **Known limitations** — low-cost sensor calibration unknown; Kyrgyzhydromet history is PDF-only; CAMS/ERA5 are modelled not measured; single reference monitor in Bishkek; grid is 0.5° (~50 km) so intra-city variation is not resolved.
6. **Map & kepler** — screenshot of the Folium map, link to `kepler/kepler_layers.md`.
7. **Licences** — per-source, from the `license` column; note CC BY 4.0 attribution requirements for OpenAQ, Open-Meteo, and Zenodo 12720883 (cite Guttikunda 2024).

- [ ] **Step 2: Run the whole test suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 3: Full pipeline acceptance run**

Run every command from README step 2 in order with real keys and a real (0.5°) grid. Then check:
- `dataset/stations_daily.csv` covers 2021–2025 for `bishkek_us_embassy` (or documents the gap).
- `dataset/grid_daily.parquet` row count ≈ `n_cells × n_days` (minus documented CAMS gaps).
- `dataset/data_dictionary.md` has no `TODO-REVIEW` rows for any shipped column.
- `map/bishkek_air_quality_map.html` opens, all layers toggle, links resolve.
- `kepler/grid_daily_long.parquet` + `kepler/stations_kepler.csv` load into kepler.gl and the `date` filter produces a time slider.
- Dangerous-day counts per heating season for the Bishkek cell are in a plausible range vs Isaev Table 4 (52–93). If wildly off, note it in the README limitations rather than silently shipping.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: catalog README and pipeline runbook; acceptance run complete"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage**

| Spec section | Task |
|---|---|
| 1 Purpose — two datasets, pollutants + met, map, kepler, quality reports | Tasks 3–10 |
| 2 Approach — OpenAQ / AirNow / Zenodo / Open-Meteo points+grid | Tasks 3, 4, 5, 6 |
| 2 — Sentinel-5P / CAMS-EAC4 documented not automated | Task 8 `sources.csv` rows + README |
| 2 Region & grid — bbox, 0.5°, call budget | Task 1 config, Task 2 `build_grid`, Task 6 |
| 3 Deliverable structure | File Structure section + per-task Files |
| 4.1 sources.csv schema + grading rules | Task 8 Steps 1, 6 (validator enforces) |
| 4.2 stations.geojson + precision/coord_source | Task 8 Steps 3, 6 |
| 4.3 studies.csv + seed rows | Task 8 Step 2 |
| 4.4 common.py (grid, to_daily, cached_get, quality report, config) | Task 2 |
| 4.5 fetch_openaq | Task 3 |
| 4.6 fetch_airnow + offline fallback | Task 4 |
| 4.7 fetch_zenodo + checksum + manifest | Task 5 |
| 4.8 fetch_open_meteo points+grid, vars, daily agg, Bishkek cross-check | Task 6 |
| 4.9 build_dataset — stations_daily, grid_daily, flags, data dictionary, long file | Task 7 |
| 4.10 build_map — 7 layer groups, colour by grade | Task 9 |
| 4.11 kepler exports + layer guide | Task 10 |
| 5 Data flow | README step 2 sequence; Task 7/9 consume Task 3–6 outputs |
| 6 Error handling — retry/backoff, skip-on-missing-key, partial reports | Task 2 `cached_get`; Task 4 fallback; Task 6 error branch |
| 7 Testing | Test step in every task; full suite Task 11 Step 2 |
| 8 Dependencies | Task 1 requirements.txt |
| 9 Open items | Task 6 Step 6 (CAMS start), Task 8 Step 7 (coords/DOIs), Task 9 (airshed bbox fallback), README limitations |

No spec requirement is left without a task.

**2. Placeholder scan** — the only literal `TODO-REVIEW` is produced *by code* in `write_data_dictionary` as a deliberate review signal for unrecognised columns, and Task 11 Step 3 fails the acceptance run if any ship. Task 8 Step 7 and Task 6 Step 6 are manual-verification steps with explicit, bounded checks, not vague "handle it later" instructions. No `TBD`, no "implement later", no un-coded test steps.

**3. Type consistency** — `common.to_daily` returns a `date` column (Timestamp) + `n_hours_<col>` + `<col>_max` (mean mode) + `sparse`; consumed consistently in Tasks 3, 4, 6. `cached_get(url, params, headers=None, ...)` signature identical across Tasks 3–6 and patched with the same shape in every test. `build_grid` cell dict keys `cell_id/lat/lon` match Task 6 `run_grid` and Task 7 `build_grid_dataset`. AQ/WX var lists are defined once in Task 6 and re-declared verbatim in Task 7 (`build_dataset.py`) — kept identical intentionally so the two scripts don't import each other. Station staging columns (`station_id,name,network,operator,lat,lon,pollutants,period_start,period_end,location_precision,coord_source,access_url`) match between Task 3 output and Task 6 `_dedup_points` / Task 8 Step 3 consumption.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-08-28-central-asia-air-quality-datasets.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
