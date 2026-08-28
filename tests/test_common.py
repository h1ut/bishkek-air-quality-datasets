# tests/test_common.py
import math
import json
import pandas as pd
import pytest
from fetch import common


def test_build_grid_corners_and_count():
    bbox = {"min_lon": 66.0, "max_lon": 68.0, "min_lat": 39.0, "max_lat": 40.0}
    grid = common.build_grid(bbox, spacing=1.0)
    coords = {(c["lat"], c["lon"]) for c in grid}
    assert (39.0, 66.0) in coords
    assert (40.0, 68.0) in coords
    assert len(grid) == 3 * 2  # lats 39,40 ; lons 66,67,68
    assert grid[0]["cell_id"] == "39.0000_66.0000"


def test_build_grid_ids_unique():
    bbox = {"min_lon": 66.0, "max_lon": 80.0, "min_lat": 39.0, "max_lat": 52.0}
    grid = common.build_grid(bbox, spacing=0.5)
    assert len({c["cell_id"] for c in grid}) == len(grid)


def _hourly_frame(hours, value):
    idx = pd.date_range("2021-01-01", periods=hours, freq="h", tz="UTC")
    return pd.DataFrame({"time": idx, "pm2_5": [value] * hours,
                         "wind_direction_10m": [90.0] * hours})


def test_to_daily_flags_sparse_day():
    df = _hourly_frame(10, 20.0)          # only 10 of 24 hours
    out = common.to_daily(df, ["pm2_5", "wind_direction_10m"])
    assert len(out) == 1
    assert out.iloc[0]["n_hours_pm2_5"] == 10
    assert out.iloc[0]["pm2_5_max"] == 20.0


def test_to_daily_full_day_mean():
    df = _hourly_frame(24, 30.0)
    out = common.to_daily(df, ["pm2_5", "wind_direction_10m"])
    assert out.iloc[0]["pm2_5"] == 30.0
    assert out.iloc[0]["n_hours_pm2_5"] == 24


def test_to_daily_wind_direction_is_vector_mean():
    idx = pd.date_range("2021-01-01", periods=2, freq="h", tz="UTC")
    df = pd.DataFrame({"time": idx, "wind_direction_10m": [0.0, 180.0]})
    out = common.to_daily(df, ["wind_direction_10m"])
    # opposite directions cancel → undefined; implementation returns NaN, not 90
    assert pd.isna(out.iloc[0]["wind_direction_10m"])


def test_cached_get_uses_cache(tmp_path, monkeypatch):
    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        def json(self): return {"ok": True}
        def raise_for_status(self): pass

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        return FakeResp()

    monkeypatch.setattr(common.requests, "get", fake_get)
    for _ in range(3):
        out = common.cached_get("https://x/y", {"a": 1}, cache_dir=str(tmp_path))
    assert out == {"ok": True}
    assert calls["n"] == 1  # network hit once, then cache


def test_cached_get_retries_on_429(tmp_path, monkeypatch):
    seq = [429, 429, 200]

    class FakeResp:
        def __init__(self, code): self.status_code = code
        def json(self): return {"tries": "done"}
        def raise_for_status(self): pass

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResp(seq.pop(0))

    monkeypatch.setattr(common.requests, "get", fake_get)
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    out = common.cached_get("https://x/z", {}, cache_dir=str(tmp_path))
    assert out == {"tries": "done"}


def test_quality_report_counts_implausible(tmp_path):
    df = pd.DataFrame({
        "date": pd.date_range("2021-01-01", periods=3),
        "pm2_5": [10.0, -5.0, 3000.0],
        "n_hours_pm2_5": [24, 24, 5],
    })
    path = common.write_quality_report("demo", df, ["pm2_5"], out_dir=str(tmp_path))
    text = pd.io.common.get_handle(path, "r").handle.read()
    assert "implausible" in text.lower()
    assert "2" in text  # -5 and 3000 both implausible
