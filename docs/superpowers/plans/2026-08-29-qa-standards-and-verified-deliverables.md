# QA Layer, Threshold Standards, and Verified Deliverables — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cited threshold source-of-truth (`catalog/standards.csv`), a data-quality layer (`qa/`) that verifies the datasets on four axes and emits a committed report, and produce verified final deliverables (real datasets + a finished map + refreshed kepler exports) from one budgeted real pipeline run.

**Architecture:** Phase A is offline code: `catalog/standards.csv` + `catalog/standards.py` loader; `build_dataset` rewired to read thresholds from it; a `qa/` package (`geo`, `loaders`, four `checks/*` modules each returning `Finding` objects, `report.py`), all fixture-tested. Phase B runs the real pipeline once with API budgets, regenerates every committed artifact, then runs `qa/report.py` against the real data. Phase C is the final whole-branch review (handled by the SDD skill, not a plan task).

**Tech Stack:** Python 3.10+ (`.venv/Scripts/python`), pandas 2.3, pyarrow 25, folium 0.20, PyYAML, pytest 9. No new dependencies except an optional rar extractor detected at runtime.

**Spec:** `docs/superpowers/specs/2026-08-29-qa-standards-and-verified-deliverables-design.md` (read it and the predecessor spec it names)

## Global Constraints

- Thresholds are **US EPA and Kyrgyz only**. No WHO, no EU, no sensitivity thresholds. Primary "dangerous day" = daily-mean pm2_5 > `55.4` (`epa_aqi_unhealthy_pm25`, kind `alert`). Secondary = > `35` (`kg_mpc_daily_pm25`, kind `limit`, ПП КР №201 2016 поз. 613).
- `build_dataset` reads `55.4` / `35` (and any pollutant limit) from `catalog/standards.csv` via `catalog.standards.load_standards`, never from a literal in the flag logic. Missing file or id → raise, never fall back.
- Flag columns keep names `dangerous_day`, `exceeds_kg_limit` and nullable-boolean semantics (`pandas` `"boolean"` dtype, `<NA>` where `pm2_5` is null). No rename.
- QA **never modifies data**: no imputation, interpolation, smoothing, outlier removal. Missing stays NaN / `<NA>`. Implausible values are counted and reported, not deleted.
- Open-Meteo grid run uses `--grid-spacing 1.0` this iteration (~210 cells, ~420 calls). Not 0.5. One clean run; disk cache means re-runs only fetch misses.
- AirNow direct (500 req/hour cap; 1 request/day) runs ONLY as a conditional 2025 gap-fill (≤ ~365 requests) after inspecting OpenAQ Bishkek 2025 coverage. Primary Bishkek ground record = OpenAQ + Zenodo archive.
- No secret in any tracked file. `fetch/config.yaml` stays untracked. Keys already present there.
- Run Python as `.venv/Scripts/python`. Full suite: `.venv/Scripts/python -m pytest -q`.
- Commit after every task. Commit-message body ends with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Bishkek reference coordinate: `BISHKEK_LAT, BISHKEK_LON = 42.8746, 74.5698`. Nearest 1.0° grid cell = `cell_id` `"43.0000_75.0000"`.

---

## File Structure

```
catalog/
  standards.csv          T1 — cited thresholds, US EPA + Kyrgyz only
  standards.py           T1 — load_standards() -> dict[str, float]
  validate_catalog.py    T1 — extend: validate standards.csv
fetch/
  build_dataset.py       T2 — read thresholds from catalog.standards; add station-side flags
  parse_zenodo_bishkek.py T10 — extract + parse Zenodo US Embassy / Clarity to tidy daily csv
  fetch_airnow.py        T10 — add --start / --end overrides
qa/
  __init__.py            T3
  geo.py                 T3 — BISHKEK_LAT/LON, nearest_cell_id()
  loaders.py             T3 — QAContext, load_context()
  thresholds.yaml        T3 — WARN/FAIL bounds for the checks
  reference_values.yaml  T3 — published anchors with citations
  checks/
    __init__.py          T3
    structure.py         T4
    plausibility.py      T5
    agreement.py         T6
    reference.py         T7
  report.py              T8 — orchestrate, write QA_REPORT.md, exit code
  QA_REPORT.md           T12 — generated from real data, committed
map/
  build_map.py           T9 — snapshot = worst heating-season day; use qa.geo cell
tests/
  test_standards.py            T1
  test_build_dataset.py        T2 — extend
  test_qa_loaders.py           T3
  test_qa_structure.py         T4
  test_qa_plausibility.py      T5
  test_qa_agreement.py         T6
  test_qa_reference.py         T7
  test_qa_report.py            T8
  test_build_map.py            T9 — extend
  test_parse_zenodo.py         T10
  test_fetch_airnow.py         T10 — extend
  fixtures/qa/                  T3+ — crafted csv/parquet per check
```

---

## Task 1: `catalog/standards.csv` + `catalog/standards.py` + validator extension

**Files:**
- Create: `catalog/standards.csv`, `catalog/standards.py`, `tests/test_standards.py`
- Modify: `catalog/validate_catalog.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `catalog/standards.py`: `load_standards(path="catalog/standards.csv") -> dict[str, float]` — maps `standard_id` to `value_ug_m3` (float). Raises `FileNotFoundError` if the file is missing, `KeyError` via `require(std, sid)` helper if a caller needs an absent id.
  - `require(standards: dict, standard_id: str) -> float` — returns `standards[standard_id]` or raises `KeyError(f"standards.csv missing required id: {standard_id}")`.
  - `catalog/validate_catalog.py`: `validate()` also checks `standards.csv`.

- [ ] **Step 1: Write `catalog/standards.csv`**

```csv
standard_id,authority,pollutant,averaging_period,value_ug_m3,kind,citation,url,notes
epa_aqi_unhealthy_pm25,US EPA,pm2_5,24h,55.4,alert,"US EPA Air Quality Index (AQI) — Technical Assistance Document, PM2.5 'Unhealthy' category lower breakpoint (2024 revision retained 55.4)",https://www.airnow.gov/aqi/aqi-basics/,Health-action category boundary; not a regulatory limit. Primary 'dangerous day' threshold for the paper.
kg_mpc_daily_pm25,Kyrgyzstan,pm2_5,24h,35,limit,"ПП КР №201 от 11.04.2016, Гигиенические нормативы ПДК, поз. 613 (0,035 мг/м3 среднесуточная)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,Numerically equal to US EPA NAAQS 24-h; cited here as the Kyrgyz national daily limit.
kg_mpc_annual_pm25,Kyrgyzstan,pm2_5,1y,25,limit,"ПП КР №201 от 11.04.2016, поз. 613 примечание (0,025 мг/м3 среднегодовая)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,
kg_mpc_daily_pm10,Kyrgyzstan,pm10,24h,60,limit,"ПП КР №201 от 11.04.2016, поз. 612 (0,06 мг/м3 среднесуточная)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,
kg_mpc_annual_pm10,Kyrgyzstan,pm10,1y,40,limit,"ПП КР №201 от 11.04.2016, поз. 612 примечание (0,04 мг/м3 среднегодовая)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,
kg_mpc_daily_so2,Kyrgyzstan,sulphur_dioxide,24h,50,limit,"ПП КР №201 от 11.04.2016, поз. 463 (0,05 мг/м3 среднесуточная)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,
kg_mpc_daily_no2,Kyrgyzstan,nitrogen_dioxide,24h,40,limit,"ПП КР №201 от 11.04.2016, поз. 4 (0,04 мг/м3 среднесуточная)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,
kg_mpc_daily_no,Kyrgyzstan,nitrogen_oxide,24h,60,limit,"ПП КР №201 от 11.04.2016, поз. 6 (0,06 мг/м3 среднесуточная)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,
kg_mpc_daily_co,Kyrgyzstan,carbon_monoxide,24h,3000,limit,"ПП КР №201 от 11.04.2016, поз. 521 (3 мг/м3 среднесуточная)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,Value in ug/m3 (3 mg/m3).
kg_mpc_daily_o3,Kyrgyzstan,ozone,24h,30,limit,"ПП КР №201 от 11.04.2016, поз. 387 (0,03 мг/м3 среднесуточная)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,
kg_mpc_daily_nh3,Kyrgyzstan,ammonia,24h,40,limit,"ПП КР №201 от 11.04.2016, поз. 103 (0,04 мг/м3 среднесуточная)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,
kg_mpc_daily_hcoh,Kyrgyzstan,formaldehyde,24h,3,limit,"ПП КР №201 от 11.04.2016, поз. 541 (0,003 мг/м3 среднесуточная)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,
kg_mpc_daily_hcn,Kyrgyzstan,hydrogen_cyanide,24h,1,limit,"ПП КР №201 от 11.04.2016 (0,001 мг/м3 среднесуточная)",https://faolex.fao.org/docs/pdf/kyr179875.pdf,
```

- [ ] **Step 2: Write the failing test — `tests/test_standards.py`**

```python
import pytest
from catalog import standards as S


def test_load_standards_has_the_two_headline_ids():
    std = S.load_standards()
    assert std["epa_aqi_unhealthy_pm25"] == 55.4
    assert std["kg_mpc_daily_pm25"] == 35.0
    assert isinstance(std["kg_mpc_daily_co"], float) and std["kg_mpc_daily_co"] == 3000.0


def test_require_raises_named_error_for_missing_id():
    std = S.load_standards()
    with pytest.raises(KeyError) as e:
        S.require(std, "who_aqg_pm25")
    assert "who_aqg_pm25" in str(e.value)


def test_load_standards_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        S.load_standards("catalog/does_not_exist.csv")


def test_validate_catalog_still_passes_with_standards():
    from catalog import validate_catalog as vc
    assert vc.validate() == []
```

- [ ] **Step 3: Run — verify fail**

Run: `.venv/Scripts/python -m pytest tests/test_standards.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'catalog.standards'`

- [ ] **Step 4: Write `catalog/standards.py`**

```python
from __future__ import annotations
import csv
from pathlib import Path

_REQUIRED_IDS = {"epa_aqi_unhealthy_pm25", "kg_mpc_daily_pm25"}
_KINDS = {"alert", "limit"}
_COLS = ["standard_id", "authority", "pollutant", "averaging_period",
         "value_ug_m3", "kind", "citation", "url", "notes"]


def _rows(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"standards file not found: {path}")
    with p.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_standards(path="catalog/standards.csv") -> dict[str, float]:
    out: dict[str, float] = {}
    for r in _rows(path):
        out[r["standard_id"]] = float(r["value_ug_m3"])
    return out


def require(standards: dict, standard_id: str) -> float:
    try:
        return standards[standard_id]
    except KeyError:
        raise KeyError(f"standards.csv missing required id: {standard_id}") from None


def problems(path="catalog/standards.csv") -> list[str]:
    out = []
    rows = _rows(path)
    if rows and list(rows[0].keys()) != _COLS:
        out.append(f"standards.csv columns != expected: {list(rows[0].keys())}")
    ids = set()
    for r in rows:
        sid = r.get("standard_id", "?")
        if sid in ids:
            out.append(f"standards.csv: duplicate id {sid}")
        ids.add(sid)
        if r.get("kind") not in _KINDS:
            out.append(f"{sid}: bad kind {r.get('kind')!r}")
        try:
            v = float(r["value_ug_m3"])
            if v <= 0:
                out.append(f"{sid}: value_ug_m3 must be > 0")
        except (KeyError, ValueError):
            out.append(f"{sid}: value_ug_m3 not a number")
        if not (r.get("url", "").startswith("http")):
            out.append(f"{sid}: url not a URL")
        if not r.get("citation"):
            out.append(f"{sid}: empty citation")
    for req in _REQUIRED_IDS:
        if req not in ids:
            out.append(f"standards.csv: missing required id {req}")
    return out
```

- [ ] **Step 5: Extend `catalog/validate_catalog.py`**

At the end of `validate()`, before `return problems`, add:

```python
    from catalog import standards as _std
    try:
        problems.extend(_std.problems(HERE / "standards.csv"))
    except FileNotFoundError:
        problems.append("standards.csv: file missing")
