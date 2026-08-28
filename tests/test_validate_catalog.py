import json
from pathlib import Path

from catalog import validate_catalog as vc

SRC_HEADER = ",".join(vc.SRC_COLS)
STUDY_HEADER = ",".join(vc.STUDY_COLS)

_GOOD_STUDY_ROW = ("s1,Some Citation,2024,https://doi.org/10.1/x,Bishkek,yes,"
                   "yes,pm2_5,RF,notes")
_GOOD_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [74.6, 42.9]},
         "properties": {"station_id": "s", "location_precision": "exact",
                        "coord_source": "geocode"}},
    ],
}


def test_catalog_is_valid():
    problems = vc.validate()
    assert problems == [], "\n".join(problems)


def test_validate_flags_bad_catalog(tmp_path):
    # satellite-type source graded A with no validation caveat -> at least one problem
    bad_src = (
        "sentbad,Bad Sat,satellite,ESA,API,https://example.com/,no,Global,no2,,"
        "2018-present,daily,open,A,clean imagery,independent signal"
    )
    (tmp_path / "sources.csv").write_text(SRC_HEADER + "\n" + bad_src + "\n", encoding="utf-8")
    (tmp_path / "studies.csv").write_text(
        STUDY_HEADER + "\n" + _GOOD_STUDY_ROW + "\n", encoding="utf-8")
    (tmp_path / "stations.geojson").write_text(json.dumps(_GOOD_GEOJSON), encoding="utf-8")

    problems = vc.validate(catalog_dir=tmp_path)
    assert problems, "expected validate() to report problems for the bad catalog"
    assert any("grade A" in p for p in problems)


def test_validate_flags_short_studies_row(tmp_path):
    (tmp_path / "sources.csv").write_text(SRC_HEADER + "\n", encoding="utf-8")
    (tmp_path / "studies.csv").write_text(
        STUDY_HEADER + "\n" + "s1,only,three\n", encoding="utf-8")
    (tmp_path / "stations.geojson").write_text(json.dumps(_GOOD_GEOJSON), encoding="utf-8")

    problems = vc.validate(catalog_dir=tmp_path)
    assert any("studies.csv" in p and "columns" in p for p in problems)
