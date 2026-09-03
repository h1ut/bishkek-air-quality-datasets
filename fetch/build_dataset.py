from __future__ import annotations
import argparse
import glob
from pathlib import Path
import pandas as pd
from catalog.standards import load_standards, require

AQ_VARS = ["pm2_5", "pm10", "carbon_monoxide", "nitrogen_dioxide",
           "sulphur_dioxide", "ozone", "aerosol_optical_depth", "dust"]
WX_VARS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
           "wind_direction_10m", "surface_pressure", "boundary_layer_height"]

# Station-schema columns that must always be documented in the data dictionary,
# even when no station CSVs exist locally (empty `stations` frame contributes nothing).
_STATION_POLLUTANTS = ["pm2_5", "pm10", "sulphur_dioxide", "nitrogen_dioxide",
                       "carbon_monoxide", "ozone"]
KNOWN_STATION_COLS = (
    ["station_key", "city", "date", "pm2_5", "pm10", "sulphur_dioxide",
     "nitrogen_dioxide", "carbon_monoxide", "ozone", "relative_humidity", "temperature"]
    + [f"{v}_source" for v in _STATION_POLLUTANTS]
    + [f"n_hours_{v}" for v in _STATION_POLLUTANTS]
)

_DICT = {
    "pm2_5": ("OpenAQ/AirNow or CAMS", "µg/m³", "hourly→daily mean; _max kept",
              "ground = measured; grid = model, needs validation"),
    "pm10": ("OpenAQ or CAMS", "µg/m³", "daily mean", "as pm2_5"),
    "carbon_monoxide": ("OpenAQ or CAMS",
                        "µg/m³ (CAMS); OpenAQ CO may be mg/m³ or ppm depending on provider — check per station",
                        "daily mean", "check unit per source; CAMS is µg/m³"),
    "nitrogen_dioxide": ("OpenAQ or CAMS", "µg/m³", "daily mean", "as pm2_5"),
    "sulphur_dioxide": ("OpenAQ or CAMS", "µg/m³", "daily mean", "as pm2_5"),
    "ozone": ("OpenAQ or CAMS", "µg/m³", "daily mean", "as pm2_5"),
    "aerosol_optical_depth": ("CAMS", "unitless", "daily mean", "model; column property"),
    "dust": ("CAMS", "µg/m³", "daily mean", "model surface dust estimate"),
    "temperature_2m": ("ERA5", "°C", "daily mean; _max kept", "reanalysis"),
    "relative_humidity_2m": ("ERA5", "%", "daily mean", "reanalysis"),
    "temperature": ("OpenAQ", "°C", "hourly→daily mean; _max kept",
                    "ground station co-located met; sensor-dependent"),
    "relative_humidity": ("OpenAQ", "%", "hourly→daily mean",
                          "ground station co-located met; sensor-dependent"),
    "wind_speed_10m": ("ERA5", "m/s", "daily mean", "reanalysis"),
    "wind_direction_10m": ("ERA5", "° from N", "daily vector mean", "reanalysis"),
    "surface_pressure": ("ERA5", "hPa", "daily mean", "reanalysis"),
    "boundary_layer_height": ("ERA5", "m", "daily mean", "reanalysis; key for winter inversions"),
    "dangerous_day": ("derived", "boolean",
                      "pm2_5 > standards.epa_aqi_unhealthy_pm25",
                      "US EPA AQI Unhealthy lower bound (24-h PM2.5 55.4 µg/m³); "
                      "<NA> where pm2_5 is missing (not the same as False)"),
    "exceeds_kg_limit": ("derived", "boolean",
                         "pm2_5 > standards.kg_mpc_daily_pm25",
                         "Kyrgyz ПДК среднесуточная, ПП КР №201 (2016) поз. 613, 35 µg/m³; "
                         "<NA> where pm2_5 is missing (not the same as False)"),
    "cell_id": ("derived", "id", "grid cell key `<lat:.4f>_<lon:.4f>`", "—"),
    "lat": ("grid/station", "degrees", "point coordinate", "—"),
    "lon": ("grid/station", "degrees", "point coordinate", "—"),
    "date": ("derived", "date", "UTC calendar day", "—"),
    "sparse": ("derived", "bool", "any source had <18 h that day", "flag, not a value"),
    "station_key": ("derived", "id", "station/city identifier", "—"),
    "city": ("OpenAQ", "name", "source city label", "—"),
}