```

(`HERE` is the existing `Path(__file__).parent` in that module. Keep the existing `problems` list variable name; if the module uses a different name, adapt.)

- [ ] **Step 6: Run — verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_standards.py tests/test_validate_catalog.py -q`
Expected: PASS (all)

- [ ] **Step 7: Full suite + commit**

Run: `.venv/Scripts/python -m pytest -q` — expect all green (was 27, now +4).

```bash
git add catalog/standards.csv catalog/standards.py catalog/validate_catalog.py tests/test_standards.py
git commit -m "feat: cited threshold standards (US EPA + Kyrgyz) with loader and validator"
```

---

## Task 2: Rewire `fetch/build_dataset.py` thresholds

**Files:**
- Modify: `fetch/build_dataset.py`
- Modify: `tests/test_build_dataset.py`

**Interfaces:**
- Consumes: `catalog.standards.load_standards`, `catalog.standards.require` (Task 1).
- Produces:
  - `build_grid_dataset(proc_dir="data/processed", standards=None) -> DataFrame` — `standards` defaults to `load_standards()`; flags computed from `require(standards, "epa_aqi_unhealthy_pm25")` and `require(standards, "kg_mpc_daily_pm25")`.
  - `build_stations(proc_dir="data/processed", standards=None) -> DataFrame` — now also adds `dangerous_day` / `exceeds_kg_limit` nullable-boolean columns from `pm2_5` when `pm2_5` is a column.
  - `main` passes one `load_standards()` result into both.

- [ ] **Step 1: Write failing tests — append to `tests/test_build_dataset.py`**

```python
def test_grid_flags_use_standards_not_literals(tmp_path):
    import pandas as pd
    from fetch import build_dataset as bd
    g = pd.DataFrame({"cell_id": ["a", "a", "a"], "lat": [43.0]*3, "lon": [75.0]*3,
                      "date": pd.to_datetime(["2022-08-04", "2022-08-05", "2022-08-06"]),
                      "pm2_5": [30.0, 40.0, None], "n_hours_pm2_5": [24, 24, 0]})
    g.to_parquet(tmp_path / "openmeteo_grid_daily.parquet", index=False)
    fake_std = {"epa_aqi_unhealthy_pm25": 55.4, "kg_mpc_daily_pm25": 35.0}
    out = bd.build_grid_dataset(str(tmp_path), standards=fake_std).set_index("date")
    assert out.loc["2022-08-04", "exceeds_kg_limit"] == False
    assert out.loc["2022-08-05", "exceeds_kg_limit"] == True
    assert out.loc["2022-08-05", "dangerous_day"] == False
    assert pd.isna(out.loc["2022-08-06", "exceeds_kg_limit"])


def test_build_stations_gets_nullable_flags():
    import pandas as pd, pathlib
    from fetch import build_dataset as bd
    fix = pathlib.Path(__file__).parent / "fixtures" / "proc"
    df = bd.build_stations(str(fix), standards={"epa_aqi_unhealthy_pm25": 55.4,
                                                "kg_mpc_daily_pm25": 35.0})
    assert "dangerous_day" in df.columns and "exceeds_kg_limit" in df.columns
    b = df[df["station_key"] == "bishkek_us_embassy"].set_index("date")
    # fixture airnow row for 2021-01-02 is 120.0 -> both flags True
    assert b.loc["2021-01-02", "dangerous_day"] == True


def test_build_grid_raises_when_standard_id_missing(tmp_path):
    import pandas as pd, pytest
    from fetch import build_dataset as bd
    g = pd.DataFrame({"cell_id": ["a"], "lat": [43.0], "lon": [75.0],
                      "date": pd.to_datetime(["2022-08-04"]), "pm2_5": [30.0]})
    g.to_parquet(tmp_path / "openmeteo_grid_daily.parquet", index=False)
    with pytest.raises(KeyError):
        bd.build_grid_dataset(str(tmp_path), standards={"kg_mpc_daily_pm25": 35.0})
```

- [ ] **Step 2: Run — verify fail**

Run: `.venv/Scripts/python -m pytest tests/test_build_dataset.py -q`
Expected: FAIL — `build_grid_dataset()` has no `standards` kwarg / flags still hard-coded.

- [ ] **Step 3: Edit `fetch/build_dataset.py`**

Add import near the top:

```python
from catalog.standards import load_standards, require
```

Replace `build_grid_dataset`:

```python
def build_grid_dataset(proc_dir="data/processed", standards=None) -> pd.DataFrame:
    std = standards if standards is not None else load_standards()
    g = pd.read_parquet(Path(proc_dir) / "openmeteo_grid_daily.parquet")
    g["date"] = pd.to_datetime(g["date"])
    if "pm2_5" in g:
        danger = require(std, "epa_aqi_unhealthy_pm25")
        kg = require(std, "kg_mpc_daily_pm25")
        g["dangerous_day"] = (g["pm2_5"] > danger).astype("boolean").mask(g["pm2_5"].isna())
        g["exceeds_kg_limit"] = (g["pm2_5"] > kg).astype("boolean").mask(g["pm2_5"].isna())
    front = [c for c in ["cell_id", "lat", "lon", "date"] if c in g]
    rest = [c for c in g.columns if c not in front]
    return g[front + rest]
```

In `build_stations`, change the signature to `def build_stations(proc_dir="data/processed", standards=None) -> pd.DataFrame:` and, just before the final `return out.sort_values(...)`, add:

```python
    if "pm2_5" in out.columns:
        std = standards if standards is not None else load_standards()
        danger = require(std, "epa_aqi_unhealthy_pm25")
        kg = require(std, "kg_mpc_daily_pm25")
        pm = pd.to_numeric(out["pm2_5"], errors="coerce")
        out["dangerous_day"] = (pm > danger).astype("boolean").mask(pm.isna())
        out["exceeds_kg_limit"] = (pm > kg).astype("boolean").mask(pm.isna())
```

In `main`, replace the two calls:

```python
    std = load_standards()
    stations = build_stations(args.proc_dir, standards=std)
    ...
    grid = build_grid_dataset(args.proc_dir, standards=std)
```

Update `_DICT` entries:

```python
    "dangerous_day": ("derived", "boolean",
                      "pm2_5 > standards.epa_aqi_unhealthy_pm25",
                      "US EPA AQI Unhealthy lower bound (24-h PM2.5 55.4 µg/m³); "
                      "<NA> where pm2_5 is missing (not the same as False)"),
    "exceeds_kg_limit": ("derived", "boolean",
                         "pm2_5 > standards.kg_mpc_daily_pm25",
                         "Kyrgyz ПДК среднесуточная, ПП КР №201 (2016) поз. 613, 35 µg/m³; "
                         "<NA> where pm2_5 is missing (not the same as False)"),
```

- [ ] **Step 4: Run — verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_build_dataset.py -q`
Expected: PASS. Then `grep -n "55.4\|> 35" fetch/build_dataset.py` — should only match `_DICT` caveat text and comments, not the flag logic.

- [ ] **Step 5: Regenerate the committed dictionary + sample from the existing local grid**

Run: `.venv/Scripts/python -m fetch.build_dataset` (uses the local `data/processed/openmeteo_grid_daily.parquet` from predecessor work if present; if absent, skip and note it — Task 11 regenerates properly).
Check: `grep -c "TODO-REVIEW" dataset/data_dictionary.md` → `0`.

- [ ] **Step 6: Full suite + commit**

```bash
git add fetch/build_dataset.py tests/test_build_dataset.py dataset/data_dictionary.md dataset/grid_daily_sample.csv
git commit -m "feat: build_dataset reads pm2_5 thresholds from catalog/standards.csv; station-side danger flags"
```

---

## Task 3: `qa/` skeleton — `geo`, `loaders`, config files

**Files:**
- Create: `qa/__init__.py`, `qa/geo.py`, `qa/loaders.py`, `qa/thresholds.yaml`, `qa/reference_values.yaml`, `qa/checks/__init__.py`, `tests/test_qa_loaders.py`, `tests/fixtures/qa/` (crafted files below)

**Interfaces:**
- Consumes: `catalog.standards.load_standards`.
- Produces:
  - `qa/geo.py`: `BISHKEK_LAT = 42.8746`, `BISHKEK_LON = 74.5698`; `nearest_cell_id(grid_df, lat=BISHKEK_LAT, lon=BISHKEK_LON) -> str` — returns the `cell_id` of the row minimising squared degree distance; raises `ValueError` if `grid_df` is empty.
  - `qa/loaders.py`:
    - `@dataclass QAContext` with fields: `stations: pd.DataFrame`, `grid: pd.DataFrame`, `grid_long: pd.DataFrame | None`, `points: pd.DataFrame | None`, `openaq: dict[str, pd.DataFrame]`, `airnow: pd.DataFrame | None`, `zenodo: dict[str, pd.DataFrame]`, `standards: dict[str, float]`, `thresholds: dict`, `reference_values: dict`, `bishkek_cell_id: str | None`, `data_dictionary: str`.
    - `load_context(dataset_dir="dataset", proc_dir="data/processed", qa_dir="qa", kepler_dir="kepler") -> QAContext` — reads whatever exists; missing optional inputs become empty frames / `None`, never an exception. `grid["date"]` and `stations["date"]` parsed to datetime.
    - `AQ_VARS`, `WX_VARS` re-declared verbatim (same 8 + 6 as `fetch/build_dataset.py`).
    - `STATION_SCHEMA: dict[str, str]` and `GRID_SCHEMA: dict[str, str]` — column → dtype-family (`"float"`, `"int"`, `"bool"`, `"datetime"`, `"str"`) manifests used by `structure.py`.
  - `Finding` dataclass importable from `qa.checks` (`qa/checks/__init__.py`): fields `check_id: str`, `level: str` (`"PASS"|"WARN"|"FAIL"|"INFO"`), `summary: str`, `table: str | None = None`. Plus `LEVELS = ["PASS", "INFO", "WARN", "FAIL"]` for ordering.

- [ ] **Step 1: Write `qa/checks/__init__.py`**

```python
from __future__ import annotations
from dataclasses import dataclass

LEVELS = ["PASS", "INFO", "WARN", "FAIL"]


@dataclass
class Finding:
    check_id: str
    level: str
    summary: str
    table: str | None = None

    def __post_init__(self):
        if self.level not in LEVELS:
            raise ValueError(f"bad level {self.level!r}")
```

- [ ] **Step 2: Write `qa/geo.py`**

```python
from __future__ import annotations
import pandas as pd

BISHKEK_LAT = 42.8746
BISHKEK_LON = 74.5698


def nearest_cell_id(grid_df: pd.DataFrame, lat: float = BISHKEK_LAT,
                    lon: float = BISHKEK_LON) -> str:
    if grid_df is None or len(grid_df) == 0:
        raise ValueError("grid_df is empty; cannot pick a nearest cell")
    d = (grid_df["lat"] - lat) ** 2 + (grid_df["lon"] - lon) ** 2
    return str(grid_df.loc[d.idxmin(), "cell_id"])
```

- [ ] **Step 3: Write `qa/thresholds.yaml`**

```yaml
completeness:
  warn_pct: 80
  fail_pct: 50
gap:
  warn_days: 7
agreement:
  min_overlap_days: 30
  ground_r_warn: 0.80
  ground_bias_warn: 10.0
  ground_r_fail: 0.50
  model_r_warn: 0.40
seasonality:
  min_winter_summer_ratio: 2.0
plausibility:
  fail_fraction: 0.001
ranges:
  pm2_5: [0, 1000]
  pm10: [0, 2000]
  sulphur_dioxide: [0, 5000]
  nitrogen_dioxide: [0, 5000]
  carbon_monoxide: [0, 100000]
  ozone: [0, 1000]
  aerosol_optical_depth: [0, 5]
  dust: [0, 2000]
  temperature_2m: [-45, 50]
  relative_humidity_2m: [0, 100]
  wind_speed_10m: [0, 60]
  wind_direction_10m: [0, 360]
  surface_pressure: [600, 1050]
  boundary_layer_height: [0, 5000]
  temperature: [-45, 50]
  relative_humidity: [0, 100]
