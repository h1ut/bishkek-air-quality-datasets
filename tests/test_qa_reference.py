import numpy as np, pandas as pd
from qa.checks import reference
from qa.loaders import QAContext

REF = {"bishkek_annual_pm25": {"low": 30, "high": 70, "cite": "x"},
       "isaev_table4_exceed35": {"low": 52, "high": 93, "cite": "Isaev T4"}}
TH = {"seasonality": {"min_winter_summer_ratio": 2.0}, "agreement": {}}


def _ctx(**kw):
    base = dict(stations=pd.DataFrame(), grid=pd.DataFrame(), grid_long=None, points=None,
                openaq={}, airnow=None, zenodo={}, standards={"epa_aqi_unhealthy_pm25": 55.4,
                "kg_mpc_daily_pm25": 35.0}, thresholds=TH, reference_values=REF,
                bishkek_cell_id="43.0000_75.0000", data_dictionary="")
    base.update(kw)
    return QAContext(**base)


def test_heating_season_boundary():
    assert reference.heating_season(pd.Timestamp("2022-12-15")) == 2022
    assert reference.heating_season(pd.Timestamp("2023-02-15")) == 2022
    assert reference.heating_season(pd.Timestamp("2023-08-15")) == 2023


def test_annual_mean_out_of_band_warns():
    idx = pd.date_range("2023-01-01", "2023-12-31")
    an = pd.DataFrame({"date": idx, "pm2_5": [200.0] * len(idx)})  # mean 200 -> above high 70
    out = {f.check_id: f for f in reference.run(_ctx(airnow=an))}
    assert out["reference.annual_mean"].level == "WARN"


def test_seasonal_cycle_ground_flat_is_fail():
    idx = pd.date_range("2022-07-01", "2023-06-30")
    an = pd.DataFrame({"date": idx, "pm2_5": [40.0] * len(idx)})  # flat -> ratio 1.0
    out = {f.check_id: f for f in reference.run(_ctx(airnow=an))}
    assert out["reference.seasonal_cycle"].level == "FAIL"


def test_annual_mean_in_band_is_info():
    idx = pd.date_range("2023-01-01", "2023-12-31")
    an = pd.DataFrame({"date": idx, "pm2_5": [50.0] * len(idx)})  # mean 50 -> inside [30,70]
    out = {f.check_id: f for f in reference.run(_ctx(airnow=an))}
    assert out["reference.annual_mean"].level == "INFO"


def test_exceedance_days_in_range_is_info():
    # one heating season (Nov 2022 - Mar 2023) with a plausible in-range count of days >35
    idx = pd.date_range("2022-11-01", "2023-03-31")
    vals = [80.0 if i % 2 == 0 else 20.0 for i in range(len(idx))]  # ~half of ~151 days -> ~75, inside 52-93
    an = pd.DataFrame({"date": idx, "pm2_5": vals})
    out = {f.check_id: f for f in reference.run(_ctx(airnow=an))}
    assert out["reference.exceedance_days"].level == "INFO"


def test_best_ground_series_skips_short_airnow_for_long_openaq():
    ai_idx = pd.date_range("2024-01-01", periods=20)
    an = pd.DataFrame({"date": ai_idx, "pm2_5": [30.0] * 20})
    oa_idx = pd.date_range("2022-01-01", periods=400)
    oa = pd.DataFrame({"date": oa_idx, "pm2_5": [25.0] * 400})
    name, series = reference.best_ground_series(
        _ctx(airnow=an, openaq={"openaq_bishkek": oa}))
    assert name == "openaq"
    assert int(series.notna().sum()) == 400


def test_seasonal_cycle_no_series_no_grid_is_info():
    out = {f.check_id: f for f in reference.run(_ctx())}  # no airnow, empty grid
    assert out["reference.seasonal_cycle"].level == "INFO"
