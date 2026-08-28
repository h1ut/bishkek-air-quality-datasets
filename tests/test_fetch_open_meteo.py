# tests/test_fetch_open_meteo.py
import json, pandas as pd, pytest
from pathlib import Path
from fetch import fetch_open_meteo as fom

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_apis(monkeypatch):
    aq = json.loads((FIX / "open_meteo_aq.json").read_text())
    wx = json.loads((FIX / "open_meteo_weather.json").read_text())

    def fake_cached_get(url, params, headers=None, **kw):
        return aq if "air-quality" in url else wx

    monkeypatch.setattr(fom.common, "cached_get", fake_cached_get)


def test_fetch_point_merges_aq_and_weather(fake_apis):
    cfg = {"date_start": "2021-01-01", "date_end": "2021-01-01"}
    df = fom.fetch_point(42.87, 74.57, cfg)
    assert len(df) == 1
    assert df.iloc[0]["pm2_5"] == 60.0
    assert df.iloc[0]["pm2_5_max"] == 70.0
    assert df.iloc[0]["temperature_2m"] == -4.5
    assert df.iloc[0]["wind_direction_10m"] == pytest.approx(90.0)
    assert df.iloc[0]["lat"] == 42.87 and df.iloc[0]["lon"] == 74.57
    assert df.iloc[0]["n_hours_pm2_5"] == 2


def test_run_grid_writes_parquet(fake_apis, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/processed").mkdir(parents=True)
    cfg = {"date_start": "2021-01-01", "date_end": "2021-01-01",
           "region_bbox": {"min_lon": 74.0, "max_lon": 74.5,
                           "min_lat": 42.5, "max_lat": 43.0},
           "grid_spacing_deg": 0.5}
    fom.run_grid(cfg)
    out = pd.read_parquet(tmp_path / "data/processed/openmeteo_grid_daily.parquet")
    assert {"cell_id", "lat", "lon", "date", "pm2_5"}.issubset(out.columns)
    assert out["cell_id"].nunique() == 4   # 2x2 grid