cams_boundary_date: "2022-08-04"
```

- [ ] **Step 4: Write `qa/reference_values.yaml`**

```yaml
bishkek_annual_pm25:
  low: 30
  high: 70
  cite: "WHO/IQAir/World Bank cite ~40-50 ug/m3 for the Bishkek airshed (annual)"
isaev_table4_exceed35:
  low: 52
  high: 93
  cite: "Isaev et al. 2022, Aerosol Air Qual. Res., doi:10.4209/aaqr.210336, Table 4 (days > 35 ug/m3 per heating season)"
```

- [ ] **Step 5: Write fixtures**

`tests/fixtures/qa/grid_min.parquet` — create in the test via pandas (2 cells, a few dates). `tests/fixtures/qa/stations_min.csv`:

```csv
station_key,date,pm2_5,n_hours_pm2_5,dangerous_day,exceeds_kg_limit
bishkek,2022-12-01,80.0,24,True,True
bishkek,2022-12-02,10.0,24,False,False
```

- [ ] **Step 6: Write the failing test — `tests/test_qa_loaders.py`**

```python
import pandas as pd
from qa import geo
from qa.loaders import load_context, AQ_VARS, WX_VARS


def test_nearest_cell_id_picks_closest():
    g = pd.DataFrame({"cell_id": ["43.0000_75.0000", "39.0000_66.0000"],
                      "lat": [43.0, 39.0], "lon": [75.0, 66.0]})
    assert geo.nearest_cell_id(g) == "43.0000_75.0000"


def test_var_lists_match_build_dataset():
    from fetch.build_dataset import AQ_VARS as A2, WX_VARS as W2
    assert AQ_VARS == A2 and WX_VARS == W2


def test_load_context_tolerates_missing_inputs(tmp_path):
    ctx = load_context(dataset_dir=str(tmp_path), proc_dir=str(tmp_path),
                       qa_dir="qa", kepler_dir=str(tmp_path))
    assert ctx.grid.empty and ctx.stations.empty
    assert ctx.standards["epa_aqi_unhealthy_pm25"] == 55.4
    assert ctx.thresholds["completeness"]["warn_pct"] == 80
    assert ctx.reference_values["isaev_table4_exceed35"]["low"] == 52
```

- [ ] **Step 7: Run — verify fail**

Run: `.venv/Scripts/python -m pytest tests/test_qa_loaders.py -q`
Expected: FAIL — `qa.loaders` missing.

- [ ] **Step 8: Write `qa/loaders.py`**

```python
from __future__ import annotations
import glob
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from catalog.standards import load_standards
from qa import geo

AQ_VARS = ["pm2_5", "pm10", "carbon_monoxide", "nitrogen_dioxide",
           "sulphur_dioxide", "ozone", "aerosol_optical_depth", "dust"]
WX_VARS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
           "wind_direction_10m", "surface_pressure", "boundary_layer_height"]

STATION_SCHEMA = {"station_key": "str", "date": "datetime", "pm2_5": "float",
                  "n_hours_pm2_5": "float", "dangerous_day": "bool",
                  "exceeds_kg_limit": "bool"}
GRID_SCHEMA = {"cell_id": "str", "lat": "float", "lon": "float", "date": "datetime",
               "pm2_5": "float", "dangerous_day": "bool", "exceeds_kg_limit": "bool"}


@dataclass
class QAContext:
    stations: pd.DataFrame
    grid: pd.DataFrame
    grid_long: pd.DataFrame | None
    points: pd.DataFrame | None
    openaq: dict = field(default_factory=dict)
    airnow: pd.DataFrame | None = None
    zenodo: dict = field(default_factory=dict)
    standards: dict = field(default_factory=dict)
    thresholds: dict = field(default_factory=dict)
    reference_values: dict = field(default_factory=dict)
    bishkek_cell_id: str | None = None
    data_dictionary: str = ""


def _csv(path):
    p = Path(path)
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def _parquet(path):
    p = Path(path)
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def _yaml(path):
    p = Path(path)
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_context(dataset_dir="dataset", proc_dir="data/processed",
                 qa_dir="qa", kepler_dir="kepler") -> QAContext:
    stations = _csv(f"{dataset_dir}/stations_daily.csv")
    grid = _parquet(f"{dataset_dir}/grid_daily.parquet")
    for df in (stations, grid):
        if not df.empty and "date" in df:
            df["date"] = pd.to_datetime(df["date"])
    grid_long = _parquet(f"{kepler_dir}/grid_daily_long.parquet")
    points = _csv(f"{proc_dir}/openmeteo_points_daily.csv")
    openaq = {}
    for fp in sorted(glob.glob(f"{proc_dir}/openaq_*_daily.csv")):
        openaq[Path(fp).stem.replace("openaq_", "").replace("_daily", "")] = pd.read_csv(fp)
    airnow = _csv(f"{proc_dir}/airnow_bishkek_daily.csv")
    zenodo = {}
    for name in ("zenodo_bishkek_us_embassy_daily", "zenodo_clarity_bishkek_daily"):
        d = _csv(f"{proc_dir}/{name}.csv")
        if not d.empty:
            zenodo[name] = d
    dd = Path(f"{dataset_dir}/data_dictionary.md")
    cell = None
    if not grid.empty:
        try:
            cell = geo.nearest_cell_id(grid)
        except ValueError:
            cell = None
    return QAContext(
        stations=stations, grid=grid,
        grid_long=grid_long if not grid_long.empty else None,
        points=points if not points.empty else None,
        openaq=openaq, airnow=airnow if not airnow.empty else None,
        zenodo=zenodo, standards=load_standards(),
        thresholds=_yaml(f"{qa_dir}/thresholds.yaml"),
        reference_values=_yaml(f"{qa_dir}/reference_values.yaml"),
        bishkek_cell_id=cell,
        data_dictionary=dd.read_text(encoding="utf-8") if dd.exists() else "")
```

- [ ] **Step 9: Run — verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_qa_loaders.py -q`
Expected: PASS (3 passed)

- [ ] **Step 10: Commit**

```bash
git add qa/ tests/test_qa_loaders.py tests/fixtures/qa/
git commit -m "feat: qa package skeleton — geo, loaders, thresholds and reference-value config"
```

---

## Task 4: `qa/checks/structure.py`

**Files:**
- Create: `qa/checks/structure.py`, `tests/test_qa_structure.py`

**Interfaces:**
- Consumes: `QAContext`, `Finding`, `qa.checks.LEVELS`, `catalog.standards.require`.
- Produces: `run(ctx) -> list[Finding]`. `check_id` values: `structure.schema_stations`, `structure.schema_grid`, `structure.keys_unique`, `structure.flag_consistency`, `structure.n_hours_bounds`, `structure.dict_coverage`, `structure.grid_bbox`, `structure.kepler_long`.

- [ ] **Step 1: Write the failing test — `tests/test_qa_structure.py`**

```python
import pandas as pd
from qa.checks import Finding
from qa.checks import structure
from qa.loaders import QAContext


def _ctx(**kw):
    base = dict(stations=pd.DataFrame(), grid=pd.DataFrame(), grid_long=None,
                points=None, openaq={}, airnow=None, zenodo={},
                standards={"epa_aqi_unhealthy_pm25": 55.4, "kg_mpc_daily_pm25": 35.0},
                thresholds={}, reference_values={}, bishkek_cell_id=None,
                data_dictionary="")
    base.update(kw)
    return QAContext(**base)


def test_flag_consistency_flags_mismatch():
    grid = pd.DataFrame({"cell_id": ["a", "a"], "lat": [43.0, 43.0], "lon": [75.0, 75.0],
                         "date": pd.to_datetime(["2022-12-01", "2022-12-02"]),
                         "pm2_5": [80.0, 10.0],
                         "dangerous_day": pd.array([False, False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([True, False], dtype="boolean")})
    out = {f.check_id: f for f in structure.run(_ctx(grid=grid))}
    assert out["structure.flag_consistency"].level == "FAIL"  # 80>55.4 but dangerous_day False


def test_grid_bbox_flags_out_of_range():
    grid = pd.DataFrame({"cell_id": ["x"], "lat": [60.0], "lon": [75.0],
                         "date": pd.to_datetime(["2022-12-01"]), "pm2_5": [10.0],
                         "dangerous_day": pd.array([False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([False], dtype="boolean")})
    out = {f.check_id: f for f in structure.run(_ctx(grid=grid))}
    assert out["structure.grid_bbox"].level == "FAIL"


def test_keys_unique_flags_dupes():
    grid = pd.DataFrame({"cell_id": ["a", "a"], "lat": [43.0, 43.0], "lon": [75.0, 75.0],
                         "date": pd.to_datetime(["2022-12-01", "2022-12-01"]),
                         "pm2_5": [10.0, 11.0],
                         "dangerous_day": pd.array([False, False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([False, False], dtype="boolean")})
    out = {f.check_id: f for f in structure.run(_ctx(grid=grid))}
    assert out["structure.keys_unique"].level == "FAIL"


def test_clean_grid_passes_core_checks():
    grid = pd.DataFrame({"cell_id": ["a", "a"], "lat": [43.0, 43.0], "lon": [75.0, 75.0],
                         "date": pd.to_datetime(["2022-12-01", "2022-12-02"]),
                         "pm2_5": [80.0, 10.0], "n_hours_pm2_5": [24, 24],
                         "sparse": [False, False],
                         "dangerous_day": pd.array([True, False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([True, False], dtype="boolean")})
    out = {f.check_id: f for f in structure.run(_ctx(grid=grid,
              data_dictionary="| cell_id | | | | |\n| pm2_5 | | | | |"))}
    assert out["structure.flag_consistency"].level in ("PASS", "INFO")
    assert out["structure.keys_unique"].level == "PASS"
    assert out["structure.grid_bbox"].level == "PASS"
```

- [ ] **Step 2: Run — verify fail**

Run: `.venv/Scripts/python -m pytest tests/test_qa_structure.py -q`
Expected: FAIL — `qa.checks.structure` missing.

- [ ] **Step 3: Write `qa/checks/structure.py`**

