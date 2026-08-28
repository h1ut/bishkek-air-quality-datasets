import json, pandas as pd, pytest
from pathlib import Path
from fetch import fetch_airnow

FIX = Path(__file__).parent / "fixtures"


def test_fetch_bishkek_daily_mean(monkeypatch):
    obs = json.loads((FIX / "airnow_obs.json").read_text())
    monkeypatch.setattr(fetch_airnow.common, "cached_get", lambda *a, **k: obs)
    cfg = {"date_start": "2021-01-01", "date_end": "2021-01-01",
           "cities": {"Bishkek": [42.8746, 74.5698]}, "airnow_api_key": "x"}
    df = fetch_airnow.fetch_bishkek(cfg)
    assert list(df.columns) == ["date", "pm2_5", "n_hours_pm2_5"]
    assert df.iloc[0]["pm2_5"] == pytest.approx(62.7)
    assert df.iloc[0]["n_hours_pm2_5"] == 2


def test_missing_key_exits_clean(monkeypatch, capsys):
    cfg = {"date_start": "2021-01-01", "date_end": "2021-01-01",
           "cities": {"Bishkek": [42.8746, 74.5698]}, "airnow_api_key": ""}
    monkeypatch.setattr(fetch_airnow, "load_config", lambda *_: cfg)
    rc = fetch_airnow.main([])
    assert rc == 0
    assert "12720883" in capsys.readouterr().out
