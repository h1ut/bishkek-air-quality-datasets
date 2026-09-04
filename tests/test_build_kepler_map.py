import json
import pandas as pd
from kepler import build_kepler_map
from kepler.build_kepler_map import GRID_COLS, STATION_COLS, SENSOR_COLS


def _fixtures(tmp_path):
    days = pd.to_datetime(["2022-08-04", "2022-08-05"])
    rows = []
    for cid, lat, lon in (("a", 42.0, 74.0), ("b", 43.0, 75.0)):
        for d in days:
            rows.append({"cell_id": cid, "lat": lat, "lon": lon, "date": d,
                         "pm2_5": 12.0, "pm10": 20.0, "ozone": 30.0, "dust": 5.0,
                         "carbon_monoxide": 100.0, "nitrogen_dioxide": 4.0,
                         "sulphur_dioxide": 2.0, "aerosol_optical_depth": 0.1,
                         "temperature_2m": 25.0, "relative_humidity_2m": 40.0,
                         "wind_speed_10m": 3.0, "wind_direction_10m": 180.0,
                         "surface_pressure": 900.0, "boundary_layer_height": 800.0,
                         "pm2_5_max": 20.0, "n_hours_pm2_5": 24,
                         "dangerous_day": False, "exceeds_kg_limit": False})
    pd.DataFrame(rows).to_parquet(tmp_path / "grid_daily.parquet")

    pd.DataFrame({
        "station_key": ["bishkek", "bishkek", "almaty"],
        "city": ["Bishkek", "Bishkek", "Almaty"],
        "date": pd.to_datetime(["2022-08-04", "2022-08-05", "2022-08-04"]),
        "pm2_5": [40.0, None, 15.0], "pm10": [None, None, 22.0],
        "ozone": [10.0, 11.0, 12.0], "temperature": [25.0, 26.0, 27.0],
        "relative_humidity": [30.0, 31.0, 32.0],
        "dangerous_day": [False, None, False],
        "exceeds_kg_limit": [True, None, False],
    }).to_csv(tmp_path / "stations_daily.csv", index=False)

    pd.DataFrame({
        "station_id": ["s1", "s2", "s3"],
        "name": ["Sensor One", "Sensor Two", "Far Away"],
        "network": ["OpenAQ:Clarity", "OpenAQ:AirGradient", "OpenAQ:Other"],
        "operator": ["Clarity", "AirGradient", "X"],
        "lat": [42.9, 43.2, 10.0], "lon": [74.6, 76.9, 10.0],
        "pollutants": ["pm2_5", "pm2_5;pm10", "pm2_5"],
        "period_start": ["2021", "2021", "2021"],
        "period_end": ["2025", "2025", "2025"],
        "access_url": ["http://a", "http://b", "http://c"],
    }).to_csv(tmp_path / "_stations_staging.csv", index=False)


def test_build_kepler_map_writes_expected_outputs(tmp_path):
    _fixtures(tmp_path)
    rc = build_kepler_map.main(["--dataset-dir", str(tmp_path),
                                "--proc-dir", str(tmp_path),
                                "--out-dir", str(tmp_path)])
    assert rc == 0

    grid = pd.read_csv(tmp_path / "ca_air_quality_grid.csv")
    assert list(grid.columns) == GRID_COLS
    assert "pm2_5_max" not in grid.columns and "n_hours_pm2_5" not in grid.columns
    assert grid["date"].iloc[0] == "2022-08-04"

    stn = pd.read_csv(tmp_path / "ca_air_quality_stations.csv")
    assert list(stn.columns) == STATION_COLS
    # bishkek row 2 (both pm2_5 & pm10 null) dropped -> 2 rows remain
    assert len(stn) == 2
    assert set(stn["lat"]) == {42.8746, 43.238}

    sen = pd.read_csv(tmp_path / "ca_air_quality_sensors.csv")
    assert list(sen.columns) == SENSOR_COLS
    assert len(sen) == 2  # the lat/lon 10,10 sensor is outside the CA bbox

    cfg = json.loads((tmp_path / "kepler_config.json").read_text(encoding="utf-8"))
    assert len(cfg["config"]["visState"]["layers"]) == 3
    assert len(cfg["config"]["visState"]["filters"]) == 2

    styling = json.loads((tmp_path / "ca_air_quality_styling.json").read_text(encoding="utf-8"))
    assert [d["data"]["id"] for d in styling["datasets"]] == [
        "ca_air_quality_stations", "ca_air_quality_sensors"]