```python
from __future__ import annotations
import pandas as pd

from qa.checks import Finding
from qa.loaders import STATION_SCHEMA, GRID_SCHEMA, AQ_VARS, WX_VARS
from catalog.standards import require


def _schema_finding(cid, df, schema):
    if df is None or df.empty:
        return Finding(cid, "INFO", "frame empty — schema not checked")
    missing = [c for c in schema if c not in df.columns]
    if missing:
        return Finding(cid, "FAIL", f"missing columns: {missing}")
    return Finding(cid, "PASS", f"{len(schema)} expected columns present")


def _keys_unique(cid, df, keys):
    if df is None or df.empty:
        return Finding(cid, "INFO", "frame empty")
    have = [k for k in keys if k in df.columns]
    if len(have) < len(keys):
        return Finding(cid, "INFO", f"key columns absent: {set(keys) - set(have)}")
    dup = df.duplicated(subset=have).sum()
    if dup:
        ex = df[df.duplicated(subset=have, keep=False)].head(6)
        return Finding(cid, "FAIL", f"{dup} duplicate {have} rows",
                       ex[have].to_markdown(index=False))
    return Finding(cid, "PASS", f"{have} unique over {len(df)} rows")


def _flag_consistency(cid, df, danger, kg):
    if df is None or df.empty or "pm2_5" not in df.columns:
        return Finding(cid, "INFO", "no pm2_5 to check flags against")
    pm = pd.to_numeric(df["pm2_5"], errors="coerce")
    bad = 0
    for col, thr in (("dangerous_day", danger), ("exceeds_kg_limit", kg)):
        if col not in df.columns:
            return Finding(cid, "FAIL", f"missing flag column {col}")
        exp = (pm > thr)
        got = df[col]
        nn = pm.notna()
        mism = int(((got[nn].astype("float") != exp[nn].astype("float"))).sum())
        na_bad = int((got[~nn].notna()).sum())  # should be NA where pm2_5 NA
        bad += mism + na_bad
    if bad:
        return Finding(cid, "FAIL", f"{bad} rows where a flag != (pm2_5 > threshold) "
                                    f"or a flag is set where pm2_5 is missing")
    return Finding(cid, "PASS", "dangerous_day / exceeds_kg_limit consistent with pm2_5")


def _n_hours(cid, df):
    if df is None or df.empty:
        return Finding(cid, "INFO", "frame empty")
    cols = [c for c in df.columns if c.startswith("n_hours_")]
    if not cols:
        return Finding(cid, "INFO", "no n_hours_* columns")
    bad = 0
    for c in cols:
        v = pd.to_numeric(df[c], errors="coerce")
        bad += int(((v < 0) | (v > 24)).sum())
    if "sparse" in df.columns:
        anylow = pd.concat([pd.to_numeric(df[c], errors="coerce") < 18 for c in cols],
                           axis=1).any(axis=1)
        sparse_bad = int((df["sparse"].astype("boolean").fillna(False) != anylow.fillna(False)).sum())
    else:
        sparse_bad = 0
    if bad or sparse_bad:
        return Finding(cid, "FAIL", f"{bad} n_hours outside [0,24]; {sparse_bad} sparse mismatches")
    return Finding(cid, "PASS", f"{len(cols)} n_hours_* columns in range; sparse consistent")


def _dict_coverage(cid, df, dd_text):
    if df is None or df.empty:
        return Finding(cid, "INFO", "frame empty")
    if not dd_text:
        return Finding(cid, "WARN", "data_dictionary.md not found")
    missing = [c for c in df.columns if f"| {c} " not in dd_text]
    todo = dd_text.count("TODO-REVIEW")
    if missing or todo:
        return Finding(cid, "FAIL", f"undocumented columns: {missing}; TODO-REVIEW rows: {todo}")
    return Finding(cid, "PASS", f"all {len(df.columns)} columns documented; no TODO-REVIEW")


def _grid_bbox(cid, df):
    if df is None or df.empty or "lat" not in df.columns:
        return Finding(cid, "INFO", "no grid")
    bad = int(((df["lat"] < 39) | (df["lat"] > 52) |
               (df["lon"] < 66) | (df["lon"] > 80)).sum())
    if bad:
        return Finding(cid, "FAIL", f"{bad} cells outside bbox lat[39,52] lon[66,80]")
    return Finding(cid, "PASS", "all cells within region bbox")


def _kepler_long(cid, long_df):
    if long_df is None or long_df.empty:
        return Finding(cid, "INFO", "grid_daily_long absent")
    ok_vars = set(AQ_VARS + WX_VARS)
    bad_vars = sorted(set(long_df["variable"]) - ok_vars)
    nulls = int(long_df["value"].isna().sum())
    dup = int(long_df.duplicated(subset=["cell_id", "date", "variable"]).sum())
    if bad_vars or nulls or dup:
        return Finding(cid, "FAIL", f"unexpected vars {bad_vars}; {nulls} null values; {dup} dup keys")
    return Finding(cid, "PASS", f"{len(long_df)} rows, {long_df['variable'].nunique()} vars, clean")


def run(ctx) -> list[Finding]:
    danger = require(ctx.standards, "epa_aqi_unhealthy_pm25")
    kg = require(ctx.standards, "kg_mpc_daily_pm25")
    return [
        _schema_finding("structure.schema_stations", ctx.stations, STATION_SCHEMA),
        _schema_finding("structure.schema_grid", ctx.grid, GRID_SCHEMA),
        _keys_unique("structure.keys_unique", ctx.grid, ["cell_id", "date"]),
        _keys_unique("structure.keys_unique_stations", ctx.stations, ["station_key", "date"]),
        _flag_consistency("structure.flag_consistency", ctx.grid, danger, kg),
        _n_hours("structure.n_hours_bounds", ctx.grid),
        _dict_coverage("structure.dict_coverage", ctx.grid, ctx.data_dictionary),
        _grid_bbox("structure.grid_bbox", ctx.grid),
        _kepler_long("structure.kepler_long", ctx.grid_long),
    ]
```

- [ ] **Step 4: Run — verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_qa_structure.py -q`
Expected: PASS (4 passed). Fix `_flag_consistency` NA-handling until `test_clean_grid_passes_core_checks` and `test_flag_consistency_flags_mismatch` both pass.

- [ ] **Step 5: Commit**

```bash
git add qa/checks/structure.py tests/test_qa_structure.py
git commit -m "feat: qa structure checks — schema, key uniqueness, flag consistency, dict coverage, bbox"
```

---

## Task 5: `qa/checks/plausibility.py`

**Files:**
- Create: `qa/checks/plausibility.py`, `tests/test_qa_plausibility.py`

**Interfaces:**
- Consumes: `QAContext`, `Finding`.
- Produces: `run(ctx) -> list[Finding]`. `check_id`: `plausibility.ranges_grid`, `plausibility.ranges_stations`, `plausibility.completeness`, `plausibility.duplicate_keys`, `plausibility.date_gaps`, `plausibility.cams_boundary`.

- [ ] **Step 1: Write the failing test — `tests/test_qa_plausibility.py`**

```python
import pandas as pd
from qa.checks import plausibility
from qa.loaders import QAContext

TH = {"completeness": {"warn_pct": 80, "fail_pct": 50}, "gap": {"warn_days": 7},
      "plausibility": {"fail_fraction": 0.001},
      "ranges": {"pm2_5": [0, 1000], "relative_humidity_2m": [0, 100]},
      "cams_boundary_date": "2022-08-04"}


def _ctx(**kw):
    base = dict(stations=pd.DataFrame(), grid=pd.DataFrame(), grid_long=None, points=None,
                openaq={}, airnow=None, zenodo={}, standards={}, thresholds=TH,
                reference_values={}, bishkek_cell_id="43.0000_75.0000", data_dictionary="")
    base.update(kw)
    return QAContext(**base)


def test_ranges_flag_negative_pm25():
    grid = pd.DataFrame({"cell_id": ["a"] * 4, "lat": [43.0] * 4, "lon": [75.0] * 4,
                         "date": pd.to_datetime(["2022-08-04", "2022-08-05", "2022-08-06", "2022-08-07"]),
                         "pm2_5": [10.0, -5.0, 20.0, 3000.0]})
    out = {f.check_id: f for f in plausibility.run(_ctx(grid=grid))}
    assert out["plausibility.ranges_grid"].level == "FAIL"  # 2 of 4 = 50% > 0.1%


def test_cams_boundary_flags_gas_before_start():
    grid = pd.DataFrame({"cell_id": ["43.0000_75.0000"] * 2, "lat": [43.0] * 2, "lon": [75.0] * 2,
                         "date": pd.to_datetime(["2021-01-01", "2022-09-01"]),
                         "pm2_5": [12.0, 40.0], "sulphur_dioxide": [3.0, 5.0]})
    out = {f.check_id: f for f in plausibility.run(_ctx(grid=grid))}
    assert out["plausibility.cams_boundary"].level == "FAIL"  # pm2_5 present 2021 (pre-boundary)


def test_completeness_reports_low_season_as_warn():
    days = pd.date_range("2022-11-01", "2023-03-31", freq="D")
    grid = pd.DataFrame({"cell_id": ["43.0000_75.0000"] * len(days),
                         "lat": [43.0] * len(days), "lon": [75.0] * len(days),
                         "date": days,
                         "pm2_5": [10.0] * 20 + [None] * (len(days) - 20)})
    out = {f.check_id: f for f in plausibility.run(_ctx(grid=grid))}
    assert out["plausibility.completeness"].level in ("WARN", "FAIL")
    assert out["plausibility.completeness"].table is not None
```

- [ ] **Step 2: Run — verify fail**

Run: `.venv/Scripts/python -m pytest tests/test_qa_plausibility.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `qa/checks/plausibility.py`**

```python
from __future__ import annotations
import pandas as pd

from qa.checks import Finding
from qa.loaders import AQ_VARS, WX_VARS

_HEATING_MONTHS = {11, 12, 1, 2, 3}


def _ranges(cid, df, ranges, fail_frac):
    if df is None or df.empty:
        return Finding(cid, "INFO", "frame empty")
    total_bad = 0
    total_n = 0
    rows = []
    for var, (lo, hi) in ranges.items():
        if var not in df.columns:
            continue
        v = pd.to_numeric(df[var], errors="coerce")
        n = int(v.notna().sum())
        bad = int(((v < lo) | (v > hi)).sum())
        total_bad += bad
        total_n += n
        if bad:
            rows.append(f"| {var} | {bad} | {n} | [{lo}, {hi}] |")
    if total_n == 0:
        return Finding(cid, "INFO", "no numeric data in ranged columns")
    frac = total_bad / total_n
    table = None
    if rows:
        table = "| variable | out-of-range | non-null | bounds |\n|---|---|---|---|\n" + "\n".join(rows)
    if frac > fail_frac:
        return Finding(cid, "FAIL", f"{total_bad}/{total_n} ({frac:.2%}) values out of physical range", table)
    if total_bad:
        return Finding(cid, "WARN", f"{total_bad}/{total_n} ({frac:.3%}) values out of range", table)
    return Finding(cid, "PASS", f"all {total_n} values within physical bounds")


def _completeness(cid, df, key_col, warn_pct, fail_pct):
    if df is None or df.empty or "date" not in df.columns:
        return Finding(cid, "INFO", "frame empty")
    d = df.copy()
    d["year"] = d["date"].dt.year
    vars_present = [v for v in AQ_VARS + WX_VARS + ["pm2_5"] if v in d.columns]
    vars_present = list(dict.fromkeys(vars_present))
    per_key = d[key_col].nunique() if key_col in d.columns else 1
    rows = []
    worst = 100.0
    for (yr,), g in d.groupby(["year"]):
        span = (g["date"].max() - g["date"].min()).days + 1
        expected = max(span, 1) * per_key
        for v in vars_present:
            got = int(pd.to_numeric(g[v], errors="coerce").notna().sum())
            pct = 100.0 * got / expected if expected else 0.0
            rows.append((yr, v, round(pct, 1)))
            worst = min(worst, pct)
    table = ("| year | variable | % present |\n|---|---|---|\n" +
             "\n".join(f"| {y} | {v} | {p} |" for y, v, p in rows))
    if worst < fail_pct:
        return Finding(cid, "WARN", f"lowest year/var coverage {worst:.0f}% (< {fail_pct}% floor; "
                                    "may be legit CAMS pre-2022-08 gap — see table)", table)
    if worst < warn_pct:
        return Finding(cid, "WARN", f"lowest year/var coverage {worst:.0f}% (< {warn_pct}%)", table)
    return Finding(cid, "PASS", f"all year/var coverage >= {warn_pct}%", table)


def _dupes(cid, df, keys):
    if df is None or df.empty:
        return Finding(cid, "INFO", "frame empty")
    have = [k for k in keys if k in df.columns]
    if len(have) < len(keys):
        return Finding(cid, "INFO", f"key columns absent")
    n = int(df.duplicated(subset=have).sum())
    return Finding(cid, "FAIL" if n else "PASS",
                   f"{n} duplicate {have}" if n else f"{have} unique")


def _gaps(cid, df, key_col, warn_days):
    if df is None or df.empty or "date" not in df.columns:
        return Finding(cid, "INFO", "frame empty")
    keys = df[key_col].unique() if key_col in df.columns else [None]
    worst = 0
    for k in keys:
        sub = df if k is None else df[df[key_col] == k]
        ds = sub["date"].dropna().sort_values().drop_duplicates()
        if len(ds) < 2:
            continue
        worst = max(worst, int(ds.diff().dt.days.max()))
    if worst > warn_days:
        return Finding(cid, "WARN", f"largest interior date gap = {worst} days (> {warn_days})")
    return Finding(cid, "PASS", f"largest date gap = {worst} days")


def _cams_boundary(cid, grid, cell_id, boundary):
    if grid is None or grid.empty or cell_id is None:
        return Finding(cid, "INFO", "no grid / no Bishkek cell")
    b = pd.Timestamp(boundary)
    sub = grid[grid["cell_id"] == cell_id]
    if sub.empty:
        return Finding(cid, "INFO", "Bishkek cell not in grid")
    rows, bad = [], 0
    for v in AQ_VARS:
        if v not in sub.columns:
            continue
        s = pd.to_numeric(sub.set_index("date")[v], errors="coerce")
        pre = int(s[s.index < b].notna().sum())
        first = s[s.notna()].index.min()
        rows.append(f"| {v} | {pre} | {first.date() if pd.notna(first) else 'never'} |")
        if pre > 0:
            bad += 1
    table = "| gas | non-null values before boundary | first non-null date |\n|---|---|---|\n" + "\n".join(rows)
    if bad:
        return Finding(cid, "FAIL", f"{bad} gas var(s) have data before the CAMS boundary {boundary} "
                                    "— indicates a merge/source bug", table)
    return Finding(cid, "INFO", f"CAMS gases start on/after {boundary} at the Bishkek cell (expected)", table)


def run(ctx) -> list[Finding]:
    th = ctx.thresholds
    ranges = th.get("ranges", {})
    ff = th.get("plausibility", {}).get("fail_fraction", 0.001)
    comp = th.get("completeness", {})
    return [
        _ranges("plausibility.ranges_grid", ctx.grid, ranges, ff),
        _ranges("plausibility.ranges_stations", ctx.stations, ranges, ff),
        _completeness("plausibility.completeness", ctx.grid, "cell_id",
                      comp.get("warn_pct", 80), comp.get("fail_pct", 50)),
        _dupes("plausibility.duplicate_keys", ctx.grid, ["cell_id", "date"]),
        _gaps("plausibility.date_gaps", ctx.grid, "cell_id",
              th.get("gap", {}).get("warn_days", 7)),
        _cams_boundary("plausibility.cams_boundary", ctx.grid, ctx.bishkek_cell_id,
                       th.get("cams_boundary_date", "2022-08-04")),
    ]
```

