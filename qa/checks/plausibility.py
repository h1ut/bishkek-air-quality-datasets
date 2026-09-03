from __future__ import annotations
import pandas as pd

from qa.checks import Finding
from qa.loaders import AQ_VARS, WX_VARS


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
        return Finding(cid, "INFO", f"key columns absent: {set(keys) - set(have)}")
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
        _dupes("plausibility.duplicate_keys_stations", ctx.stations, ["station_key", "date"]),
        _gaps("plausibility.date_gaps", ctx.grid, "cell_id",
              th.get("gap", {}).get("warn_days", 7)),
        _cams_boundary("plausibility.cams_boundary", ctx.grid, ctx.bishkek_cell_id,
                       th.get("cams_boundary_date", "2022-08-04")),
    ]
