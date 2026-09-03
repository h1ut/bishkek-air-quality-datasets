import numpy as np, pandas as pd
from qa.checks import agreement
from qa.loaders import QAContext

TH = {"agreement": {"min_overlap_days": 5, "ground_r_warn": 0.8, "ground_bias_warn": 10.0,
                    "ground_r_fail": 0.5, "model_r_warn": 0.4}}


def _ctx(**kw):
    base = dict(stations=pd.DataFrame(), grid=pd.DataFrame(), grid_long=None, points=None,
                openaq={}, airnow=None, zenodo={}, standards={"epa_aqi_unhealthy_pm25": 55.4,
                "kg_mpc_daily_pm25": 35.0}, thresholds=TH, reference_values={},
                bishkek_cell_id="43.0000_75.0000", data_dictionary="")
    base.update(kw)
    return QAContext(**base)


def test_pair_stats_basic():
    idx = pd.date_range("2022-01-01", periods=10)
    a = pd.Series(np.arange(10.0), index=idx)
    b = pd.Series(np.arange(10.0) + 2, index=idx)
    st = agreement.pair_stats(a, b)
    assert st["n"] == 10
    assert abs(st["r"] - 1.0) < 1e-9
    assert abs(st["bias"] - (-2.0)) < 1e-9


def test_ground_pair_low_r_is_fail():
    idx = pd.date_range("2022-01-01", periods=30)
    rng = np.random.default_rng(0)
    oa = pd.DataFrame({"date": idx, "pm2_5": rng.normal(50, 10, 30)})
    an = pd.DataFrame({"date": idx, "pm2_5": rng.normal(50, 10, 30)})  # independent -> r~0
    out = {f.check_id: f for f in agreement.run(_ctx(openaq={"bishkek": oa}, airnow=an))}
    assert out["agreement.pairwise"].level == "FAIL"


def test_model_under_reads_ground_is_info():
    idx = pd.date_range("2022-01-01", periods=30)
    rng = np.random.default_rng(1)
    truth = rng.normal(60, 8, 30)
    an = pd.DataFrame({"date": idx, "pm2_5": truth})
    grid = pd.DataFrame({"cell_id": "43.0000_75.0000", "date": idx, "pm2_5": truth - 20})
    out = {f.check_id: f for f in agreement.run(_ctx(airnow=an, grid=grid))}
    assert out["agreement.pairwise"].level == "INFO"


def test_model_over_reads_ground_is_warn():
    idx = pd.date_range("2022-01-01", periods=30)
    rng = np.random.default_rng(2)
    truth = rng.normal(60, 8, 30)
    an = pd.DataFrame({"date": idx, "pm2_5": truth})
    grid = pd.DataFrame({"cell_id": "43.0000_75.0000", "date": idx, "pm2_5": truth + 20})
    out = {f.check_id: f for f in agreement.run(_ctx(airnow=an, grid=grid))}
    assert out["agreement.pairwise"].level == "WARN"


def test_exceedance_counts_present_with_single_source():
    idx = pd.date_range("2022-01-01", periods=30)
    rng = np.random.default_rng(3)
    an = pd.DataFrame({"date": idx, "pm2_5": rng.normal(50, 10, 30)})
    out = {f.check_id: f for f in agreement.run(_ctx(airnow=an))}
    assert "agreement.exceedance_counts" in out
    assert out["agreement.exceedance_counts"].level == "INFO"
    assert out["agreement.pairwise"].level == "INFO"
