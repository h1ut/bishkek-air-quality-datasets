import numpy as np
import pandas as pd
import pytest

from prep import features, pm, splits

QC = {"missing_sentinel": -999, "bam_floor_value": -15, "min_valid": -10.0, "max_valid": 985.0,
      "error_codes": [985, 990, 995, 999], "flatline_hours": 6, "flatline_min_value": 2.0,
      "spike_ratio": 6.0, "spike_min": 300.0}
TH = {"dangerous_pm25_24h": 55.5, "kg_limit_pm25_24h": 35.0, "min_valid_hours": 18}


def _raw(values, start="2020-01-10T01:00:00+06:00"):
    """Archive-style rows: datetime = END of hour, local offset."""
    t = pd.date_range(pd.Timestamp(start), periods=len(values), freq="h")
    df = pd.DataFrame({"datetime": [x.isoformat() for x in t], "value": values,
                       "sensors_id": 1, "units": "µg/m³", "lat": 42.8, "lon": 74.6})
    ts_end = pd.to_datetime(df["datetime"], utc=True)
    df["time_start_utc"] = ts_end - pd.Timedelta(hours=1)
    df["time_start_local"] = df["time_start_utc"].dt.tz_convert("Asia/Bishkek")
    df["local_date"] = df["time_start_local"].dt.tz_localize(None).dt.normalize()
    return df


def test_trunc_rule_epa():
    assert pm.trunc1(55.49) == 55.4 and pm.trunc1(55.5) == 55.5 and pm.trunc1(55.59) == 55.5
    d = pm.daily(pd.DataFrame({"local_date": [pd.Timestamp("2020-01-01")] * 24,
                               "pm2_5_qc": [55.49] * 24, "qc_flag": ["ok"] * 24}), TH)
    assert not bool(d["dangerous_day"].iloc[0])     # 55.49 truncates to 55.4 -> not Unhealthy


def test_hour_ending_file_maps_to_one_local_day():
    r = _raw([10.0] * 24)                       # 01:00 .. 24:00 local of 2020-01-10
    assert r["local_date"].nunique() == 1
    assert r["local_date"].iloc[0] == pd.Timestamp("2020-01-10")


def test_qc_flags():
    vals = [20.0] * 30
    vals[2] = -999; vals[3] = -15; vals[4] = -3; vals[5] = -12; vals[6] = 990
    vals[10] = 700.0                            # isolated spike between 20s
    vals[15:22] = [8.0] * 7                     # 7 identical hours > 2 -> flatline
    r = _raw(vals)
    h, log = pm.qc_hourly(r, QC, "2020-01-10", "2020-01-11")
    f = h.set_index("time_start_utc")["qc_flag"].dropna()
    fl = list(f.loc[r["time_start_utc"]])
    assert fl[2] == "missing_sentinel" and fl[3] == "bam_floor" and fl[4] == "neg_small"
    assert fl[5] == "below_min" and fl[6] == "error_code" and fl[10] == "spike"
    assert all(x == "flatline" for x in fl[15:22])
    q = h.set_index("time_start_utc")["pm2_5_qc"].loc[r["time_start_utc"]].tolist()
    assert q[4] == -3 and np.isnan(q[10]) and np.isnan(q[2])


def test_real_episode_not_removed():
    vals = [50, 120, 260, 410, 520, 480, 390, 300, 200] + [80] * 15   # multi-hour smog peak
    h, _ = pm.qc_hourly(_raw([float(v) for v in vals]), QC, "2020-01-10", "2020-01-10")
    assert not (h["qc_flag"] == "spike").any()
    assert h["pm2_5_qc"].max() == 520


def test_daily_completeness_rule():
    vals = [30.0 + i for i in range(17)] + [np.nan] * 7
    r = _raw(vals).dropna(subset=["value"])
    h, _ = pm.qc_hourly(r, QC, "2020-01-10", "2020-01-10")
    d = pm.daily(h, TH)
    assert d["pm2_5_n_hours"].iloc[0] == 17 and np.isnan(d["pm2_5"].iloc[0])


