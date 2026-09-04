import pandas as pd
from qa.checks import Finding
from qa.checks import structure
from qa.loaders import QAContext


def _ctx(**kw):
    base = dict(stations=pd.DataFrame(), grid=pd.DataFrame(), grid_long=None,
                points=None, openaq={}, airnow=None, zenodo={},
                standards={"epa_aqi_unhealthy_pm25": 55.4, "kg_mpc_daily_pm25": 35.0},
                thresholds={}, reference_values={}, bishkek_cell_id=None,
                data_dictionary="")
    base.update(kw)
    return QAContext(**base)


def test_flag_consistency_flags_mismatch():
    grid = pd.DataFrame({"cell_id": ["a", "a"], "lat": [43.0, 43.0], "lon": [75.0, 75.0],
                         "date": pd.to_datetime(["2022-12-01", "2022-12-02"]),
                         "pm2_5": [80.0, 10.0],
                         "dangerous_day": pd.array([False, False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([True, False], dtype="boolean")})
    out = {f.check_id: f for f in structure.run(_ctx(grid=grid))}
    assert out["structure.flag_consistency"].level == "FAIL"  # 80>55.4 but dangerous_day False


def test_flag_consistency_pm25_nan_with_na_flags_passes():
    grid = pd.DataFrame({"cell_id": ["a", "a"], "lat": [43.0, 43.0], "lon": [75.0, 75.0],
                         "date": pd.to_datetime(["2022-12-01", "2022-12-02"]),
                         "pm2_5": [float("nan"), 10.0],
                         "dangerous_day": pd.array([None, False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([None, False], dtype="boolean")})
    out = {f.check_id: f for f in structure.run(_ctx(grid=grid))}
    assert out["structure.flag_consistency"].level == "PASS"


def test_flag_consistency_pm25_nan_with_flag_set_fails():
    grid = pd.DataFrame({"cell_id": ["a", "a"], "lat": [43.0, 43.0], "lon": [75.0, 75.0],
                         "date": pd.to_datetime(["2022-12-01", "2022-12-02"]),
                         "pm2_5": [float("nan"), 10.0],
                         "dangerous_day": pd.array([True, False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([None, False], dtype="boolean")})
    out = {f.check_id: f for f in structure.run(_ctx(grid=grid))}
    assert out["structure.flag_consistency"].level == "FAIL"


def test_grid_bbox_flags_out_of_range():
    grid = pd.DataFrame({"cell_id": ["x"], "lat": [60.0], "lon": [75.0],
                         "date": pd.to_datetime(["2022-12-01"]), "pm2_5": [10.0],
                         "dangerous_day": pd.array([False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([False], dtype="boolean")})
    out = {f.check_id: f for f in structure.run(_ctx(grid=grid))}
    assert out["structure.grid_bbox"].level == "FAIL"


def test_keys_unique_flags_dupes():
    grid = pd.DataFrame({"cell_id": ["a", "a"], "lat": [43.0, 43.0], "lon": [75.0, 75.0],
                         "date": pd.to_datetime(["2022-12-01", "2022-12-01"]),
                         "pm2_5": [10.0, 11.0],
                         "dangerous_day": pd.array([False, False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([False, False], dtype="boolean")})
    out = {f.check_id: f for f in structure.run(_ctx(grid=grid))}
    assert out["structure.keys_unique"].level == "FAIL"


def test_clean_grid_passes_core_checks():
    grid = pd.DataFrame({"cell_id": ["a", "a"], "lat": [43.0, 43.0], "lon": [75.0, 75.0],
                         "date": pd.to_datetime(["2022-12-01", "2022-12-02"]),
                         "pm2_5": [80.0, 10.0], "n_hours_pm2_5": [24, 24],
                         "sparse": [False, False],
                         "dangerous_day": pd.array([True, False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([True, False], dtype="boolean")})
    out = {f.check_id: f for f in structure.run(_ctx(grid=grid,
              data_dictionary="| cell_id | | | | |\n| pm2_5 | | | | |"))}
    assert out["structure.flag_consistency"].level in ("PASS", "INFO")
    assert out["structure.keys_unique"].level == "PASS"
    assert out["structure.grid_bbox"].level == "PASS"
