"""Leakage-safe feature table: one row per forecast ISSUE day D, target = PM2.5 on day D+1.

Information set at issue time (end of local day D): PM2.5 hours of days <= D, measured
weather (ISD) of days <= D, ERA5 / CAMS of days <= D. Every feature is computed from a
daily table by *shifting forward* (``shift(k)`` on a contiguous daily index), so a value
for row D can never come from a later day. Calendar features describe the TARGET day
D+1, which is known in advance and therefore not leakage.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _contiguous(df: pd.DataFrame, start, end) -> pd.DataFrame:
    idx = pd.date_range(start, end, freq="D", name="date")
    return df.reindex(idx)


def build(pm_daily: pd.DataFrame, pm_hourly: pd.DataFrame, met_tables: list[pd.DataFrame],
          cfg: dict) -> pd.DataFrame:
    fc = cfg["features"]
    h = int(cfg["study"]["horizon_days"])
    start = pd.Timestamp(cfg["study"]["period_start"]) - pd.Timedelta(days=max(fc["pm_rolling_days"]) + 7)
    end = pd.Timestamp(cfg["study"]["period_end"])
    pmd = _contiguous(pm_daily.set_index("date"), start, end + pd.Timedelta(days=h))
    pm = pmd["pm2_5"]                                    # NaN when < 18 valid hours

    X = pd.DataFrame(index=pmd.index)
    X.index.name = "issue_date"
    # --- target (day D+h), never imputed ---------------------------------------------------
    X["target_date"] = X.index + pd.Timedelta(days=h)
    X["y_pm2_5"] = pm.shift(-h)
    X["y_valid"] = X["y_pm2_5"].notna()
    X["y_n_hours"] = pmd["pm2_5_n_hours"].shift(-h)
    X["y_dangerous"] = pmd["dangerous_day"].shift(-h).astype("boolean")
    X["y_exceeds_kg"] = pmd["exceeds_kg_limit"].shift(-h).astype("boolean")
    X["y_source"] = pmd["pm2_5_source"].shift(-h)

    # --- PM2.5 history (day D is lag 1) ----------------------------------------------------
    for k in fc["pm_lags_days"]:
        X[f"pm_lag{k}"] = pm.shift(k - 1)
    X["pm_max_lag1"] = pmd["pm2_5_max"]
    X["pm_n_hours_lag1"] = pmd["pm2_5_n_hours"]
    X["pm_lag1_minus_lag2"] = X["pm_lag1"] - X["pm_lag2"]
    for w in fc["pm_rolling_days"]:
        X[f"pm_roll{w}_mean"] = pm.rolling(w, min_periods=max(2, w // 2)).mean()
        X[f"pm_roll{w}_n"] = pm.rolling(w, min_periods=1).count()
    X["pm_roll7_max"] = pm.rolling(7, min_periods=4).max()
    X["pm_dangerous_days_last7"] = (pmd["dangerous_day"].astype("float")
                                    .rolling(7, min_periods=4).sum())
    # last evening hours of day D (inversion build-up), from the QC'd hourly series
    tail = fc["hourly_tail_hours"]
    ev = pm_hourly[pm_hourly["local_hour"].isin(tail)].groupby("local_date")["pm2_5_qc"]
    ev_mean = ev.mean().where(ev.count() >= len(tail) // 2)
    X["pm_evening_mean_lag1"] = ev_mean.reindex(X.index)
    last = pm_hourly[pm_hourly["local_hour"] == 23].set_index("local_date")["pm2_5_qc"]
    X["pm_hour23_lag1"] = last.reindex(X.index)

    # --- weather / model predictors of day D (lag 1) and D-1 (lag 2) ----------------------
    for t in met_tables:
        t = _contiguous(t, start, end + pd.Timedelta(days=h))
        for c in t.columns:
            X[f"{c}_lag1"] = t[c]
        for c in [c for c in t.columns if c.endswith(("temp_mean", "t2m_mean", "blh_mean",
                                                      "ws10_mean", "wind_speed_mean"))]:
            X[f"{c}_d1"] = t[c] - t[c].shift(1)          # change from D-1 to D

    # --- calendar of the TARGET day (known in advance) -------------------------------------
    td = X["target_date"]
    doy = td.dt.dayofyear
    X["cal_doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    X["cal_doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    X["cal_month"] = td.dt.month
    X["cal_dow"] = td.dt.dayofweek
    X["cal_weekend"] = (td.dt.dayofweek >= 5).astype(int)
    md = td.dt.month * 100 + td.dt.day
    X["cal_heating_season_nominal"] = ((md >= 1015) | (md <= 415)).astype(int)  # Bishkek: 15 Oct - 15 Apr

    X = X.loc[pd.Timestamp(cfg["study"]["period_start"]) - pd.Timedelta(days=h):
              end - pd.Timedelta(days=h)]
    return X.reset_index()


FEATURE_PREFIXES = ("pm_", "isd_", "era5_", "cams_", "cal_")


def feature_columns(X: pd.DataFrame, exclude_prefixes=()) -> list[str]:
    cols = [c for c in X.columns if c.startswith(FEATURE_PREFIXES)]
    return [c for c in cols if not c.startswith(tuple(exclude_prefixes))]
