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
    """Assemble a QAContext from whatever inputs are on disk.

    Tolerant of missing OPTIONAL inputs: the dataset / processed / kepler files
    and the two YAML config files all fall back to an empty frame or ``{}`` when
    absent, so QA can run on a partial checkout. The one hard dependency is
    ``catalog/standards.csv`` — ``load_standards()`` raises ``FileNotFoundError``
    if it is missing, because the checks cannot resolve their thresholds without
    it (it is a committed file, so this should not happen in a normal checkout).
    """
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
