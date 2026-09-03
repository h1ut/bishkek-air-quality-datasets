import pandas as pd
from qa.checks import plausibility
from qa.loaders import QAContext

TH = {"completeness": {"warn_pct": 80, "fail_pct": 50}, "gap": {"warn_days": 7},
      "plausibility": {"fail_fraction": 0.001},
      "ranges": {"pm2_5": [0, 1000], "relative_humidity_2m": [0, 100]},
      "cams_boundary_date": "2022-08-04"}


def _ctx(**kw):
    base = dict(stations=pd.DataFrame(), grid=pd.DataFrame(), grid_long=None, points=None,
                openaq={}, airnow=None, zenodo={}, standards={}, thresholds=TH,
                reference_values={}, bishkek_cell_id="43.0000_75.0000", data_dictionary="")
    base.update(kw)
    return QAContext(**base)


def test_ranges_flag_negative_pm25():
    grid = pd.DataFrame({"cell_id": ["a"] * 4, "lat": [43.0] * 4, "lon": [75.0] * 4,
                         "date": pd.to_datetime(["2022-08-04", "2022-08-05", "2022-08-06", "2022-08-07"]),
                         "pm2_5": [10.0, -5.0, 20.0, 3000.0]})
    out = {f.check_id: f for f in plausibility.run(_ctx(grid=grid))}
    assert out["plausibility.ranges_grid"].level == "FAIL"  # 2 of 4 = 50% > 0.1%


def test_cams_boundary_flags_gas_before_start():
    grid = pd.DataFrame({"cell_id": ["43.0000_75.0000"] * 2, "lat": [43.0] * 2, "lon": [75.0] * 2,
                         "date": pd.to_datetime(["2021-01-01", "2022-09-01"]),
                         "pm2_5": [12.0, 40.0], "sulphur_dioxide": [3.0, 5.0]})
    out = {f.check_id: f for f in plausibility.run(_ctx(grid=grid))}
    assert out["plausibility.cams_boundary"].level == "FAIL"  # pm2_5 present 2021 (pre-boundary)


def test_completeness_reports_low_season_as_warn():
    days = pd.date_range("2022-11-01", "2023-03-31", freq="D")
    grid = pd.DataFrame({"cell_id": ["43.0000_75.0000"] * len(days),
                         "lat": [43.0] * len(days), "lon": [75.0] * len(days),
                         "date": days,
                         "pm2_5": [10.0] * 20 + [None] * (len(days) - 20)})
    out = {f.check_id: f for f in plausibility.run(_ctx(grid=grid))}
    assert out["plausibility.completeness"].level in ("WARN", "FAIL")
    assert out["plausibility.completeness"].table is not None


def test_duplicate_keys_stations_flags_dupe_pair():
    stations = pd.DataFrame({
        "station_key": ["s1", "s1", "s2"],
        "date": pd.to_datetime(["2022-08-04", "2022-08-04", "2022-08-04"]),
        "pm2_5": [10.0, 11.0, 12.0],
    })
    out = {f.check_id: f for f in plausibility.run(_ctx(stations=stations))}
    assert out["plausibility.duplicate_keys_stations"].level == "FAIL"


def test_duplicate_keys_stations_clean_frame_passes():
    stations = pd.DataFrame({
        "station_key": ["s1", "s1", "s2"],
        "date": pd.to_datetime(["2022-08-04", "2022-08-05", "2022-08-04"]),
        "pm2_5": [10.0, 11.0, 12.0],
    })
    out = {f.check_id: f for f in plausibility.run(_ctx(stations=stations))}
    assert out["plausibility.duplicate_keys_stations"].level == "PASS"
