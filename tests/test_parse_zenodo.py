import pandas as pd
from pathlib import Path
from fetch import parse_zenodo_bishkek as pz


def test_parse_us_embassy_from_csv(tmp_path):
    raw = tmp_path / "zenodo_12720883"
    raw.mkdir()
    pd.DataFrame({
        "datetime": pd.date_range("2020-01-01", periods=48, freq="h"),
        "PM2.5": [50.0] * 24 + [70.0] * 24,
    }).to_csv(raw / "bishkek_monitoring_us_embassy.csv", index=False)
    out = pz.parse_us_embassy(str(raw))
    assert list(out.columns) == ["date", "pm2_5", "n_hours_pm2_5"]
    assert len(out) == 2
    assert out.iloc[0]["pm2_5"] == 50.0 and out.iloc[0]["n_hours_pm2_5"] == 24


def test_find_extractor_is_str_or_none():
    assert pz.find_extractor() is None or isinstance(pz.find_extractor(), str)


def test_parse_missing_returns_empty(tmp_path):
    assert pz.parse_us_embassy(str(tmp_path)).empty
    assert pz.parse_clarity(str(tmp_path)).empty