- [ ] **Step 4: Run — verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_qa_plausibility.py -q`
Expected: PASS (3 passed). Adjust `_completeness`'s `expected` denominator until the low-season test lands on WARN.

- [ ] **Step 5: Commit**

```bash
git add qa/checks/plausibility.py tests/test_qa_plausibility.py
git commit -m "feat: qa plausibility checks — ranges, completeness, dupes, gaps, CAMS boundary"
```

---

## Task 6: `qa/checks/agreement.py`

**Files:**
- Create: `qa/checks/agreement.py`, `tests/test_qa_agreement.py`

**Interfaces:**
- Consumes: `QAContext`, `Finding`.
- Produces:
  - `bishkek_series(ctx) -> dict[str, pd.Series]` — date-indexed daily pm2_5 for keys present among `"cams_grid"`, `"airnow"`, `"openaq"`, `"zenodo"`.
  - `pair_stats(a: pd.Series, b: pd.Series) -> dict` — `{n, r, bias, rmse, mae}` on the inner-joined non-null overlap.
  - `run(ctx) -> list[Finding]`. `check_id`: `agreement.pairwise`, `agreement.exceedance_counts`.

- [ ] **Step 1: Write the failing test — `tests/test_qa_agreement.py`**

```python
import numpy as np, pandas as pd
from qa.checks import agreement
from qa.loaders import QAContext

TH = {"agreement": {"min_overlap_days": 5, "ground_r_warn": 0.8, "ground_bias_warn": 10.0,
                    "ground_r_fail": 0.5, "model_r_warn": 0.4}}


def _ctx(**kw):
    base = dict(stations=pd.DataFrame(), grid=pd.DataFrame(), grid_long=None, points=None,
                openaq={}, airnow=None, zenodo={}, standards={"epa_aqi_unhealthy_pm25": 55.4,
                "kg_mpc_daily_pm25": 35.0}, thresholds=TH, reference_values={},
                bishkek_cell_id="43.0000_75.0000", data_dictionary="")
    base.update(kw)
    return QAContext(**base)


def test_pair_stats_basic():
    idx = pd.date_range("2022-01-01", periods=10)
    a = pd.Series(np.arange(10.0), index=idx)
    b = pd.Series(np.arange(10.0) + 2, index=idx)
    st = agreement.pair_stats(a, b)
    assert st["n"] == 10
    assert abs(st["r"] - 1.0) < 1e-9
    assert abs(st["bias"] - (-2.0)) < 1e-9


def test_ground_pair_low_r_is_fail():
    idx = pd.date_range("2022-01-01", periods=30)
    rng = np.random.default_rng(0)
    oa = pd.DataFrame({"date": idx, "pm2_5": rng.normal(50, 10, 30)})
    an = pd.DataFrame({"date": idx, "pm2_5": rng.normal(50, 10, 30)})  # independent -> r~0
    out = {f.check_id: f for f in agreement.run(_ctx(openaq={"bishkek": oa}, airnow=an))}
    assert out["agreement.pairwise"].level == "FAIL"
```

- [ ] **Step 2: Run — verify fail**

Run: `.venv/Scripts/python -m pytest tests/test_qa_agreement.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `qa/checks/agreement.py`**

```python
from __future__ import annotations
import numpy as np
import pandas as pd

from qa.checks import Finding


def _daily_pm(df):
    if df is None or df.empty or "pm2_5" not in df.columns or "date" not in df.columns:
        return None
    s = df.copy()
    s["date"] = pd.to_datetime(s["date"])
    return pd.to_numeric(s.set_index("date")["pm2_5"], errors="coerce").dropna().sort_index()


def bishkek_series(ctx) -> dict:
    out = {}
    if ctx.grid is not None and not ctx.grid.empty and ctx.bishkek_cell_id:
        g = ctx.grid[ctx.grid["cell_id"] == ctx.bishkek_cell_id]
        s = _daily_pm(g)
        if s is not None and len(s):
            out["cams_grid"] = s
    if ctx.airnow is not None:
        s = _daily_pm(ctx.airnow)
        if s is not None and len(s):
            out["airnow"] = s
    for name, df in (ctx.openaq or {}).items():
        if "bishkek" in name.lower():
            s = _daily_pm(df)
            if s is not None and len(s):
                out["openaq"] = s
    for name, df in (ctx.zenodo or {}).items():
        if "embassy" in name.lower():
            s = _daily_pm(df)
            if s is not None and len(s):
                out["zenodo"] = s
    return out


def pair_stats(a: pd.Series, b: pd.Series) -> dict:
    m = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    if len(m) < 2:
        return {"n": len(m), "r": float("nan"), "bias": float("nan"),
                "rmse": float("nan"), "mae": float("nan")}
    diff = m["a"] - m["b"]
    return {"n": int(len(m)), "r": float(m["a"].corr(m["b"])),
            "bias": float(diff.mean()),
            "rmse": float(np.sqrt((diff ** 2).mean())),
            "mae": float(diff.abs().mean())}


_GROUND = {"airnow", "openaq", "zenodo"}


def run(ctx) -> list[Finding]:
    th = ctx.thresholds.get("agreement", {})
    minov = th.get("min_overlap_days", 30)
    series = bishkek_series(ctx)
    if len(series) < 2:
        return [Finding("agreement.pairwise", "INFO",
                        f"only {len(series)} Bishkek pm2_5 source(s) — need >= 2")]
    names = sorted(series)
    rows, worst = [], "PASS"
    order = {"PASS": 0, "INFO": 1, "WARN": 2, "FAIL": 3}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            st = pair_stats(series[a], series[b])
            rows.append(f"| {a} vs {b} | {st['n']} | {st['r']:.3f} | {st['bias']:.2f} | "
                        f"{st['rmse']:.2f} | {st['mae']:.2f} |")
            if st["n"] < minov:
                continue
            both_ground = a in _GROUND and b in _GROUND
            if both_ground:
                if st["r"] < th.get("ground_r_fail", 0.5):
                    worst = "FAIL"
                elif (st["r"] < th.get("ground_r_warn", 0.8)
                      or abs(st["bias"]) > th.get("ground_bias_warn", 10.0)):
                    worst = "FAIL" if worst == "FAIL" else "WARN"
            else:  # model vs ground
                if st["r"] < th.get("model_r_warn", 0.4) or st["bias"] > 0:
                    worst = "FAIL" if worst == "FAIL" else "WARN"
    table = ("| pair | n | Pearson r | bias (a-b) | RMSE | MAE |\n|---|---|---|---|---|---|\n"
             + "\n".join(rows))
    summ = ("ground pairs must agree closely; model (cams_grid) is expected to "
            "under-estimate — a positive model bias or low r is flagged")
    findings = [Finding("agreement.pairwise", worst if worst != "PASS" else "PASS", summ, table)]

    danger = ctx.standards["epa_aqi_unhealthy_pm25"]
    kg = ctx.standards["kg_mpc_daily_pm25"]
    erows = [f"| {n} | {int((s > danger).sum())} | {int((s > kg).sum())} | {len(s)} |"
             for n, s in series.items()]
    findings.append(Finding("agreement.exceedance_counts", "INFO",
        "days each Bishkek source calls dangerous (>55.4) / over the KG limit (>35)",
        "| source | days >55.4 | days >35 | total days |\n|---|---|---|---|\n" + "\n".join(erows)))
    return findings
```

- [ ] **Step 4: Run — verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_qa_agreement.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add qa/checks/agreement.py tests/test_qa_agreement.py
git commit -m "feat: qa agreement checks — pairwise r/bias/RMSE across Bishkek pm2_5 sources"
```

---

## Task 7: `qa/checks/reference.py`

**Files:**
- Create: `qa/checks/reference.py`, `tests/test_qa_reference.py`

**Interfaces:**
- Consumes: `QAContext`, `Finding`, `qa.checks.agreement.bishkek_series` (reuse the best ground series).
- Produces:
  - `best_ground_series(ctx) -> tuple[str, pd.Series] | tuple[None, None]` — prefers `airnow`, then `openaq`, then `zenodo` from `agreement.bishkek_series`.
  - `heating_season(ts) -> int` — the year the Nov–Mar season starts in (Jan–Jun belong to the previous year's season).
  - `run(ctx) -> list[Finding]`. `check_id`: `reference.annual_mean`, `reference.exceedance_days`, `reference.seasonal_cycle`, `reference.model_vs_ground_gap`.

- [ ] **Step 1: Write the failing test — `tests/test_qa_reference.py`**

```python
import numpy as np, pandas as pd
from qa.checks import reference
from qa.loaders import QAContext

REF = {"bishkek_annual_pm25": {"low": 30, "high": 70, "cite": "x"},
       "isaev_table4_exceed35": {"low": 52, "high": 93, "cite": "Isaev T4"}}
TH = {"seasonality": {"min_winter_summer_ratio": 2.0}, "agreement": {}}


def _ctx(**kw):
    base = dict(stations=pd.DataFrame(), grid=pd.DataFrame(), grid_long=None, points=None,
                openaq={}, airnow=None, zenodo={}, standards={"epa_aqi_unhealthy_pm25": 55.4,
                "kg_mpc_daily_pm25": 35.0}, thresholds=TH, reference_values=REF,
                bishkek_cell_id="43.0000_75.0000", data_dictionary="")
    base.update(kw)
    return QAContext(**base)


def test_heating_season_boundary():
    assert reference.heating_season(pd.Timestamp("2022-12-15")) == 2022
    assert reference.heating_season(pd.Timestamp("2023-02-15")) == 2022
    assert reference.heating_season(pd.Timestamp("2023-08-15")) == 2023


def test_annual_mean_out_of_band_warns():
    idx = pd.date_range("2023-01-01", "2023-12-31")
    an = pd.DataFrame({"date": idx, "pm2_5": [200.0] * len(idx)})  # mean 200 -> above high 70
    out = {f.check_id: f for f in reference.run(_ctx(airnow=an))}
    assert out["reference.annual_mean"].level == "WARN"


def test_seasonal_cycle_ground_flat_is_fail():
    idx = pd.date_range("2022-07-01", "2023-06-30")
    an = pd.DataFrame({"date": idx, "pm2_5": [40.0] * len(idx)})  # flat -> ratio 1.0
    out = {f.check_id: f for f in reference.run(_ctx(airnow=an))}
    assert out["reference.seasonal_cycle"].level == "FAIL"
```

- [ ] **Step 2: Run — verify fail**

Run: `.venv/Scripts/python -m pytest tests/test_qa_reference.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `qa/checks/reference.py`**

