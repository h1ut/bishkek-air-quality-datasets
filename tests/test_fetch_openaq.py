import json, pandas as pd, pytest
from pathlib import Path
from fetch import fetch_openaq, common

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_api(monkeypatch):
    loc = json.loads((FIX / "openaq_locations.json").read_text())
    meas = json.loads((FIX / "openaq_measurements.json").read_text())

    def fake_cached_get(url, params, headers=None, **kw):
        if "/locations" in url:
            return loc
        return meas

    monkeypatch.setattr(fetch_openaq.common, "cached_get", fake_cached_get)


def test_fetch_city_returns_daily_schema(fake_api):
    cfg = {"date_start": "2021-01-01", "date_end": "2021-01-31", "openaq_api_key": "x"}
    df = fetch_openaq.fetch_city("Bishkek", 42.8746, 74.5698, cfg)
    assert {"date", "pm2_5", "n_hours_pm2_5", "city"}.issubset(df.columns)
    assert df["city"].unique().tolist() == ["Bishkek"]
    assert len(df) == 2
    assert df.iloc[0]["pm2_5"] == 60.0
