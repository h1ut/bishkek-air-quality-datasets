"""Sanity baselines on the prepared splits (no hyper-parameter tuning, test used once).

    python -m prep.baseline   # -> data/prepared/baseline_results.md / .json

Models: persistence (y_hat = PM2.5 of issue day), train monthly climatology, ridge on the
train-fitted imputed/standardised matrix, and a histogram gradient-boosting regressor on the
raw (NaN-aware) features with library defaults. Both learned models predict log1p(PM2.5).
Dangerous-day skill uses the same EPA rule as the labels: trunc1(y_hat) >= 55.5.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge

from prep import pm

P = Path("data/prepared")


def metrics(y, yhat, thr) -> dict:
    y = np.asarray(y, float); yhat = np.asarray(yhat, float)
    err = yhat - y
    obs = np.array([pm.trunc1(v) >= thr for v in y])
    pred = np.array([pm.trunc1(v) >= thr for v in yhat])
    tp = int((obs & pred).sum()); fp = int((~obs & pred).sum()); fn = int((obs & ~pred).sum())
    out = {"n": int(len(y)), "MAE": float(np.mean(np.abs(err))), "RMSE": float(np.sqrt(np.mean(err ** 2))),
           "bias": float(np.mean(err)),
           "MAE_dangerous_days": float(np.mean(np.abs(err[obs]))) if obs.any() else float("nan"),
           "MAE_other_days": float(np.mean(np.abs(err[~obs]))) if (~obs).any() else float("nan"),
           "n_dangerous": int(obs.sum()),
           "recall": tp / (tp + fn) if tp + fn else float("nan"),
           "precision": tp / (tp + fp) if tp + fp else float("nan"),
           "CSI": tp / (tp + fp + fn) if tp + fp + fn else float("nan")}
    return out


def main():
    cfg = yaml.safe_load(Path("prep/config.yaml").read_text(encoding="utf-8"))
    thr = cfg["thresholds"]["dangerous_pm25_24h"]
    pre = json.loads((P / "preprocessing_train_fit.json").read_text(encoding="utf-8"))
    raw = {s: pd.read_parquet(P / f"{s}_raw.parquet") for s in ("train", "validation", "test")}
    mod = {s: pd.read_parquet(P / f"{s}_model.parquet") for s in ("train", "validation", "test")}
    mcols = pre["columns"] + [f"{c}__missing" for c in pre["missing_indicators"]]
    rcols = pre["columns"]
    tr = raw["train"]
    clim = tr.groupby(tr["target_date"].dt.month)["y_pm2_5"].mean()
    ridge = Ridge(alpha=1.0).fit(mod["train"][mcols], np.log1p(tr["y_pm2_5"].clip(lower=0)))
    hgb = HistGradientBoostingRegressor(random_state=0).fit(tr[rcols], np.log1p(tr["y_pm2_5"].clip(lower=0)))
    res, lines = {}, []
    for s in ("validation", "test"):
        r, m = raw[s], mod[s]
        y = r["y_pm2_5"].to_numpy()
        persist = r["pm_lag1"].fillna(r["pm_roll7_mean"]).fillna(r["target_date"].dt.month.map(clim))
        preds = {
            "persistence (D -> D+1)": persist,
            "train monthly climatology": r["target_date"].dt.month.map(clim),
            "ridge (log1p, train-fit impute+scale)": np.expm1(ridge.predict(m[mcols])),
            "hist gradient boosting (log1p, defaults)": np.expm1(hgb.predict(r[rcols])),
        }
        res[s] = {k: metrics(y, v, thr) for k, v in preds.items()}
    lines += ["# Baseline sanity check", "",
              "Trained on `train` only; no tuning; `test` evaluated once. Dangerous = trunc1(PM2.5) >= 55.5 µg/m³.", ""]
    for s in res:
        lines += [f"## {s}", "", "| model | n | MAE | RMSE | bias | MAE dangerous | MAE other | n dangerous | recall | precision | CSI |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in res[s].items():
            lines.append(f"| {k} | {v['n']} | {v['MAE']:.1f} | {v['RMSE']:.1f} | {v['bias']:+.1f} | "
                         f"{v['MAE_dangerous_days']:.1f} | {v['MAE_other_days']:.1f} | {v['n_dangerous']} | "
                         f"{v['recall']:.2f} | {v['precision']:.2f} | {v['CSI']:.2f} |")
        lines.append("")
    (P / "baseline_results.md").write_text("\n".join(lines), encoding="utf-8")
    (P / "baseline_results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
