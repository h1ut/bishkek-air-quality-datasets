"""Post-build validation of data/prepared/* (exit code 1 on any FAIL).

    python -m prep.checks
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from prep import features, pm
from prep.build import embassy_hourly, load_cfg

P = Path("data/prepared")
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(("PASS" if ok else "FAIL", name, detail))


def raw_integrity() -> None:
    man = Path("data/raw/MANIFEST.jsonl")
    if not man.exists():
        check("raw.manifest_present", False, "MANIFEST.jsonl missing"); return
    recs = {}
    for line in man.read_text(encoding="utf-8").splitlines():
        r = json.loads(line); recs[r["path"]] = r
    bad = [p for p, r in recs.items()
           if not Path(p).exists() or hashlib.sha256(Path(p).read_bytes()).hexdigest() != r["sha256"]]
    check("raw.sha256_unchanged", not bad, f"{len(recs)} raw files verified; {len(bad)} mismatched/missing")


def main() -> int:
    cfg = load_cfg()
    raw_integrity()
    h = pd.read_parquet(P / "pm25_hourly_qc.parquet")
    d = pd.read_csv(P / "pm25_daily_target.csv", parse_dates=["date"])
    X = pd.read_parquet(P / "features_all.parquet")

    # hourly grid
    t = pd.to_datetime(h["time_start_utc"], utc=True)
    check("hourly.unique_timestamps", t.is_unique)
    check("hourly.regular_1h_grid", bool((t.diff().dropna() == pd.Timedelta(hours=1)).all()))
    check("hourly.local_date_matches_tz",
          bool((t.dt.tz_convert("Asia/Bishkek").dt.tz_localize(None).dt.normalize()
                == pd.to_datetime(h["local_date"])).all()))
    kept = h[h["pm2_5_qc"].notna()]
    check("hourly.no_sentinel_or_error_in_qc", bool((kept["pm2_5_qc"] > cfg["qc_pm25_hourly"]["min_valid"]).all()
                                                    and (kept["pm2_5_qc"] < cfg["qc_pm25_hourly"]["max_valid"]).all()))
    w0, w1 = cfg["us_embassy_contaminated_window"]
    win = pd.to_datetime(h["local_date"]).between(w0, w1)
    check("hourly.contaminated_window_voided", int(h.loc[win, "pm2_5_qc"].notna().sum()) == 0)

    # daily target
    check("daily.unique_dates", d["date"].is_unique)
    check("daily.contiguous", bool((d["date"].diff().dropna() == pd.Timedelta(days=1)).all()))
    check("daily.n_hours_le_24", bool((d["pm2_5_n_hours"] <= 24).all()))
    mv = cfg["thresholds"]["min_valid_hours"]
    check("daily.target_nan_when_incomplete", bool(d.loc[d["pm2_5_n_hours"] < mv, "pm2_5"].isna().all()))
    tr = d["pm2_5"].map(pm.trunc1)
    exp = tr >= cfg["thresholds"]["dangerous_pm25_24h"]
    dd = d["dangerous_day"].astype("boolean")
    check("daily.dangerous_rule_epa_trunc", bool((dd[d["pm2_5"].notna()] == exp[d["pm2_5"].notna()]).all()))

    # features / target alignment
    X["issue_date"] = pd.to_datetime(X["issue_date"]); X["target_date"] = pd.to_datetime(X["target_date"])
    check("features.issue_unique_increasing", X["issue_date"].is_monotonic_increasing and X["issue_date"].is_unique)
    check("features.target_is_issue_plus_h",
          bool((X["target_date"] - X["issue_date"] == pd.Timedelta(days=cfg["study"]["horizon_days"])).all()))
    m = X.merge(d[["date", "pm2_5"]], left_on="target_date", right_on="date", how="left")
    same = (m["y_pm2_5"].isna() & m["pm2_5"].isna()) | np.isclose(m["y_pm2_5"], m["pm2_5"])
    check("features.target_not_imputed_equals_daily", bool(same.all()))
    lag1 = X.merge(d[["date", "pm2_5"]], left_on="issue_date", right_on="date", how="left")
    same1 = (lag1["pm_lag1"].isna() & lag1["pm2_5"].isna()) | np.isclose(lag1["pm_lag1"], lag1["pm2_5"])
    check("features.pm_lag1_is_issue_day", bool(same1.all()))

    # leakage test: recompute features with every observation AFTER the issue day removed
    hh = embassy_hourly(cfg, {})
    full_daily = pm.daily(hh, cfg["thresholds"])
    src = hh.groupby("local_date")["source"].agg(lambda s: "|".join(sorted(set(s.dropna()))) or None)
    full_daily["pm2_5_source"] = full_daily["date"].map(src)
    from prep import met
    years = range(int(cfg["study"]["period_start"][:4]), int(cfg["study"]["period_end"][:4]) + 1)
    st = cfg["sources"]["isd_stations"]
    met_full = [met.isd_daily(st["manas_metar"], years, "isd_manas_", 36),
                met.isd_daily(st["bishkek_synop"], years, "isd_bishkek_", 6),
                met.era5_daily(), met.cams_daily()]
    met_full = [t_ for t_ in met_full if not t_.empty]
    Xf = features.build(full_daily, hh, met_full, cfg).set_index("issue_date")
    rng = np.random.default_rng(0)
    cand = X.loc[X["y_valid"], "issue_date"].to_numpy()
    sample = rng.choice(cand, size=min(25, len(cand)), replace=False)
    fcols = features.feature_columns(Xf.reset_index())
    leaks = []
    for D in sample:
        D = pd.Timestamp(D)
        cut_d = full_daily.copy()
        cut_d.loc[cut_d["date"] > D, ["pm2_5", "pm2_5_max", "pm2_5_n_hours", "dangerous_day",
                                      "exceeds_kg_limit"]] = np.nan
        cut_h = hh.copy(); cut_h.loc[pd.to_datetime(cut_h["local_date"]) > D, "pm2_5_qc"] = np.nan
        cut_m = [t_.mask(pd.Series(t_.index > D, index=t_.index), axis=0) for t_ in met_full]
        Xc = features.build(cut_d, cut_h, cut_m, cfg).set_index("issue_date")
        a, b = Xf.loc[D, fcols].astype(float), Xc.loc[D, fcols].astype(float)
        diff = ~((a.isna() & b.isna()) | np.isclose(a, b, equal_nan=True))
        if diff.any():
            leaks.append((str(D.date()), list(a.index[diff])[:5]))
    check("leakage.features_use_only_past", not leaks,
          f"{len(sample)} random issue days recomputed with all data after D removed; "
          f"{len(leaks)} differ {leaks[:2]}")

    # splits
    lab = X["split"]
    for a_, b_ in (("train", "validation"), ("validation", "test")):
        ta, tb = X.loc[lab == a_, "target_date"], X.loc[lab == b_, "target_date"]
        gap = (tb.min() - ta.max()).days - 1
        check(f"splits.{a_}_before_{b_}_with_embargo", gap >= cfg["splits"]["embargo_days"],
              f"last {a_} target {ta.max().date()}, first {b_} target {tb.min().date()}, gap {gap} d")
        check(f"splits.{a_}_{b_}_no_shared_rows", set(X.index[lab == a_]).isdisjoint(set(X.index[lab == b_])))
    valid_in_window = X["y_valid"] & X["target_date"].between(w0, w1)
    check("splits.no_target_in_contaminated_window", int(valid_in_window.sum()) == 0)
    for name in ("train", "validation", "test"):
        part = pd.read_parquet(P / f"{name}_raw.parquet")
        check(f"splits.{name}_targets_all_valid", bool(part["y_pm2_5"].notna().all()), f"{len(part)} rows")

    # preprocessing fitted on train only
    pre = json.loads((P / "preprocessing_train_fit.json").read_text(encoding="utf-8"))
    trn = pd.read_parquet(P / "train_raw.parquet")
    med_ok = all((np.isnan(pre["median"][c]) and trn[c].isna().all()) or
                 np.isclose(pre["median"][c], trn[c].astype(float).median()) for c in pre["columns"])
    check("preprocess.medians_from_train", med_ok, f"{len(pre['columns'])} columns")
    trm = pd.read_parquet(P / "train_model.parquet")
    zc = [c for c in pre["columns"]]
    check("preprocess.train_standardised", bool(np.allclose(trm[zc].mean(), 0, atol=1e-6)))
    vm = pd.read_parquet(P / "validation_model.parquet")
    check("preprocess.no_nan_in_model_matrices", not trm[zc].isna().any().any() and not vm[zc].isna().any().any())

    lines = ["# Post-build checks", "", f"{sum(r[0]=='PASS' for r in results)} PASS / "
             f"{sum(r[0]=='FAIL' for r in results)} FAIL", "", "| result | check | detail |", "|---|---|---|"]
    lines += [f"| {r} | `{n}` | {dt} |" for r, n, dt in results]
    (P / "checks_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if all(r[0] == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