```python
from __future__ import annotations
import pandas as pd

from qa.checks import Finding
from qa.checks.agreement import bishkek_series


def heating_season(ts) -> int:
    ts = pd.Timestamp(ts)
    return ts.year if ts.month >= 7 else ts.year - 1


def best_ground_series(ctx):
    s = bishkek_series(ctx)
    for k in ("airnow", "openaq", "zenodo"):
        if k in s and len(s[k]):
            return k, s[k]
    return None, None


def _annual_mean(cid, name, series, ref):
    if series is None:
        return Finding(cid, "INFO", "no Bishkek ground series")
    band = ref.get("bishkek_annual_pm25", {})
    lo, hi = band.get("low", 0), band.get("high", 1e9)
    rows, level = [], "PASS"
    for yr, g in series.groupby(series.index.year):
        m = float(g.mean())
        outb = m < lo or m > hi
        rows.append(f"| {yr} | {m:.1f} | {int(g.count())} | {'OUT' if outb else 'ok'} |")
        if outb:
            level = "WARN"
    table = f"| year | mean pm2_5 | days | vs [{lo},{hi}] |\n|---|---|---|---|\n" + "\n".join(rows)
    return Finding(cid, level, f"annual mean pm2_5 ({name}) vs published band [{lo},{hi}] "
                               f"({band.get('cite','')})", table)


def _exceedance_days(cid, name, series, std, ref):
    if series is None:
        return Finding(cid, "INFO", "no Bishkek ground series")
    danger = std["epa_aqi_unhealthy_pm25"]
    kg = std["kg_mpc_daily_pm25"]
    band = ref.get("isaev_table4_exceed35", {})
    lo, hi = band.get("low", 0), band.get("high", 1e9)
    df = pd.DataFrame({"pm2_5": series})
    df["season"] = [heating_season(t) for t in df.index]
    df = df[[m in (11, 12, 1, 2, 3) for m in df.index.month]]
    rows, level = [], "PASS"
    for s, g in df.groupby("season"):
        d55 = int((g["pm2_5"] > danger).sum())
        d35 = int((g["pm2_5"] > kg).sum())
        note = ""
        if g["pm2_5"].count() >= 60 and (d35 < lo or d35 > hi):
            note = f"OUT of Isaev [{lo},{hi}]"
            level = "WARN"
        rows.append(f"| {s} | {int(g['pm2_5'].count())} | {d55} | {d35} | {note} |")
    table = (f"| heating season | days w/ data | days >{danger} | days >{kg} | vs Isaev T4 |\n"
             "|---|---|---|---|---|\n" + "\n".join(rows))
    return Finding(cid, level, f"exceedance days per heating season ({name}); Isaev Table 4 "
                               f">{kg}: {lo}-{hi}/season ({band.get('cite','')})", table)


def _seasonal_cycle(cid, name, series, grid, cell_id, min_ratio):
    findings_level = "PASS"
    parts = []

    def ratio(s):
        if s is None or s.empty:
            return None
        by = s.groupby(s.index.month).mean()
        w = by.reindex([12, 1, 2]).mean()
        su = by.reindex([6, 7, 8]).mean()
        return None if not su else float(w / su)

    gr = ratio(series)
    if gr is None:
        parts.append("ground: n/a")
    else:
        parts.append(f"ground winter/summer = {gr:.2f}")
        if gr < min_ratio:
            findings_level = "FAIL"
    if grid is not None and not grid.empty and cell_id:
        gs = grid[grid["cell_id"] == cell_id]
        if not gs.empty and "pm2_5" in gs:
            s = pd.to_numeric(gs.set_index("date")["pm2_5"], errors="coerce").dropna()
            mr = ratio(s)
            if mr is not None:
                parts.append(f"grid winter/summer = {mr:.2f}")
                if mr < min_ratio and findings_level != "FAIL":
                    findings_level = "WARN"
    return Finding(cid, findings_level,
                   f"seasonal cycle ({name}); expect winter >= {min_ratio}x summer — " + "; ".join(parts))


def _gap(cid, name, series, grid, cell_id, std):
    if series is None or grid is None or grid.empty or not cell_id:
        return Finding(cid, "INFO", "need both a ground series and the grid Bishkek cell")
    kg = std["kg_mpc_daily_pm25"]
    gs = grid[grid["cell_id"] == cell_id]
    s_grid = pd.to_numeric(gs.set_index("date")["pm2_5"], errors="coerce").dropna()
    gdf = pd.DataFrame({"pm2_5": s_grid})
    gdf["season"] = [heating_season(t) for t in gdf.index]
    gdf = gdf[[m in (11, 12, 1, 2, 3) for m in gdf.index.month]]
    grnd = pd.DataFrame({"pm2_5": series})
    grnd["season"] = [heating_season(t) for t in grnd.index]
    grnd = grnd[[m in (11, 12, 1, 2, 3) for m in grnd.index.month]]
    rows = []
    for s in sorted(set(gdf["season"]) | set(grnd["season"])):
        gd = int((gdf[gdf["season"] == s]["pm2_5"] > kg).sum())
        rd = int((grnd[grnd["season"] == s]["pm2_5"] > kg).sum())
        rows.append(f"| {s} | {rd} | {gd} |")
    table = f"| heating season | ground days >{kg} | grid days >{kg} |\n|---|---|---|\n" + "\n".join(rows)
    return Finding(cid, "INFO", "model-vs-ground exceedance gap (documents the known limitation)", table)


def run(ctx) -> list[Finding]:
    name, series = best_ground_series(ctx)
    ref = ctx.reference_values
    mr = ctx.thresholds.get("seasonality", {}).get("min_winter_summer_ratio", 2.0)
    return [
        _annual_mean("reference.annual_mean", name, series, ref),
        _exceedance_days("reference.exceedance_days", name, series, ctx.standards, ref),
        _seasonal_cycle("reference.seasonal_cycle", name, series, ctx.grid,
                        ctx.bishkek_cell_id, mr),
        _gap("reference.model_vs_ground_gap", name, series, ctx.grid,
             ctx.bishkek_cell_id, ctx.standards),
    ]
```

- [ ] **Step 4: Run — verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_qa_reference.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add qa/checks/reference.py tests/test_qa_reference.py
git commit -m "feat: qa reference checks — annual mean, exceedance days vs Isaev, seasonal cycle, model gap"
```

---

## Task 8: `qa/report.py`

**Files:**
- Create: `qa/report.py`, `tests/test_qa_report.py`

**Interfaces:**
- Consumes: `qa.loaders.load_context`, the four `qa.checks.*.run`.
- Produces:
  - `run_all(ctx) -> list[Finding]` — concatenation of the four modules' `run(ctx)`, module order structure → plausibility → agreement → reference.
  - `render(findings, ctx, generated_at) -> str` — the QA_REPORT.md text.
  - `main(argv=None) -> int` — loads real context, writes `qa/QA_REPORT.md`, returns `1` if any `FAIL`, else `0`.

- [ ] **Step 1: Write the failing test — `tests/test_qa_report.py`**

```python
import pandas as pd
from qa import report
from qa.loaders import QAContext


def _ctx(grid):
    return QAContext(stations=pd.DataFrame(), grid=grid, grid_long=None, points=None,
        openaq={}, airnow=None, zenodo={},
        standards={"epa_aqi_unhealthy_pm25": 55.4, "kg_mpc_daily_pm25": 35.0},
        thresholds={"ranges": {"pm2_5": [0, 1000]}, "plausibility": {"fail_fraction": 0.001},
                    "completeness": {"warn_pct": 80, "fail_pct": 50}, "gap": {"warn_days": 7},
                    "cams_boundary_date": "2022-08-04", "agreement": {}, "seasonality": {}},
        reference_values={}, bishkek_cell_id="43.0000_75.0000", data_dictionary="")


def test_render_has_header_and_sections():
    grid = pd.DataFrame({"cell_id": ["43.0000_75.0000"], "lat": [43.0], "lon": [75.0],
                         "date": pd.to_datetime(["2022-09-01"]), "pm2_5": [40.0],
                         "dangerous_day": pd.array([False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([True], dtype="boolean")})
    ctx = _ctx(grid)
    fs = report.run_all(ctx)
    txt = report.render(fs, ctx, "2026-08-29")
    assert "PASS" in txt and "## structure" in txt.lower() or "structure" in txt.lower()
    assert txt.splitlines()[0].startswith("# QA report")


def test_main_returns_1_on_fail(tmp_path, monkeypatch):
    grid = pd.DataFrame({"cell_id": ["60.0000_75.0000"], "lat": [60.0], "lon": [75.0],
                         "date": pd.to_datetime(["2022-09-01"]), "pm2_5": [40.0],
                         "dangerous_day": pd.array([False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([True], dtype="boolean")})
    monkeypatch.setattr(report, "load_context", lambda *a, **k: _ctx(grid))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "qa").mkdir()
    rc = report.main([])
    assert rc == 1
    assert (tmp_path / "qa" / "QA_REPORT.md").exists()
```

- [ ] **Step 2: Run — verify fail**

Run: `.venv/Scripts/python -m pytest tests/test_qa_report.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `qa/report.py`**

```python
from __future__ import annotations
import argparse
import datetime as _dt
from pathlib import Path

from qa.loaders import load_context
from qa.checks import structure, plausibility, agreement, reference

_MODULES = [("structure", structure), ("plausibility", plausibility),
            ("agreement", agreement), ("reference", reference)]
_ICON = {"PASS": "OK", "INFO": "..", "WARN": "!!", "FAIL": "XX"}


def run_all(ctx) -> list:
    out = []
    for _, mod in _MODULES:
        out.extend(mod.run(ctx))
    return out


def render(findings, ctx, generated_at: str) -> str:
    counts = {k: sum(1 for f in findings if f.level == k) for k in ("PASS", "INFO", "WARN", "FAIL")}
    lines = [f"# QA report — {generated_at}", "",
             f"{counts['PASS']} PASS / {counts['INFO']} INFO / {counts['WARN']} WARN / {counts['FAIL']} FAIL",
             "",
             f"- stations rows: {len(ctx.stations)}  grid rows: {len(ctx.grid)}  "
             f"Bishkek grid cell: {ctx.bishkek_cell_id}",
             ""]
    by_mod = {}
    for f in findings:
        by_mod.setdefault(f.check_id.split(".")[0], []).append(f)
    for name, _ in _MODULES:
        lines.append(f"## {name}")
        for f in by_mod.get(name, []):
            lines.append(f"- **[{_ICON[f.level]} {f.level}] {f.check_id}** — {f.summary}")
            if f.table:
                lines += ["", f.table, ""]
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="qa/QA_REPORT.md")
    args = ap.parse_args(argv)
    ctx = load_context()
    findings = run_all(ctx)
    txt = render(findings, ctx, _dt.date.today().isoformat())
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(txt, encoding="utf-8")
    rc = 1 if any(f.level == "FAIL" for f in findings) else 0
    print(f"[qa] wrote {args.out}; FAIL={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run — verify pass; then full suite**

Run: `.venv/Scripts/python -m pytest tests/test_qa_report.py -q` → PASS.
Run: `.venv/Scripts/python -m pytest -q` → all green.

- [ ] **Step 5: Commit**

```bash
git add qa/report.py tests/test_qa_report.py
git commit -m "feat: qa report orchestrator — QA_REPORT.md with per-module findings and FAIL exit code"
```

---

## Task 9: `map/build_map.py` — heating-season snapshot + shared Bishkek cell

**Files:**
- Modify: `map/build_map.py`
- Modify: `tests/test_build_map.py`

**Interfaces:**
- Consumes: `qa.geo.nearest_cell_id`, `qa.geo.BISHKEK_LAT`, `qa.geo.BISHKEK_LON`.
- Produces: `build(...)` unchanged signature; when `snapshot_dates is None` and a grid is supplied, the snapshot date is the **heating-season** (months 11,12,1,2,3) day with the highest `snapshot_var` mean across cells; if no heating-season day has data, fall back to the global max day, else `grid["date"].max()`.

- [ ] **Step 1: Write the failing test — append to `tests/test_build_map.py`**

```python
def test_snapshot_prefers_heating_season_worst(tmp_path):
    import pandas as pd, json
    from map import build_map
    # a huge summer dust day and a moderate winter day
    grid = pd.DataFrame({
        "cell_id": ["43.0000_75.0000", "43.0000_75.0000"],
        "lat": [43.0, 43.0], "lon": [75.0, 75.0],
        "date": pd.to_datetime(["2023-05-15", "2023-01-15"]),
        "pm2_5": [900.0, 120.0],
        "dangerous_day": pd.array([True, True], dtype="boolean"),
        "exceeds_kg_limit": pd.array([True, True], dtype="boolean")})
    gp = tmp_path / "grid.parquet"; grid.to_parquet(gp, index=False)
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [74.59, 42.90]},
         "properties": {"station_id": "a", "name": "US Embassy", "network": "AirNow",
           "operator": "EPA", "pollutants": "pm2_5", "period_start": "2019", "period_end": "now",
           "location_precision": "approx", "access_url": "https://x", "coord_source": "geo",
           "quality_grade": "A", "notes": ""}}]}
    sp = tmp_path / "s.geojson"; sp.write_text(json.dumps(geo))
    stp = tmp_path / "st.csv"; stp.write_text("study_id,citation,year,doi_or_url,region,open_access,data_made_available,variables,method,relevance_notes\n")
    out = build_map.build(str(sp), str(stp), grid_path=str(gp), out_path=str(tmp_path / "m.html"))
    html = open(out, encoding="utf-8").read()
    assert "2023-01-15" in html and "2023-05-15" not in html
