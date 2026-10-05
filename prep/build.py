"""End-to-end, reproducible preparation of the Bishkek next-day PM2.5 dataset.

    python -m prep.build            # raw (data/raw, read-only) -> data/prepared/*

Steps: (1) load raw US Embassy hourly PM2.5 (OpenAQ archive locations 8225 + 8827);
(2) hourly QC with explicit flags; (3) local-day target with the EPA 18-of-24-hour rule;
(4) measured weather (NOAA ISD), ERA5 and CAMS daily predictors; (5) leakage-safe features;
(6) chronological splits with embargo; (7) train-only imputation/scaling;
(8) outputs + processing log + checks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from prep import features, met, pm, splits
from prep.sources.openaq_archive import US_EMBASSY, US_EMBASSY_DUP

OUT = Path("data/prepared")


def load_cfg(path="prep/config.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def contamination_mask(h: pd.DataFrame, window: list[str]) -> pd.Series:
    t0, t1 = (pd.Timestamp(x) for x in window)
    return h["local_date"].between(t0, t1)


def embassy_hourly(cfg: dict, log: dict) -> pd.DataFrame:
    """QC'd hourly US Embassy series: 8225 primary, 8827 only for hours 8225 lacks."""
    qc = cfg["qc_pm25_hourly"]
    start, end = "2019-09-01", cfg["study"]["period_end"]
    raw_a = pm.load_raw(US_EMBASSY)
    raw_b = pm.load_raw(US_EMBASSY_DUP)
    ha, log["qc_8225"] = pm.qc_hourly(raw_a, qc, start, end)
    hb, log["qc_8827"] = pm.qc_hourly(raw_b, qc, start, end)
    # 8827 is the same instrument with a period-dependent +-1 h timestamp offset (audit A3).
    # Re-align it with the offset estimated where both overlap, then use it only to fill gaps.
    shifts = cfg["us_embassy_dup_alignment"]
    hb = hb.set_index("time_start_utc")
    aligned = []
    for seg in shifts:
        a, b, k = pd.Timestamp(seg["from"], tz="UTC"), pd.Timestamp(seg["to"], tz="UTC"), int(seg["shift_h"])
        part = hb.loc[(hb.index >= a) & (hb.index < b), ["pm2_5_qc", "qc_flag"]].copy()
        part.index = part.index + pd.Timedelta(hours=k)
        aligned.append(part)
    hb = pd.concat(aligned)
    hb = hb[~hb.index.duplicated()]
    ha = ha.set_index("time_start_utc")
    fill = ha["pm2_5_qc"].isna() & hb["pm2_5_qc"].reindex(ha.index).notna()
    ha["source"] = np.where(ha["pm2_5_qc"].notna(), "openaq:8225", None)
    ha.loc[fill, "pm2_5_qc"] = hb["pm2_5_qc"].reindex(ha.index)[fill]
    ha.loc[fill, "source"] = "openaq:8827"
    ha.loc[fill, "qc_flag"] = "filled_from_8827"
    log["hours_filled_from_8827"] = int(fill.sum())
    # foreign interleaved stream (audit A1): void every hour inside the contaminated window
    cm = contamination_mask(ha, cfg["us_embassy_contaminated_window"])
    log["hours_voided_contaminated_window"] = int((cm & ha["pm2_5_qc"].notna()).sum())
    ha.loc[cm, "pm2_5_qc"] = np.nan
    ha.loc[cm, "qc_flag"] = "feed_contaminated"
    ha.loc[cm, "source"] = None
    log["final_hourly_flag_counts"] = {k: int(v) for k, v in ha["qc_flag"].value_counts().items()}
    log["final_hours_by_source"] = {str(k): int(v) for k, v in ha["source"].value_counts(dropna=False).items()}
    return ha.reset_index()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="prep/config.yaml")
    args = ap.parse_args(argv)
    cfg = load_cfg(args.config)
    OUT.mkdir(parents=True, exist_ok=True)
    log: dict = {}

    h = embassy_hourly(cfg, log)
    d = pm.daily(h, cfg["thresholds"])
    src = h.groupby("local_date")["source"].agg(lambda s: "|".join(sorted(set(s.dropna()))) or None)
    d["pm2_5_source"] = d["date"].map(src).where(d["pm2_5_valid_day"])
    d = d[(d["date"] >= cfg["study"]["period_start"]) & (d["date"] <= cfg["study"]["period_end"])]

    years = range(int(cfg["study"]["period_start"][:4]), int(cfg["study"]["period_end"][:4]) + 1)
    st = cfg["sources"]["isd_stations"]
    met_tables = [
        met.isd_daily(st["manas_metar"], years, "isd_manas_", min_obs=36),
        met.isd_daily(st["bishkek_synop"], years, "isd_bishkek_", min_obs=6),
        met.era5_daily(),
        met.cams_daily(),
    ]
    met_tables = [t for t in met_tables if not t.empty]
    X = features.build(d, h, met_tables, cfg)
    X["split"] = splits.assign(X, cfg["splits"], cfg["splits"]["embargo_days"])

    feat_cols = features.feature_columns(X)
    train = X[(X["split"] == "train") & X["y_valid"]]
    # model matrices: drop predictors that are mostly absent in TRAIN (decided on train only;
    # e.g. CAMS starts 2022-08-04, after the training period). Raw files keep every column.
    coverage = train[feat_cols].notna().mean()
    model_cols = [c for c in feat_cols if coverage[c] >= 0.5]
    log["model_columns_dropped_lt50pct_train_coverage"] = sorted(set(feat_cols) - set(model_cols))
    pre = splits.TrainOnlyPreprocessor(model_cols).fit(train)

    # ---- outputs -------------------------------------------------------------------------
    h_out = h[["time_start_utc", "time_start_local", "local_date", "local_hour",
               "pm2_5_raw", "pm2_5_qc", "qc_flag", "source"]].copy()
    h_out["time_start_local"] = h_out["time_start_local"].astype(str)
    h_out.to_parquet(OUT / "pm25_hourly_qc.parquet", index=False)
    d.to_csv(OUT / "pm25_daily_target.csv", index=False)
    X.to_parquet(OUT / "features_all.parquet", index=False)
    key = ["issue_date", "target_date", "split", "y_pm2_5", "y_dangerous", "y_exceeds_kg",
           "y_n_hours", "y_source"]
    for name in ("train", "validation", "test"):
        part = X[(X["split"] == name) & X["y_valid"]]
        part[key + feat_cols].to_parquet(OUT / f"{name}_raw.parquet", index=False)
        pd.concat([part[key].reset_index(drop=True),
                   pre.transform(part).reset_index(drop=True)], axis=1) \
            .to_parquet(OUT / f"{name}_model.parquet", index=False)
    (OUT / "preprocessing_train_fit.json").write_text(pre.to_json(), encoding="utf-8")
    summary = (X.assign(y_dangerous=X["y_dangerous"].astype("float"), y_exceeds_kg=X["y_exceeds_kg"].astype("float"))
               .groupby("split").agg(rows=("issue_date", "size"), valid_targets=("y_valid", "sum"),
                                      first_target=("target_date", "min"), last_target=("target_date", "max"),
                                      dangerous_days=("y_dangerous", "sum"), kg_limit_days=("y_exceeds_kg", "sum"),
                                      mean_pm2_5=("y_pm2_5", "mean")))
    summary.to_csv(OUT / "split_summary.csv")
    (OUT / "processing_log.json").write_text(json.dumps(log, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in log.items() if not isinstance(v, dict)}, indent=1))
    print(X.groupby("split")["y_valid"].agg(["size", "sum"]))


if __name__ == "__main__":
    main()
