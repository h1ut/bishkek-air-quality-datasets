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


def test_fetch_city_merges_multiple_sensors_single_pollutant(fake_api):
    """Test that multiple sensors reporting same pollutant merge cleanly without _x/_y suffixes."""
    cfg = {"date_start": "2021-01-01", "date_end": "2021-01-31", "openaq_api_key": "x"}
    df = fetch_openaq.fetch_city("Bishkek", 42.8746, 74.5698, cfg)
    # Verify no suffix columns from merge collision
    assert "pm2_5_x" not in df.columns
    assert "pm2_5_y" not in df.columns
    assert "n_hours_pm2_5_x" not in df.columns
    assert "n_hours_pm2_5_y" not in df.columns
    # Fixture has 2 locations with same pm25 sensor, each gets same measurements (60, 80)
    # Two sensors merged should average: (60+60)/2 = 60 for date 1, (80+80)/2 = 80 for date 2
    assert df.iloc[0]["pm2_5"] == 60.0
    assert df.iloc[1]["pm2_5"] == 80.0
    # n_hours on the /daily endpoint is coverage-derived; the fixture carries no
    # coverage field, so it is NA (combine is now "max", never a sensor count)
    assert pd.isna(df.iloc[0]["n_hours_pm2_5"])
