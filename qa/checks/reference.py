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
