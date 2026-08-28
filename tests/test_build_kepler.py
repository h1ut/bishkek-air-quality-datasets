import json, pandas as pd
from pathlib import Path
from kepler import build_kepler


def test_stations_to_csv_flat(tmp_path):
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [74.59, 42.90]},
         "properties": {"station_id": "a", "name": "US Embassy", "network": "AirNow",
           "operator": "EPA", "pollutants": "pm2_5", "period_start": "2019",
           "period_end": "now", "location_precision": "approx", "coord_source": "x",
           "access_url": "https://x", "quality_grade": "A", "notes": ""}}]}
    p = tmp_path / "s.geojson"
    p.write_text(json.dumps(geo))
    out = build_kepler.stations_to_csv(str(p), str(tmp_path / "k.csv"))
    df = pd.read_csv(out)
    assert list(df.columns) == ["name", "latitude", "longitude", "network",
        "operator", "pollutants", "period_start", "period_end", "quality_grade"]
    assert df.iloc[0]["latitude"] == 42.90 and df.iloc[0]["longitude"] == 74.59