```

- [ ] **Step 2: Run — verify fail**

Run: `.venv/Scripts/python -m pytest tests/test_build_map.py -q`
Expected: FAIL — current code picks the global max (2023-05-15).

- [ ] **Step 3: Edit `map/build_map.py`**

Add import:

```python
from qa.geo import nearest_cell_id, BISHKEK_LAT, BISHKEK_LON  # noqa: F401
```

In `build()`, where `snapshot_dates` is derived (currently something like
`worst = grid.groupby("date")[snapshot_var].mean().idxmax()`), replace with:

```python
        if snapshot_dates is None:
            daily = grid.groupby("date")[snapshot_var].mean()
            heating = daily[[d.month in (11, 12, 1, 2, 3) for d in daily.index]]
            if heating.notna().any():
                snapshot_dates = [heating.idxmax()]
            elif daily.notna().any():
                snapshot_dates = [daily.idxmax()]
            else:
                snapshot_dates = [grid["date"].max()]
```

Keep the existing NaN-cell skip (`if pd.isna(val): continue`) and the `if not vmax:` guard.

- [ ] **Step 4: Run — verify pass; regenerate the committed HTML from local data if present**

Run: `.venv/Scripts/python -m pytest tests/test_build_map.py -q` → PASS.
Run: `.venv/Scripts/python -m map.build_map` (if `dataset/grid_daily.parquet` exists locally) and eyeball that it still opens.

- [ ] **Step 5: Commit**

```bash
git add map/build_map.py tests/test_build_map.py map/bishkek_air_quality_map.html
git commit -m "feat: map CAMS snapshot uses the worst heating-season day, not a summer dust day"
```

---

## Task 10: `fetch/parse_zenodo_bishkek.py` + AirNow date-range args

**Files:**
- Create: `fetch/parse_zenodo_bishkek.py`, `tests/test_parse_zenodo.py`
- Modify: `fetch/fetch_airnow.py`, `tests/test_fetch_airnow.py`

**Interfaces:**
- Produces:
  - `fetch/parse_zenodo_bishkek.py`:
    - `find_extractor() -> str | None` — first of `7z`, `7za`, `unrar`, `bsdtar` on PATH, else `None`.
    - `extract_archives(raw_dir="data/raw/zenodo_12720883") -> list[str]` — extracts every `.rar` there next to itself; no-op (returns `[]`) if no extractor.
    - `parse_us_embassy(raw_dir=...) -> pd.DataFrame` — locates the extracted US-Embassy monitoring file(s) (csv or xlsx), returns tidy `date,pm2_5,n_hours_pm2_5` daily (mean of sub-daily, `n_hours` = count or `pd.NA`), sorted; empty frame if not found.
    - `parse_clarity(raw_dir=...) -> pd.DataFrame` — reads `bishkek_monitoring_claritysensor_2021.xlsx`, returns tidy `date,pm2_5,n_hours_pm2_5` daily averaged across sensors; empty frame if not found or unreadable.
    - `main(argv=None)` — extract, parse both, write `data/processed/zenodo_bishkek_us_embassy_daily.csv` and `data/processed/zenodo_clarity_bishkek_daily.csv` (only when non-empty); print row counts.
  - `fetch/fetch_airnow.py`: `main` gains `--start` / `--end` (ISO dates); when given they override `cfg["date_start"]`/`cfg["date_end"]` for that run only.

- [ ] **Step 1: Write fixtures + failing test — `tests/test_parse_zenodo.py`**

```python
import pandas as pd
from pathlib import Path
from fetch import parse_zenodo_bishkek as pz


def test_parse_us_embassy_from_csv(tmp_path):
    raw = tmp_path / "zenodo_12720883"
    raw.mkdir()
    pd.DataFrame({
        "datetime": pd.date_range("2020-01-01", periods=48, freq="h"),
        "PM2.5": [50.0] * 24 + [70.0] * 24,
    }).to_csv(raw / "bishkek_monitoring_us_embassy.csv", index=False)
    out = pz.parse_us_embassy(str(raw))
    assert list(out.columns) == ["date", "pm2_5", "n_hours_pm2_5"]
    assert len(out) == 2
    assert out.iloc[0]["pm2_5"] == 50.0 and out.iloc[0]["n_hours_pm2_5"] == 24


def test_find_extractor_is_str_or_none():
    assert pz.find_extractor() is None or isinstance(pz.find_extractor(), str)


def test_parse_missing_returns_empty(tmp_path):
    assert pz.parse_us_embassy(str(tmp_path)).empty
    assert pz.parse_clarity(str(tmp_path)).empty
```

- [ ] **Step 2: Run — verify fail**

Run: `.venv/Scripts/python -m pytest tests/test_parse_zenodo.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write `fetch/parse_zenodo_bishkek.py`**

```python
from __future__ import annotations
import argparse
import glob
import shutil
import subprocess
from pathlib import Path

import pandas as pd

_EXTRACTORS = ["7z", "7za", "unrar", "bsdtar"]


def find_extractor() -> str | None:
    for e in _EXTRACTORS:
        if shutil.which(e):
            return e
    return None


def extract_archives(raw_dir="data/raw/zenodo_12720883") -> list[str]:
    exe = find_extractor()
    if not exe:
        print("[zenodo] no rar extractor (7z/unrar/bsdtar) on PATH; skipping .rar")
        return []
    done = []
    for rar in glob.glob(f"{raw_dir}/*.rar"):
        dest = Path(rar).with_suffix("")
        dest.mkdir(exist_ok=True)
        if exe in ("7z", "7za"):
            cmd = [exe, "x", "-y", f"-o{dest}", rar]
        elif exe == "unrar":
            cmd = [exe, "x", "-o+", rar, f"{dest}/"]
        else:
            cmd = [exe, "-x", "-f", rar, "-C", str(dest)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            done.append(str(dest))
        except subprocess.CalledProcessError as e:  # noqa: PERF203
            print(f"[zenodo] extract failed for {rar}: {e}")
    return done


def _to_daily_pm(df, time_col, pm_col):
    d = df[[time_col, pm_col]].copy()
    d[time_col] = pd.to_datetime(d[time_col], errors="coerce")
    d = d.dropna(subset=[time_col])
    d["date"] = d[time_col].dt.floor("D")
    g = d.groupby("date")[pm_col]
    out = g.mean().reset_index().rename(columns={pm_col: "pm2_5"})
    out["n_hours_pm2_5"] = g.count().values
    return out.sort_values("date").reset_index(drop=True)


def _find_files(raw_dir, *needles):
    hits = []
    for fp in glob.glob(f"{raw_dir}/**/*", recursive=True):
        low = fp.lower()
        if any(n in low for n in needles) and low.endswith((".csv", ".xlsx", ".xls")):
            hits.append(fp)
    return hits


def _read_any(fp):
    if fp.lower().endswith(".csv"):
        return pd.read_csv(fp)
    return pd.read_excel(fp)  # needs openpyxl (already a pandas extra in the env)


def _pick_cols(df):
    tcol = next((c for c in df.columns if str(c).lower() in
                 ("datetime", "date", "timestamp", "time", "date_time")), None)
    pcol = next((c for c in df.columns if "2.5" in str(c) or
                 str(c).lower() in ("pm25", "pm2_5", "value")), None)
    return tcol, pcol


def parse_us_embassy(raw_dir="data/raw/zenodo_12720883") -> pd.DataFrame:
    for fp in _find_files(raw_dir, "embassy", "us.embassy", "us_embassy"):
        try:
            df = _read_any(fp)
            t, p = _pick_cols(df)
            if t and p:
                return _to_daily_pm(df, t, p)
        except Exception as e:  # noqa: BLE001
            print(f"[zenodo] could not parse {fp}: {e}")
    return pd.DataFrame(columns=["date", "pm2_5", "n_hours_pm2_5"])


def parse_clarity(raw_dir="data/raw/zenodo_12720883") -> pd.DataFrame:
    for fp in _find_files(raw_dir, "clarity"):
        try:
            df = _read_any(fp)
            t, p = _pick_cols(df)
            if t and p:
                return _to_daily_pm(df, t, p)
        except Exception as e:  # noqa: BLE001
            print(f"[zenodo] could not parse {fp}: {e}")
    return pd.DataFrame(columns=["date", "pm2_5", "n_hours_pm2_5"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw/zenodo_12720883")
    args = ap.parse_args(argv)
    extract_archives(args.raw_dir)
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    emb = parse_us_embassy(args.raw_dir)
    if not emb.empty:
        emb.to_csv("data/processed/zenodo_bishkek_us_embassy_daily.csv", index=False)
    cl = parse_clarity(args.raw_dir)
    if not cl.empty:
        cl.to_csv("data/processed/zenodo_clarity_bishkek_daily.csv", index=False)
    print(f"[zenodo] us_embassy: {len(emb)} days; clarity: {len(cl)} days")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: AirNow date-range args — edit `fetch/fetch_airnow.py`**

In `main`, after `ap.add_argument("--config", ...)` add:

```python
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
```

After `cfg = load_config(args.config)` add:

```python
    if args.start:
        cfg["date_start"] = args.start
    if args.end:
        cfg["date_end"] = args.end
```

Append to `tests/test_fetch_airnow.py`:

```python
def test_start_end_override(monkeypatch, tmp_path):
    from fetch import fetch_airnow
    seen = {}
    def fake_fetch(cfg):
        import pandas as pd
        seen["range"] = (cfg["date_start"], cfg["date_end"])
        return pd.DataFrame({"date": ["2025-01-01"], "pm2_5": [10.0], "n_hours_pm2_5": [24]})
    monkeypatch.setattr(fetch_airnow, "fetch_bishkek", fake_fetch)
    monkeypatch.setattr(fetch_airnow, "load_config",
                        lambda *_: {"airnow_api_key": "x", "date_start": "2021-01-01",
                                    "date_end": "2025-12-31", "cities": {"Bishkek": [42.8746, 74.5698]}})
    monkeypatch.chdir(tmp_path); (tmp_path / "data" / "processed").mkdir(parents=True)
    fetch_airnow.main(["--start", "2025-01-01", "--end", "2025-12-31"])
    assert seen["range"] == ("2025-01-01", "2025-12-31")
