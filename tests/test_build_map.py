import json, pandas as pd
from pathlib import Path
from map import build_map


def _mini_catalog(tmp_path):
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [74.59, 42.90]},
         "properties": {"station_id": "a", "name": "US Embassy", "network": "AirNow",
           "operator": "EPA", "pollutants": "pm2_5", "period_start": "2019", "period_end": "now",
           "location_precision": "approx", "access_url": "https://x", "coord_source": "geocode",
           "quality_grade": "A", "notes": ""}}]}
    (tmp_path / "stations.geojson").write_text(json.dumps(geo))
    pd.DataFrame([{"study_id": "s1", "citation": "C", "year": 2024,
                   "doi_or_url": "https://doi.org/x", "region": "Bishkek",
                   "open_access": "yes", "data_made_available": "yes",
                   "variables": "pm2_5", "method": "RF", "relevance_notes": "n"}]
                 ).to_csv(tmp_path / "studies.csv", index=False)
    return tmp_path / "stations.geojson", tmp_path / "studies.csv"


def test_build_writes_html_with_layers(tmp_path):
    sp, stp = _mini_catalog(tmp_path)
    out = build_map.build(str(sp), str(stp), out_path=str(tmp_path / "m.html"))
    html = Path(out).read_text(encoding="utf-8")
    assert "Reference monitors" in html
    # Folium 0.20 encodes & as & in JavaScript layer control strings
    assert ("Study &amp; campaign sites" in html or "Study & campaign sites" in html
            or "Study \\u0026 campaign sites" in html)
    assert "LayerControl" in html or "layer_control" in html or "leaflet-control-layers" in html


def test_snapshot_prefers_heating_season_worst(tmp_path):
    import pandas as pd, json
    from map import build_map
    # a huge summer dust day and a moderate winter day
    grid = pd.DataFrame({
        "cell_id": ["43.0000_75.0000", "43.0000_75.0000"],
        "lat": [43.0, 43.0], "lon": [75.0, 75.0],
        "date": pd.to_datetime(["2023-05-15", "2023-01-15"]),
        "pm2_5": [900.0, 120.0],
        "dangerous_day": pd.array([True, True], dtype="boolean"),
        "exceeds_kg_limit": pd.array([True, True], dtype="boolean")})
    gp = tmp_path / "grid.parquet"; grid.to_parquet(gp, index=False)
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [74.59, 42.90]},
         "properties": {"station_id": "a", "name": "US Embassy", "network": "AirNow",
           "operator": "EPA", "pollutants": "pm2_5", "period_start": "2019", "period_end": "now",
           "location_precision": "approx", "access_url": "https://x", "coord_source": "geo",
           "quality_grade": "A", "notes": ""}}]}
    sp = tmp_path / "s.geojson"; sp.write_text(json.dumps(geo))
    stp = tmp_path / "st.csv"; stp.write_text("study_id,citation,year,doi_or_url,region,open_access,data_made_available,variables,method,relevance_notes\n")
    out = build_map.build(str(sp), str(stp), grid_path=str(gp), out_path=str(tmp_path / "m.html"))
    html = open(out, encoding="utf-8").read()
    assert "2023-01-15" in html and "2023-05-15" not in html
