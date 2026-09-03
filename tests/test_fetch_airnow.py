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


def test_start_end_override(monkeypatch, tmp_path):
    from fetch import fetch_airnow
    seen = {}
    def fake_fetch(cfg):
        import pandas as pd
        seen["range"] = (cfg["date_start"], cfg["date_end"])
        return pd.DataFrame({"date": ["2025-01-01"], "pm2_5": [10.0], "n_hours_pm2_5": [24]})
    monkeypatch.setattr(fetch_airnow, "fetch_bishkek", fake_fetch)
    monkeypatch.setattr(fetch_airnow, "load_config",
                        lambda *_: {"airnow_api_key": "x", "date_start": "2021-01-01",
                                    "date_end": "2025-12-31", "cities": {"Bishkek": [42.8746, 74.5698]}})
    monkeypatch.chdir(tmp_path); (tmp_path / "data" / "processed").mkdir(parents=True)
    fetch_airnow.main(["--start", "2025-01-01", "--end", "2025-12-31"])
    assert seen["range"] == ("2025-01-01", "2025-12-31")