```

- [ ] **Step 5: Run — verify pass; full suite**

Run: `.venv/Scripts/python -m pytest tests/test_parse_zenodo.py tests/test_fetch_airnow.py -q` → PASS.
Run: `.venv/Scripts/python -m pytest -q` → all green.

- [ ] **Step 6: Commit**

```bash
git add fetch/parse_zenodo_bishkek.py fetch/fetch_airnow.py tests/test_parse_zenodo.py tests/test_fetch_airnow.py
git commit -m "feat: Zenodo Bishkek monitoring parser + AirNow --start/--end for gap-fill runs"
```

---

## Task 11: Real pipeline run (Phase B — execute and record)

**Files:**
- Modify (regenerated, committed): `dataset/data_dictionary.md`, `dataset/grid_daily_sample.csv`, `map/bishkek_air_quality_map.html`, `kepler/stations_kepler.csv`
- Not committed (gitignored): everything under `data/`, `dataset/stations_daily.csv`, `dataset/grid_daily.parquet`, `kepler/grid_daily_long.parquet`

**This task runs commands and records outputs. No new code. If a command needs a code fix, stop and report — do not improvise.**

- [ ] **Step 1: Preflight**

```bash
.venv/Scripts/python -m pytest -q            # all green
.venv/Scripts/python -c "import openpyxl"     # for Zenodo xlsx; if ImportError: .venv/Scripts/python -m pip install openpyxl
sed -E 's/(key: ")[^"]+/\1***/' fetch/config.yaml   # confirm keys present, do NOT print raw
```

- [ ] **Step 2: OpenAQ (4 cities, real key)**

```bash
.venv/Scripts/python -m fetch.fetch_openaq --config fetch/config.yaml
```

Record: for each city, days fetched and pollutants present (from the console lines). Inspect Bishkek 2025 coverage:

```bash
.venv/Scripts/python -c "import pandas as pd; d=pd.read_csv('data/processed/openaq_bishkek_daily.csv'); d['date']=pd.to_datetime(d['date']); x=d[d['date'].dt.year==2025]; print('2025 rows:', len(x), 'pm2_5 non-null:', x['pm2_5'].notna().sum() if 'pm2_5' in x else 0)"
```

- [ ] **Step 3: Decide AirNow-2025 gap-fill**

If Step 2 shows Bishkek 2025 `pm2_5` non-null days < 250, run the bounded gap-fill:

```bash
.venv/Scripts/python -m fetch.fetch_airnow --config fetch/config.yaml --start 2025-01-01 --end 2025-12-31
```

Otherwise skip and note "OpenAQ 2025 coverage adequate; AirNow direct not run". Either way, do **not** run AirNow for the full 2021–2025 range.

- [ ] **Step 4: Zenodo parse**

```bash
.venv/Scripts/python -m fetch.fetch_zenodo_bishkek        # ensure archive present (idempotent, cached)
.venv/Scripts/python -m fetch.parse_zenodo_bishkek
```

Record: whether an extractor was found, and the day counts for `zenodo_bishkek_us_embassy_daily.csv` / `zenodo_clarity_bishkek_daily.csv` (or "not produced").

- [ ] **Step 5: Open-Meteo — points, then grid at 1.0°**

```bash
.venv/Scripts/python -m fetch.fetch_open_meteo --mode points --config fetch/config.yaml
.venv/Scripts/python -m fetch.fetch_open_meteo --mode grid --grid-spacing 1.0 --config fetch/config.yaml
```

Record: grid cells fetched vs expected (~210), any cells that fell back to weather-only (rate-limit skips), and the first non-null `pm2_5` date at the Bishkek points row (should be ~2022-08-04). If the grid run reports many skips, wait and re-run the same command once — the cache keeps the successes; do not re-run more than twice.

- [ ] **Step 6: Build datasets + map + kepler**

```bash
.venv/Scripts/python -m fetch.build_dataset
.venv/Scripts/python -m map.build_map
.venv/Scripts/python -m kepler.build_kepler
```

- [ ] **Step 7: Verify acceptance gates 2, 3, 6**

```bash
grep -n "55.4\|> 35" fetch/build_dataset.py                       # only _DICT text / comments
.venv/Scripts/python -c "import pandas as pd; s=pd.read_csv('dataset/stations_daily.csv'); s['date']=pd.to_datetime(s['date']); print('stations rows:', len(s), 'Bishkek-ish keys:', sorted(k for k in s['station_key'].unique() if 'bishkek' in str(k).lower()))"
.venv/Scripts/python -c "import pandas as pd; g=pd.read_parquet('dataset/grid_daily.parquet'); print('grid rows:', len(g), 'cells:', g['cell_id'].nunique())"
grep -c "TODO-REVIEW" dataset/data_dictionary.md                  # 0
.venv/Scripts/python -c "import pandas as pd; print('kepler stations rows:', len(pd.read_csv('kepler/stations_kepler.csv')))"
git status --porcelain                                            # no data/ or *.parquet staged later
```

Expected: `stations_daily.csv` non-empty with a Bishkek key; `grid_daily.parquet` ~210 cells; dictionary 0 `TODO-REVIEW`.

- [ ] **Step 8: Write the run record + commit regenerated artifacts**

Write `docs/superpowers/plans/2026-08-29-real-run-record.md` with every recorded number from Steps 2–7 (per-city coverage, AirNow decision, Zenodo counts, grid cells/skips, CAMS first date, dataset row counts).

```bash
git add dataset/data_dictionary.md dataset/grid_daily_sample.csv map/bishkek_air_quality_map.html kepler/stations_kepler.csv docs/superpowers/plans/2026-08-29-real-run-record.md
git commit -m "chore: real pipeline run — regenerated datasets, map, kepler exports (1.0deg grid)"
```

---

## Task 12: QA report on real data

**Files:**
- Create (committed): `qa/QA_REPORT.md`

- [ ] **Step 1: Run QA against the real artifacts**

```bash
.venv/Scripts/python -m qa.report
echo "exit: $?"
```

- [ ] **Step 2: Read `qa/QA_REPORT.md` and triage**

For every `FAIL`:
- If it reveals a real defect in the pipeline code (e.g. a flag inconsistency, a bbox breach, a duplicate key), STOP and report to the controller with the finding — it becomes a fix, not an adjudication.
- If it is an expected data limitation (CAMS gases absent before 2022-08-04 driving a low-completeness FAIL; the model-vs-ground gap), append an **Adjudication** subsection to `qa/QA_REPORT.md` naming the finding, why it is acceptable, and the citation (spec §5). The CAMS boundary check is designed to emit INFO, not FAIL, for the expected case — a FAIL there is a real bug.

- [ ] **Step 3: Re-run until no unadjudicated FAIL**

```bash
.venv/Scripts/python -m qa.report ; echo "exit: $?"
```

Exit 0, or exit 1 with every FAIL carrying an Adjudication paragraph.

- [ ] **Step 4: Commit**

```bash
git add qa/QA_REPORT.md
git commit -m "chore: QA report on real datasets (with adjudications for known CAMS gaps)"
```

---

## Task 13: Finished-map verification

**Files:**
- Modify if needed: `map/build_map.py` (+ test)

- [ ] **Step 1: Inspect the built map**

```bash
.venv/Scripts/python - <<'PY'
from pathlib import Path
h = Path("map/bishkek_air_quality_map.html").read_text(encoding="utf-8")
need = ["Reference monitors", "Kyrgyzhydromet sensors", "Citizen/low-cost sensors",
        "Comparison cities", "Study &amp; campaign sites", "Airshed extent"]
print("missing layers:", [n for n in need if n not in h and n.replace("&amp;", "&") not in h])
print("has LayerControl:", ("LayerControl" in h) or ("layer_control" in h) or ("leaflet-control-layers" in h))
print("has CAMS grid layer:", "CAMS grid:" in h)
print("nan popups:", h.count("pm2_5=nan"))
print("bytes:", len(h))
PY
```

Expected: no missing layers; LayerControl present; `CAMS grid:` present; `nan popups: 0`.

- [ ] **Step 2: If a check fails, fix `build_map.py` with a test**

Add a targeted test in `tests/test_build_map.py` reproducing the gap, fix minimally, re-run `.venv/Scripts/python -m map.build_map`, re-inspect. Commit `map/build_map.py`, the test, and the regenerated `map/bishkek_air_quality_map.html`.

- [ ] **Step 3: Full suite + final commit**

```bash
.venv/Scripts/python -m pytest -q       # all green
git add -A && git status --porcelain    # only intended files
git commit -m "chore: verify finished map — all layers, no nan cells, heating-season snapshot" || echo "nothing to commit"
```

---

## Self-Review

**1. Spec coverage**

| Spec section | Task |
|---|---|
| §2.1 standards.csv (US EPA + Kyrgyz only, cited) | T1 |
| §2.1 validate standards.csv | T1 (validate_catalog extension) |
| §2.2 build_dataset reads thresholds from standards; no literal | T2 |
| §2.2 station-side flags; missing-id raises; _DICT caveats | T2 |
| §3 qa/ package layout | T3 (skeleton) + T4–T8 |
| §3 loaders / QAContext / thresholds.yaml / reference_values.yaml | T3 |
| §3 bishkek grid cell centralised | T3 (`qa/geo.py`), consumed T9 + loaders |
| §3.1 plausibility (ranges, completeness, dupes, gaps, CAMS boundary) | T5 |
| §3.2 agreement (pairwise r/bias/RMSE/MAE; exceedance counts) | T6 |
| §3.3 reference (annual mean, exceedance vs Isaev, seasonal cycle, gap) | T7 |
| §3.4 structure (schema, keys, flag consistency, n_hours/sparse, dict, bbox, kepler long) | T4 |
| §3.5 report.py + QA_REPORT.md + exit code | T8 |
| §3.6 fixture-based pytest per check | T4–T8 tests |
| §4.1 Open-Meteo grid 1.0°, one run, budget | T11 Step 5 |
| §4.2 OpenAQ 4 cities | T11 Step 2 |
| §4.3 AirNow conditional 2025 gap-fill only | T10 (args) + T11 Step 3 |
| §4.4 Zenodo extract + parse US Embassy + Clarity | T10 + T11 Step 4 |
| §5 gate 1 pytest green | every task + T11 Step 1 |
| §5 gate 2 no literal thresholds | T2 Step 4, T11 Step 7 |
| §5 gate 3 real datasets non-empty | T11 Step 7 |
| §5 gate 4 finished map | T9 + T13 |
| §5 gate 5 QA_REPORT.md, FAILs adjudicated | T12 |
| §5 gate 6 kepler refreshed | T11 Step 6–7 |
| §5 gate 7 no secret tracked, clean tree | T11 Step 7, T13 Step 3 |
| §6 no data modification | enforced by check design (T4–T7 read-only); called out in T12 Step 2 |
| §7 phases A / B / C | T1–T10 / T11–T13 / SDD final review |
| §8 open items | T10 (extractor detection), T11 Step 2–3 (OpenAQ 2025), T9 (heating-season snapshot), T3 (cell centralised) |

No spec requirement is left without a task.

**2. Placeholder scan** — every code step carries real code. T11/T12/T13 are execute-and-record tasks (like the predecessor plan's Task 11) with concrete commands and explicit stop conditions ("STOP and report — do not improvise"), not vague instructions. No `TBD`, no "add error handling", no un-coded test steps.

**3. Type consistency** — `Finding(check_id, level, summary, table=None)` defined in T3 (`qa/checks/__init__.py`), used identically in T4–T8. `QAContext` fields defined in T3, consumed by the same names in T4–T8 and T12's monkeypatched `_ctx`. `run(ctx) -> list[Finding]` is the uniform check-module entry point (T4–T7), aggregated by `run_all` in T8. `load_standards` / `require` defined in T1, imported in T2 and (via loaders) T3+. `AQ_VARS` / `WX_VARS` re-declared verbatim in T3 `qa/loaders.py` and asserted equal to `fetch.build_dataset`'s in T3 Step 6. `nearest_cell_id(grid_df, lat, lon)` defined in T3 `qa/geo.py`, consumed in T9 and `qa/loaders.py`. `bishkek_series(ctx)` defined in T6, reused in T7. Flag column names `dangerous_day` / `exceeds_kg_limit` consistent across T2, T4, T6, T7.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-08-29-qa-standards-and-verified-deliverables.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration, ledger-resumable across a usage-limit interruption.

**2. Inline Execution** — tasks in this session with checkpoints for review.

**Which approach?**
