from __future__ import annotations
import numpy as np
import pandas as pd

from qa.checks import Finding


def _daily_pm(df):
    if df is None or df.empty or "pm2_5" not in df.columns or "date" not in df.columns:
        return None
    s = df.copy()
    s["date"] = pd.to_datetime(s["date"])
    return pd.to_numeric(s.set_index("date")["pm2_5"], errors="coerce").dropna().sort_index()


def bishkek_series(ctx) -> dict:
    out = {}
    if ctx.grid is not None and not ctx.grid.empty and ctx.bishkek_cell_id:
        g = ctx.grid[ctx.grid["cell_id"] == ctx.bishkek_cell_id]
        s = _daily_pm(g)
        if s is not None and len(s):
            out["cams_grid"] = s
    if ctx.airnow is not None:
        s = _daily_pm(ctx.airnow)
        if s is not None and len(s):
            out["airnow"] = s
    for name, df in (ctx.openaq or {}).items():
        if "bishkek" in name.lower():
            s = _daily_pm(df)
            if s is not None and len(s):
                out["openaq"] = s
    for name, df in (ctx.zenodo or {}).items():
        if "embassy" in name.lower():
            s = _daily_pm(df)
            if s is not None and len(s):
                out["zenodo"] = s
    return out


def pair_stats(a: pd.Series, b: pd.Series) -> dict:
    m = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    if len(m) < 2:
        return {"n": len(m), "r": float("nan"), "bias": float("nan"),
                "rmse": float("nan"), "mae": float("nan")}
    diff = m["a"] - m["b"]
    return {"n": int(len(m)), "r": float(m["a"].corr(m["b"])),
            "bias": float(diff.mean()),
            "rmse": float(np.sqrt((diff ** 2).mean())),
            "mae": float(diff.abs().mean())}


_GROUND = {"airnow", "openaq", "zenodo"}
_ORDER = {"PASS": 0, "INFO": 1, "WARN": 2, "FAIL": 3}


def run(ctx) -> list[Finding]:
    th = ctx.thresholds.get("agreement", {})
    minov = th.get("min_overlap_days", 30)
    series = bishkek_series(ctx)
    findings = []

    if len(series) < 2:
        findings.append(Finding("agreement.pairwise", "INFO",
                                f"only {len(series)} Bishkek pm2_5 source(s) — need >= 2"))
    else:
        names = sorted(series)
        rows, worst = [], "PASS"
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                st = pair_stats(series[a], series[b])
                rows.append(f"| {a} vs {b} | {st['n']} | {st['r']:.3f} | {st['bias']:.2f} | "
                            f"{st['rmse']:.2f} | {st['mae']:.2f} |")
                if st["n"] < minov:
                    continue
                both_ground = a in _GROUND and b in _GROUND
                if both_ground:
                    if st["r"] < th.get("ground_r_fail", 0.5):
                        worst = "FAIL"
                    elif (st["r"] < th.get("ground_r_warn", 0.8)
                          or abs(st["bias"]) > th.get("ground_bias_warn", 10.0)):
                        worst = max(worst, "WARN", key=_ORDER.get)
                else:  # model vs ground — orient bias as model minus ground
                    model_name = a if a == "cams_grid" else b
                    ground_name = b if a == "cams_grid" else a
                    mb = pair_stats(series[model_name], series[ground_name])["bias"]
                    if st["r"] < th.get("model_r_warn", 0.4) or mb > 0:
                        worst = max(worst, "WARN", key=_ORDER.get)
                    else:
                        worst = max(worst, "INFO", key=_ORDER.get)
        table = ("| pair | n | Pearson r | bias (a-b) | RMSE | MAE |\n|---|---|---|---|---|---|\n"
                 + "\n".join(rows))
        summ = ("ground pairs must agree closely; model (cams_grid) is expected to "
                "under-estimate — a positive model bias or low r is flagged")
        findings.append(Finding("agreement.pairwise", worst, summ, table))

    if len(series) >= 1:
        danger = ctx.standards["epa_aqi_unhealthy_pm25"]
        kg = ctx.standards["kg_mpc_daily_pm25"]
        erows = [f"| {n} | {int((s > danger).sum())} | {int((s > kg).sum())} | {len(s)} |"
                 for n, s in series.items()]
        findings.append(Finding("agreement.exceedance_counts", "INFO",
            "days each Bishkek source calls dangerous (>55.4) / over the KG limit (>35)",
            "| source | days >55.4 | days >35 | total days |\n|---|---|---|---|\n" + "\n".join(erows)))
    return findings
