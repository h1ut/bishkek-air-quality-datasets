"""Meteorology and model-pollutant predictors aggregated to LOCAL calendar days.

Every aggregate for day D uses only hours whose start lies inside local day D
(Asia/Bishkek, UTC+6), i.e. 18:00 UTC of D-1 .. 17:00 UTC of D.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from prep.sources import isd, openmeteo_s3

TZ = "Asia/Bishkek"


def _local_day(ts_utc: pd.Series) -> pd.Series:
    return ts_utc.dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()


def rh_from_t_td(t: pd.Series, td: pd.Series) -> pd.Series:
    """Relative humidity (%) from temperature and dew point (Magnus, over water)."""
    a, b = 17.625, 243.04
    return 100 * np.exp(a * td / (b + td) - a * t / (b + t))


def isd_daily(station: str, years, prefix: str, min_obs: int) -> pd.DataFrame:
    h = isd.parse_station(station, years)
    if h.empty:
        return pd.DataFrame()
    h["date"] = _local_day(h["time_utc"])
    h["local_hour"] = h["time_utc"].dt.tz_convert(TZ).dt.hour
    h["rh"] = rh_from_t_td(h["temp_c"], h["dewpoint_c"])
    rad = np.deg2rad(h["wind_dir_deg"])
    # meteorological convention: direction the wind blows FROM
    h["u"] = -h["wind_speed_ms"] * np.sin(rad)
    h["v"] = -h["wind_speed_ms"] * np.cos(rad)
    calm = h["wind_speed_ms"].eq(0)
    h.loc[calm, ["u", "v"]] = 0.0
    h["haze_smoke"] = h["wx_code"].isin([4, 5]).astype(float).where(h["wx_code"].notna())
    h["fog"] = h["wx_code"].between(40, 49).astype(float).where(h["wx_code"].notna())
    night = h["local_hour"].isin([0, 1, 2, 3, 4, 5, 6])
    g = h.groupby("date")
    out = pd.DataFrame({
        "n_obs": g["temp_c"].count(),
        "temp_mean": g["temp_c"].mean(), "temp_min": g["temp_c"].min(), "temp_max": g["temp_c"].max(),
        "dewpoint_mean": g["dewpoint_c"].mean(),
        "rh_mean": g["rh"].mean(),
        "slp_mean": g["slp_hpa"].mean(),
        "wind_speed_mean": g["wind_speed_ms"].mean(),
        "wind_calm_frac": g["wind_speed_ms"].apply(lambda s: (s == 0).mean() if s.notna().any() else np.nan),
        "wind_u_mean": g["u"].mean(), "wind_v_mean": g["v"].mean(),
        "visibility_min": g["visibility_m"].min(), "visibility_mean": g["visibility_m"].mean(),
        "haze_smoke_frac": g["haze_smoke"].mean(), "fog_frac": g["fog"].mean(),
    })
    out["temp_range"] = out["temp_max"] - out["temp_min"]
    out["temp_night_mean"] = h[night].groupby("date")["temp_c"].mean()
    out["wind_speed_night_mean"] = h[night].groupby("date")["wind_speed_ms"].mean()
    ok = out["n_obs"] >= min_obs
    vals = [c for c in out.columns if c != "n_obs"]
    out.loc[~ok, vals] = np.nan              # too few reports that day -> missing, not partial
    out = out.add_prefix(prefix)
    out.index.name = "date"
    return out


def _om_hourly(domain: str, var: str) -> pd.Series:
    p = openmeteo_s3.raw_path(domain, var)
    if not p.exists():
        return pd.Series(dtype=float)
    d = pd.read_csv(p, parse_dates=["time_utc"])
    d["time_utc"] = pd.to_datetime(d["time_utc"], utc=True)
    return d.set_index("time_utc")["value"]


def era5_daily(min_hours: int = 20) -> pd.DataFrame:
    dom = "copernicus_era5"
    s = {v: _om_hourly(dom, v) for v in openmeteo_s3.ERA5_VARS}
    h = pd.DataFrame(s)
    if h.empty:
        return h
    h["date"] = _local_day(h.index.to_series())
    h["local_hour"] = h.index.tz_convert(TZ).hour
    h["wind_speed_10m"] = np.hypot(h["wind_u_component_10m"], h["wind_v_component_10m"])
    h["rh_2m"] = rh_from_t_td(h["temperature_2m"], h["dew_point_2m"])
    g = h.groupby("date")
    out = pd.DataFrame({
        "n_hours": g["temperature_2m"].count(),
        "n_hours_blh": g["boundary_layer_height"].count(),
        "t2m_mean": g["temperature_2m"].mean(), "t2m_min": g["temperature_2m"].min(),
        "t2m_max": g["temperature_2m"].max(),
        "rh2m_mean": g["rh_2m"].mean(),
        "u10_mean": g["wind_u_component_10m"].mean(), "v10_mean": g["wind_v_component_10m"].mean(),
        "ws10_mean": g["wind_speed_10m"].mean(),
        "blh_mean": g["boundary_layer_height"].mean(), "blh_min": g["boundary_layer_height"].min(),
        "blh_max": g["boundary_layer_height"].max(),
        "mslp_mean": g["pressure_msl"].mean(),
        "precip_sum": g["precipitation"].sum(min_count=min_hours),
        "cloud_mean": g["cloud_cover"].mean(),
        "swrad_mean": g["shortwave_radiation"].mean(),
    })
    evening = h["local_hour"].between(18, 23)
    out["blh_evening_mean"] = h[evening].groupby("date")["boundary_layer_height"].mean()
    out["ventilation_mean"] = (h["boundary_layer_height"] * h["wind_speed_10m"]).groupby(h["date"]).mean()
    full = out["n_hours"] >= min_hours
    blh_ok = out["n_hours_blh"] >= min_hours
    blh_cols = ["blh_mean", "blh_min", "blh_max", "blh_evening_mean", "ventilation_mean"]
    other = [c for c in out.columns if c not in blh_cols + ["n_hours", "n_hours_blh"]]
    out.loc[~full, other] = np.nan
    out.loc[~blh_ok, blh_cols] = np.nan
    out = out.drop(columns=["n_hours", "n_hours_blh"]).add_prefix("era5_")
    out.index.name = "date"
    return out


def cams_daily(min_hours: int = 20) -> pd.DataFrame:
    dom = "cams_global"
    h = pd.DataFrame({v: _om_hourly(dom, v) for v in openmeteo_s3.CAMS_VARS})
    if h.empty:
        return h
    h["date"] = _local_day(h.index.to_series())
    g = h.groupby("date")
    out = g[openmeteo_s3.CAMS_VARS].mean()
    n = g["pm2_5"].count()
    out.loc[n < min_hours, :] = np.nan
    out["pm2_5_max"] = g["pm2_5"].max().where(n >= min_hours)
    out = out.add_prefix("cams_")
    out.index.name = "date"
    return out
