"""PM2.5: load raw OpenAQ-archive hourly records, apply QC, aggregate to LOCAL calendar days.

Time convention (verified on the raw files): the archive ``datetime`` is the END of the
averaging hour in local time with an explicit offset, e.g. the file for 2020-01-10 holds
``2020-01-10T01:00:00+06:00`` ... ``2020-01-11T00:00:00+06:00``. The hour therefore BEGINS
one hour earlier, and the local calendar day of an hour is ``(datetime - 1 h).date()``.
US EPA computes the 24-h PM2.5 average over the local calendar day (midnight to midnight),
so that is the day definition used for the target and the dangerous-day flag.
"""
from __future__ import annotations

import glob
import math
from pathlib import Path

import numpy as np
import pandas as pd

from prep.sources.openaq_archive import raw_dir

TZ = "Asia/Bishkek"


def load_raw(location_id: int, parameter: str | None = "pm25") -> pd.DataFrame:
    """All raw rows for a location, unmodified except for parsing. One row per archive line."""
    files = sorted(glob.glob(str(raw_dir() / f"locationid={location_id}" / "**" / "*.csv.gz"),
                             recursive=True))
    frames = []
    for fp in files:
        d = pd.read_csv(fp, dtype={"value": "float64", "sensors_id": "int64"})
        d["source_file"] = Path(fp).name
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if parameter:
        df = df[df["parameter"] == parameter].copy()
    df["utc_offset"] = df["datetime"].str[-6:]
    ts_end = pd.to_datetime(df["datetime"], utc=True)
    df["time_start_utc"] = ts_end - pd.Timedelta(hours=1)
    df["time_start_local"] = df["time_start_utc"].dt.tz_convert(TZ)
    df["local_date"] = df["time_start_local"].dt.tz_localize(None).dt.normalize()
    return df.reset_index(drop=True)


def _runs(values: pd.Series) -> pd.Series:
    """Length of the run of identical consecutive non-NaN values each element belongs to."""
    v = values.to_numpy()
    change = np.ones(len(v), dtype=bool)
    change[1:] = ~((v[1:] == v[:-1]) & ~np.isnan(v[1:]) & ~np.isnan(v[:-1]))
    run_id = np.cumsum(change)
    sizes = pd.Series(run_id).map(pd.Series(run_id).value_counts())
    return pd.Series(np.where(np.isnan(v), 0, sizes.to_numpy()), index=values.index)