def test_conflicting_duplicates_voided():
    r = _raw([10.0, 20.0, 30.0])
    dup = r.iloc[[1]].copy(); dup["value"] = 99.0
    h, log = pm.qc_hourly(pd.concat([r, dup]), QC, "2020-01-10", "2020-01-10")
    assert log["conflicting_duplicate_hours"] == 1
    assert (h["qc_flag"] == "duplicate_conflict").sum() == 1


def _cfg():
    return {"study": {"horizon_days": 1, "period_start": "2020-01-15", "period_end": "2020-03-31"},
            "features": {"pm_lags_days": [1, 2, 7], "pm_rolling_days": [3, 7], "hourly_tail_hours": [22, 23]}}


def _synthetic():
    days = pd.date_range("2019-12-20", "2020-04-02", freq="D")
    rng = np.random.default_rng(1)
    d = pd.DataFrame({"date": days, "pm2_5": rng.gamma(2, 20, len(days))})
    d["pm2_5_max"] = d["pm2_5"] * 2; d["pm2_5_n_hours"] = 24
    d["dangerous_day"] = d["pm2_5"] >= 55.5; d["exceeds_kg_limit"] = d["pm2_5"] > 35
    d["pm2_5_source"] = "x"
    hrs = pd.DataFrame({"local_date": np.repeat(days, 24), "local_hour": np.tile(range(24), len(days)),
                        "pm2_5_qc": np.repeat(d["pm2_5"].to_numpy(), 24)})
    met = pd.DataFrame({"era5_t2m_mean": rng.normal(0, 5, len(days))}, index=pd.Index(days, name="date"))
    return d, hrs, met


def test_features_only_use_past_and_target_not_imputed():
    d, hrs, met = _synthetic()
    X = features.build(d, hrs, [met], _cfg()).set_index("issue_date")
    D = pd.Timestamp("2020-02-20")
    d2 = d.copy(); d2.loc[d2["date"] > D, ["pm2_5", "pm2_5_max"]] = 1e6
    h2 = hrs.copy(); h2.loc[h2["local_date"] > D, "pm2_5_qc"] = 1e6
    m2 = met.copy(); m2.loc[m2.index > D] = 1e6
    X2 = features.build(d2, h2, [m2], _cfg()).set_index("issue_date")
    cols = features.feature_columns(X.reset_index())
    assert np.allclose(X.loc[D, cols].astype(float), X2.loc[D, cols].astype(float), equal_nan=True)
    assert X.loc[D, "y_pm2_5"] == pytest.approx(float(d.loc[d["date"] == D + pd.Timedelta(days=1), "pm2_5"].iloc[0]))


def test_split_assign_and_embargo():
    X = pd.DataFrame({"target_date": pd.date_range("2020-01-01", "2020-12-31", freq="D")})
    sp = {"train": ["2020-01-01", "2020-05-31"], "validation": ["2020-06-15", "2020-08-31"],
          "test": [["2020-09-15", "2020-10-15"], ["2020-11-15", "2020-12-31"]]}
    lab = splits.assign(X, sp, embargo_days=14)
    assert (lab == "embargo").sum() == 14 + 14
    assert lab[X["target_date"] == "2020-11-01"].iloc[0] == "excluded_window"
    with pytest.raises(AssertionError):
        splits.assign(X, sp, embargo_days=20)


def test_preprocessor_is_fit_on_train_only():
    tr = pd.DataFrame({"a": [1.0, 2.0, np.nan, 4.0]})
    va = pd.DataFrame({"a": [1000.0, np.nan]})
    p = splits.TrainOnlyPreprocessor(["a"]).fit(tr)
    assert p.median_["a"] == 2.0
    out = p.transform(va)
    assert out["a__missing"].tolist() == [0, 1]
    assert out["a"].iloc[1] == pytest.approx((2.0 - p.mean_["a"]) / p.std_["a"])
