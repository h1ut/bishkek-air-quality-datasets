"""Build the kepler.gl deliverables for the Central Asia air-quality dataset.

Reads the shipped datasets (`dataset/grid_daily.parquet`,
`dataset/stations_daily.csv`) and the sensor staging table
(`data/processed/_stations_staging.csv`) and writes, into `kepler/`:

* ``ca_air_quality_grid.csv``     — daily gridded surface, one row per cell-date
* ``ca_air_quality_stations.csv`` — daily OpenAQ/AirNow city series with coords
* ``ca_air_quality_sensors.csv``  — discovered sensor point locations
* ``kepler_config.json``          — the 3-layer kepler.gl config (committed)
* ``ca_air_quality_styling.json`` — config + embedded station/sensor datasets

The three CSVs are gitignored (bulky, regenerated per run); ``kepler_config.json``
is committed because the load doc references it and it is tiny.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path

import pandas as pd

from qa.loaders import AQ_VARS, WX_VARS

# city / station_key -> (lat, lon); stations_daily.csv carries no coordinates.
CITY_COORDS = {
    "bishkek": (42.8746, 74.5698),
    "almaty": (43.238, 76.945),
    "tashkent": (41.2995, 69.2401),
    "astana": (51.1605, 71.4704),
    "bishkek_us_embassy": (42.9006, 74.5936),
}

GRID_COLS = ["cell_id", "lat", "lon", "date", *AQ_VARS, *WX_VARS,
             "dangerous_day", "exceeds_kg_limit"]
STATION_COLS = ["station_key", "city", "lat", "lon", "date", "pm2_5", "pm10",
                "ozone", "temperature", "relative_humidity",
                "dangerous_day", "exceeds_kg_limit"]
SENSOR_COLS = ["sensor_name", "network", "operator", "lat", "lon", "pollutants",
               "period_start", "period_end", "access_url"]


def _kepler_config() -> dict:
    """The committed 3-layer kepler.gl config: grid + stations + sensors."""
    colors = ["#ffffb2", "#fed976", "#feb24c", "#fd8d3c", "#f03b20", "#bd0026"]
    ylord = {"name": "ColorBrewer YlOrRd-6", "type": "sequential",
             "category": "ColorBrewer", "colors": colors}

    def pm_layer(lid, data_id, label, rgb, radius, visible):
        return {
            "id": lid, "type": "point",
            "config": {
                "dataId": data_id, "label": label, "color": rgb,
                "columns": {"lat": "lat", "lng": "lon", "altitude": None},
                "isVisible": visible,
                "visConfig": {"radius": radius, "opacity": 0.8, "filled": True,
                              "colorRange": ylord},
                "colorField": {"name": "pm2_5", "type": "real"},
                "colorScale": "quantile",
            },
            "visualChannels": {
                "colorField": {"name": "pm2_5", "type": "real"},
                "colorScale": "quantile", "sizeField": None, "sizeScale": "linear"},
        }

    sensors_layer = {
        "id": "sen", "type": "point",
        "config": {
            "dataId": "ca_air_quality_sensors",
            "label": "All discovered sensors", "color": [255, 255, 255],
            "columns": {"lat": "lat", "lng": "lon", "altitude": None},
            "isVisible": False,
            "visConfig": {"radius": 8, "opacity": 0.7, "filled": True,
                          "colorRange": {"name": "Uber Viz Qualitative 4",
                                         "type": "qualitative", "category": "Uber",
                                         "colors": ["#12939A", "#DDB27C", "#88572C",
                                                    "#FF991F", "#F15C17"]}},
            "colorField": {"name": "network", "type": "string"},
            "colorScale": "ordinal",
        },
        "visualChannels": {
            "colorField": {"name": "network", "type": "string"},
            "colorScale": "ordinal", "sizeField": None, "sizeScale": "linear"},
    }

    return {
        "version": "v1",
        "config": {
            "visState": {
                "filters": [
                    {"dataId": ["ca_air_quality_grid"], "id": "tf_grid",
                     "name": ["date"], "type": "timeRange", "enlarged": True,
                     "plotType": "histogram", "animationWindow": "free"},
                    {"dataId": ["ca_air_quality_stations"], "id": "tf_stn",
                     "name": ["date"], "type": "timeRange", "enlarged": False,
                     "plotType": "histogram", "animationWindow": "free"},
                ],
                "layers": [
                    pm_layer("grid", "ca_air_quality_grid",
                             "CAMS grid — all variables", [241, 92, 23], 20, True),
                    pm_layer("stn", "ca_air_quality_stations",
                             "Ground stations (OpenAQ/AirNow)", [18, 147, 154], 30, True),
                    sensors_layer,
                ],
                "layerBlending": "normal",
                "interactionConfig": {
                    "tooltip": {"enabled": True, "fieldsToShow": {
                        "ca_air_quality_grid": [{"name": "cell_id"}, {"name": "pm2_5"},
                                                {"name": "pm10"}, {"name": "dust"},
                                                {"name": "temperature_2m"},
                                                {"name": "boundary_layer_height"}],
                        "ca_air_quality_stations": [{"name": "station_key"}, {"name": "pm2_5"},
                                                    {"name": "pm10"}, {"name": "ozone"}],
                        "ca_air_quality_sensors": [{"name": "sensor_name"}, {"name": "network"},
                                                   {"name": "pollutants"},
                                                   {"name": "period_start"}]}}},
            },
            "mapState": {"latitude": 43.5, "longitude": 72.0, "zoom": 4.3,
                         "bearing": 0, "pitch": 0},
            "mapStyle": {"styleType": "dark"},
        },
    }


def _kepler_type(s: pd.Series) -> str:
    if s.name == "date":
        return "date"
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_integer_dtype(s):
        return "integer"
    if pd.api.types.is_float_dtype(s):
        return "real"
    return "string"


def _embed_dataset(data_id: str, label: str, df: pd.DataFrame) -> dict:
    fields = [{"name": c, "type": _kepler_type(df[c])} for c in df.columns]
    all_data = df.where(pd.notnull(df), None).values.tolist()
    return {"version": "v1", "data": {"id": data_id, "label": label,
                                      "allData": all_data, "fields": fields}}


def build_grid(dataset_dir: Path, out_dir: Path) -> int:
    g = pd.read_parquet(dataset_dir / "grid_daily.parquet")
    g["date"] = pd.to_datetime(g["date"]).dt.strftime("%Y-%m-%d")
    cols = [c for c in GRID_COLS if c in g.columns]
    out = g[cols].copy()
    out.to_csv(out_dir / "ca_air_quality_grid.csv", index=False)
    return len(out)


def build_stations(dataset_dir: Path, out_dir: Path) -> pd.DataFrame:
    s = pd.read_csv(dataset_dir / "stations_daily.csv")
    s["date"] = pd.to_datetime(s["date"]).dt.strftime("%Y-%m-%d")
    s["lat"] = s["station_key"].map(lambda k: CITY_COORDS.get(k, (None, None))[0])
    s["lon"] = s["station_key"].map(lambda k: CITY_COORDS.get(k, (None, None))[1])
    for c in STATION_COLS:
        if c not in s.columns:
            s[c] = pd.NA
    out = s[STATION_COLS].copy()
    keep = out["pm2_5"].notna() | out["pm10"].notna()
    out = out[keep]
    out.to_csv(out_dir / "ca_air_quality_stations.csv", index=False)
    return out


def build_sensors(proc_dir: Path, out_dir: Path) -> pd.DataFrame:
    st = pd.read_csv(proc_dir / "_stations_staging.csv")
    st = st.rename(columns={"name": "sensor_name"})
    for c in SENSOR_COLS:
        if c not in st.columns:
            st[c] = pd.NA
    st = st.dropna(subset=["lat", "lon"])
    st = st[(st["lat"].between(35, 56)) & (st["lon"].between(60, 85))]
    out = st[SENSOR_COLS].copy()
    out.to_csv(out_dir / "ca_air_quality_sensors.csv", index=False)
    return out


def build(dataset_dir="dataset", proc_dir="data/processed", out_dir="kepler") -> dict:
    dataset_dir, proc_dir, out_dir = Path(dataset_dir), Path(proc_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    n_grid = build_grid(dataset_dir, out_dir)
    stations = build_stations(dataset_dir, out_dir)
    sensors = build_sensors(proc_dir, out_dir)

    cfg = _kepler_config()
    (out_dir / "kepler_config.json").write_text(
        json.dumps(cfg, indent=1, ensure_ascii=False), encoding="utf-8")

    styling = {
        "datasets": [
            _embed_dataset("ca_air_quality_stations", "Ground stations", stations),
            _embed_dataset("ca_air_quality_sensors", "Discovered sensors", sensors),
        ],
        "config": cfg["config"],
        "info": {"app": "kepler.gl", "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
                 "title": "Central Asia air quality",
                 "description": "Styling + embedded station/sensor layers. Drop this "
                                "AFTER the three CSVs to apply colours and time sliders."},
    }
    (out_dir / "ca_air_quality_styling.json").write_text(
        json.dumps(styling, ensure_ascii=False), encoding="utf-8")

    return {"grid": n_grid, "stations": len(stations), "sensors": len(sensors)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", default="dataset")
    ap.add_argument("--proc-dir", default="data/processed")
    ap.add_argument("--out-dir", default="kepler")
    args = ap.parse_args(argv)
    counts = build(args.dataset_dir, args.proc_dir, args.out_dir)
    print(f"[kepler] grid rows: {counts['grid']}  stations rows: {counts['stations']}  "
          f"sensors rows: {counts['sensors']}")
    print(f"[kepler] wrote ca_air_quality_grid.csv, ca_air_quality_stations.csv, "
          f"ca_air_quality_sensors.csv, kepler_config.json, ca_air_quality_styling.json "
          f"to {args.out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
