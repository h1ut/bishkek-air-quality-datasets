# fetch/common.py
from __future__ import annotations
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
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


def _frange(start, stop, step):
    out, i = [], 0
    while start + i * step <= stop + 1e-9:
        out.append(round(start + i * step, 4))
        i += 1
    return out


def build_grid(bbox: dict, spacing: float) -> list[dict]:
    cells = []
    for lat in _frange(bbox["min_lat"], bbox["max_lat"], spacing):
        for lon in _frange(bbox["min_lon"], bbox["max_lon"], spacing):
            cells.append({"cell_id": f"{lat:.4f}_{lon:.4f}", "lat": lat, "lon": lon})
    return cells


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
