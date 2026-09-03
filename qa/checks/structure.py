from __future__ import annotations
import pandas as pd

from qa.checks import Finding
from qa.loaders import STATION_SCHEMA, GRID_SCHEMA, AQ_VARS, WX_VARS
from catalog.standards import require


def _md_table(df: pd.DataFrame) -> str:
    """Small GitHub-flavored markdown table (avoids the optional tabulate dep)."""
    cols = [str(c) for c in df.columns]
    rows = [[("" if pd.isna(v) else str(v)) for v in rec]
            for rec in df.itertuples(index=False, name=None)]
    lines = ["| " + " | ".join(cols) + " |",
             "| " + " | ".join("---" for _ in cols) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


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
                       _md_table(ex[have]))
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
