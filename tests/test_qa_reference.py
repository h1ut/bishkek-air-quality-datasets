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
