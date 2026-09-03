# tests/test_build_dataset.py
import pandas as pd, pytest
from pathlib import Path
from fetch import build_dataset as bd

FIX = Path(__file__).parent / "fixtures" / "proc"


def test_build_stations_prefers_airnow_for_bishkek():
    df = bd.build_stations(str(FIX))
    b = df[(df["station_key"] == "bishkek_us_embassy") & (df["date"] == "2021-01-01")]
    assert b.iloc[0]["pm2_5"] == 58.0
    assert b.iloc[0]["pm2_5_source"] == "airnow"


def test_grid_flags(tmp_path):
    g = pd.DataFrame({"cell_id": ["a", "a"], "lat": [42.5, 42.5], "lon": [74.0, 74.0],
                      "date": pd.to_datetime(["2021-01-01", "2021-01-02"]),
                      "pm2_5": [40.0, 70.0], "n_hours_pm2_5": [24, 24]})
    (tmp_path / "openmeteo_grid_daily.parquet").write_bytes(b"")  # placeholder
    g.to_parquet(tmp_path / "openmeteo_grid_daily.parquet", index=False)
    out = bd.build_grid_dataset(str(tmp_path))
    assert out.set_index("date").loc["2021-01-02", "dangerous_day"] == True
    assert out.set_index("date").loc["2021-01-01", "dangerous_day"] == False
    assert out.set_index("date").loc["2021-01-01", "exceeds_kg_limit"] == True


def test_grid_flags_na_when_pm2_5_missing(tmp_path):
    g = pd.DataFrame({"cell_id": ["a", "a"], "lat": [42.5, 42.5], "lon": [74.0, 74.0],
                      "date": pd.to_datetime(["2021-01-01", "2021-01-02"]),
                      "pm2_5": [float("nan"), 70.0], "n_hours_pm2_5": [0, 24]})
    g.to_parquet(tmp_path / "openmeteo_grid_daily.parquet", index=False)
    out = bd.build_grid_dataset(str(tmp_path)).set_index("date")
    assert pd.isna(out.loc["2021-01-01", "dangerous_day"])
    assert pd.isna(out.loc["2021-01-01", "exceeds_kg_limit"])
    assert out.loc["2021-01-02", "dangerous_day"] == True
    # .sum() on a nullable boolean Series skips NA and must not raise
    assert out["dangerous_day"].sum() == 1


def test_to_long_shape():
    g = pd.DataFrame({"cell_id": ["a"], "lat": [1.0], "lon": [2.0],
                      "date": pd.to_datetime(["2021-01-01"]),
                      "pm2_5": [40.0], "pm10": [50.0], "n_hours_pm2_5": [24]})
    long = bd.to_long(g)
    assert set(long["variable"]) == {"pm2_5", "pm10"}
    assert len(long) == 2


def test_grid_flags_use_standards_not_literals(tmp_path):
    g = pd.DataFrame({"cell_id": ["a", "a", "a"], "lat": [43.0]*3, "lon": [75.0]*3,
                      "date": pd.to_datetime(["2022-08-04", "2022-08-05", "2022-08-06"]),
                      "pm2_5": [30.0, 40.0, None], "n_hours_pm2_5": [24, 24, 0]})
    g.to_parquet(tmp_path / "openmeteo_grid_daily.parquet", index=False)
    fake_std = {"epa_aqi_unhealthy_pm25": 55.4, "kg_mpc_daily_pm25": 35.0}
    out = bd.build_grid_dataset(str(tmp_path), standards=fake_std).set_index("date")
    assert out.loc["2022-08-04", "exceeds_kg_limit"] == False
    assert out.loc["2022-08-05", "exceeds_kg_limit"] == True
    assert out.loc["2022-08-05", "dangerous_day"] == False
    assert pd.isna(out.loc["2022-08-06", "exceeds_kg_limit"])


def test_build_stations_gets_nullable_flags():
    df = bd.build_stations(str(FIX), standards={"epa_aqi_unhealthy_pm25": 55.4,
                                                "kg_mpc_daily_pm25": 35.0})
    assert "dangerous_day" in df.columns and "exceeds_kg_limit" in df.columns
    b = df[df["station_key"] == "bishkek_us_embassy"].set_index("date")
    # fixture airnow row for 2021-01-02 is 120.0 -> both flags True
    assert b.loc["2021-01-02", "dangerous_day"] == True


def test_build_grid_raises_when_standard_id_missing(tmp_path):
    g = pd.DataFrame({"cell_id": ["a"], "lat": [43.0], "lon": [75.0],
                      "date": pd.to_datetime(["2022-08-04"]), "pm2_5": [30.0]})
    g.to_parquet(tmp_path / "openmeteo_grid_daily.parquet", index=False)
    with pytest.raises(KeyError):
        bd.build_grid_dataset(str(tmp_path), standards={"kg_mpc_daily_pm25": 35.0})