def build_stations(proc_dir="data/processed", standards=None) -> pd.DataFrame:
    frames = []
    for fp in sorted(glob.glob(f"{proc_dir}/openaq_*_daily.csv")):
        df = pd.read_csv(fp)
        city = Path(fp).stem.removeprefix("openaq_").removesuffix("_daily")
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
    if "pm2_5" in out.columns:
        std = standards if standards is not None else load_standards()
        danger = require(std, "epa_aqi_unhealthy_pm25")
        kg = require(std, "kg_mpc_daily_pm25")
        pm = pd.to_numeric(out["pm2_5"], errors="coerce")
        out["dangerous_day"] = (pm > danger).astype("boolean").mask(pm.isna())
        out["exceeds_kg_limit"] = (pm > kg).astype("boolean").mask(pm.isna())
    return out.sort_values(["station_key", "date"]).reset_index(drop=True)


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
        if c in _DICT:
            s, u, agg, cav = _DICT[c]
        elif c.endswith("_source"):
            s, u, agg, cav = ("derived", "text",
                              f"which source supplied `{c[:-7]}` for this row", "provenance")
        elif c.endswith("_max") and c[:-4] in _DICT:
            s, u, _, cav = _DICT[c[:-4]]
            agg = "daily max"
        else:
            s, u, agg, cav = ("TODO-REVIEW", "TODO-REVIEW", "TODO-REVIEW", "TODO-REVIEW")
        rows.append(f"| {c} | {s} | {u} | {agg} | {cav} |")
    Path(path).write_text("\n".join(rows) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--proc-dir", default="data/processed")
    args = ap.parse_args(argv)
    Path("dataset").mkdir(exist_ok=True)
    Path("kepler").mkdir(exist_ok=True)

    std = load_standards()
    stations = build_stations(args.proc_dir, standards=std)
    stations.to_csv("dataset/stations_daily.csv", index=False)

    grid = build_grid_dataset(args.proc_dir, standards=std)
    grid.to_parquet("dataset/grid_daily.parquet", index=False)
    to_long(grid).to_parquet("kepler/grid_daily_long.parquet", index=False)

    # small committed sample: Bishkek cell + 8 nearest neighbours, first week with AQ data
    if not grid.empty:
        ranked = grid.assign(d=((grid["lat"] - 42.8746) ** 2 + (grid["lon"] - 74.5698) ** 2)) \
                     .sort_values("d")
        bcell = ranked["cell_id"].iloc[0]
        near_cells = list(dict.fromkeys(ranked["cell_id"]))[:9]
        bcell_pm = grid[grid["cell_id"] == bcell]
        if "pm2_5" in grid:
            bcell_pm = bcell_pm[bcell_pm["pm2_5"].notna()]
        else:
            bcell_pm = bcell_pm.iloc[0:0]
        if len(bcell_pm):
            start = bcell_pm["date"].min()
            window = sorted(grid.loc[grid["date"] >= start, "date"].unique())[:7]
        else:
            window = sorted(grid["date"].unique())[:7]
            print("note: grid sample predates CAMS AQ coverage (no non-null pm2_5 in Bishkek cell)")
        near = grid[grid["cell_id"].isin(near_cells) & grid["date"].isin(window)]
        near.to_csv("dataset/grid_daily_sample.csv", index=False)

    dict_cols = sorted(set(stations.columns) | set(grid.columns) | set(KNOWN_STATION_COLS))
    write_data_dictionary(dict_cols)

    print(f"stations_daily: {len(stations)} rows; grid_daily: {len(grid)} rows")
    if not grid.empty and "dangerous_day" in grid:
        bg = grid[grid["cell_id"] == bcell]
        bg = bg.assign(season=bg["date"].dt.year.where(bg["date"].dt.month >= 7, bg["date"].dt.year - 1))
        print(bg.groupby("season")["dangerous_day"].sum())


if __name__ == "__main__":
    main()