def qc_hourly(raw: pd.DataFrame, qc: dict, start: str, end: str) -> tuple[pd.DataFrame, dict]:
    """Return a complete hourly grid (local time) with QC flags and a log of what changed.

    Flags (``qc_flag``): ok | neg_small (kept) | missing | missing_sentinel | duplicate_conflict |
    error_code | bam_floor | below_min | flatline | spike (all voided in ``pm2_5_qc``).
    High values are never removed for being high: 'spike' needs an isolated one-hour jump to
    > 6x BOTH neighbouring hours; multi-hour episodes are untouched.
    """
    log = {"raw_rows": int(len(raw))}
    d = raw[["time_start_utc", "value", "sensors_id", "units", "lat", "lon"]].copy()
    log["units"] = sorted(d["units"].unique().tolist())
    log["sensors"] = sorted(d["sensors_id"].unique().tolist())
    # exact duplicates (same hour, same value) collapse silently; conflicting ones are voided
    exact = d.duplicated(["time_start_utc", "value"], keep="first")
    log["exact_duplicate_rows"] = int(exact.sum())
    d = d[~exact]
    conflict_hours = d.loc[d.duplicated("time_start_utc", keep=False), "time_start_utc"].unique()
    log["conflicting_duplicate_hours"] = int(len(conflict_hours))
    d = d.drop_duplicates("time_start_utc", keep="first").set_index("time_start_utc").sort_index()

    t0 = pd.Timestamp(start, tz=TZ).tz_convert("UTC")
    t1 = (pd.Timestamp(end, tz=TZ) + pd.Timedelta(hours=23)).tz_convert("UTC")
    grid = pd.date_range(t0, t1, freq="h", tz="UTC")
    log["rows_outside_window"] = int(((d.index < t0) | (d.index > t1)).sum())
    off_grid = d.index[(d.index >= t0) & (d.index <= t1)].difference(grid)
    log["off_grid_timestamps"] = int(len(off_grid))
    h = d.reindex(grid)
    h.index.name = "time_start_utc"
    h = h.rename(columns={"value": "pm2_5_raw"})
    flag = pd.Series("ok", index=h.index, dtype=object)
    v = h["pm2_5_raw"]
    flag[v.isna()] = "missing"
    sentinel = v.eq(qc["missing_sentinel"])
    flag[sentinel] = "missing_sentinel"
    v = v.mask(sentinel)
    flag[h.index.isin(conflict_hours)] = "duplicate_conflict"
    codes = set(float(c) for c in qc["error_codes"])
    flag[(v.isin(codes) | (v >= qc["max_valid"])) & flag.eq("ok")] = "error_code"
    flag[v.eq(qc["bam_floor_value"]) & flag.eq("ok")] = "bam_floor"
    flag[(v < qc["min_valid"]) & flag.eq("ok")] = "below_min"
    flag[(v < 0) & (v >= qc["min_valid"]) & flag.eq("ok")] = "neg_small"
    usable = v.where(flag.isin(["ok", "neg_small"]))
    runs = _runs(usable)
    flat = (runs >= qc["flatline_hours"]) & (usable > qc["flatline_min_value"])
    flag[flat] = "flatline"
    prev, nxt = v.shift(1), v.shift(-1)
    spike = ((v > qc["spike_min"]) & (v > qc["spike_ratio"] * prev.clip(lower=1))
             & (v > qc["spike_ratio"] * nxt.clip(lower=1)))
    flag[spike & flag.eq("ok")] = "spike"
    h["qc_flag"] = flag
    drop = ~flag.isin(["ok", "neg_small"])
    h["pm2_5_qc"] = v.mask(drop)
    h["time_start_local"] = h.index.tz_convert(TZ)
    h["local_date"] = h["time_start_local"].dt.tz_localize(None).dt.normalize()
    h["local_hour"] = h["time_start_local"].dt.hour
    log["flag_counts"] = {k: int(n) for k, n in flag.value_counts().items()}
    return h.reset_index(), log


def trunc1(x: float) -> float:
    """EPA truncation of a 24-h PM2.5 mean to one decimal before categorising."""
    return math.floor(x * 10 + 1e-9) / 10 if pd.notna(x) else np.nan


def daily(h: pd.DataFrame, thresholds: dict) -> pd.DataFrame:
    """Local-calendar-day aggregates of the QC'd hourly series (target table)."""
    g = h.groupby("local_date")
    out = pd.DataFrame({
        "pm2_5_n_hours": g["pm2_5_qc"].count(),
        "pm2_5_mean_all": g["pm2_5_qc"].mean(),
        "pm2_5_max": g["pm2_5_qc"].max(),
        "pm2_5_n_spike": g["qc_flag"].apply(lambda s: int((s == "spike").sum())),
        "pm2_5_n_flatline": g["qc_flag"].apply(lambda s: int((s == "flatline").sum())),
        "pm2_5_n_error": g["qc_flag"].apply(lambda s: int(s.isin(["error_code", "below_min", "bam_floor",
                                                                   "duplicate_conflict"]).sum())),
    })
    valid = out["pm2_5_n_hours"] >= thresholds["min_valid_hours"]
    out["pm2_5_valid_day"] = valid
    out["pm2_5"] = out["pm2_5_mean_all"].where(valid)          # the target: NaN if < 18 valid hours
    out["pm2_5_max"] = out["pm2_5_max"].where(valid)
    t = out["pm2_5"].map(trunc1)
    out["dangerous_day"] = (t >= thresholds["dangerous_pm25_24h"]).astype("boolean").mask(~valid)
    out["exceeds_kg_limit"] = (out["pm2_5"] > thresholds["kg_limit_pm25_24h"]).astype("boolean").mask(~valid)
    out.index.name = "date"
    return out.reset_index()


def legacy_daily_utc(raw: pd.DataFrame) -> pd.DataFrame:
    """What the existing ``fetch.common.to_daily`` would produce from the same hourly rows:
    UTC calendar day of the archive timestamp, no QC, no dedup, no completeness rule."""
    d = raw.copy()
    d["date"] = pd.to_datetime(d["datetime"], utc=True).dt.tz_localize(None).dt.normalize()
    g = d.groupby("date")["value"]
    return pd.DataFrame({"pm2_5": g.mean(), "n_rows": g.count()}).reset_index()
