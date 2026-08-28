from __future__ import annotations
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
URL_RE = re.compile(r"^https?://")
SRC_COLS = ["source_id", "name", "type", "operator", "access_method",
            "endpoint_or_url", "auth_required", "spatial_coverage", "pollutants",
            "met_variables", "temporal_coverage", "temporal_resolution",
            "license", "quality_grade", "quality_notes", "ml_relevance"]
MODEL_TYPES = {"satellite", "reanalysis", "model_output"}


def validate() -> list[str]:
    problems: list[str] = []
    with open(HERE / "sources.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if rows and list(rows[0].keys()) != SRC_COLS:
        problems.append(f"sources.csv columns != expected: {list(rows[0].keys())}")
    for r in rows:
        sid = r.get("source_id", "?")
        if r.get("quality_grade") not in {"A", "B", "C"}:
            problems.append(f"{sid}: bad quality_grade {r.get('quality_grade')!r}")
        if not URL_RE.match(r.get("endpoint_or_url", "")):
            problems.append(f"{sid}: endpoint_or_url not a URL")
        if r.get("type") in MODEL_TYPES:
            if r.get("quality_grade") == "A":
                problems.append(f"{sid}: model/satellite source must not be grade A")
            note = r.get("quality_notes", "").lower()
            if "needs ground validation" not in note and "column" not in note:
                problems.append(f"{sid}: model/satellite source missing validation caveat")
    with open(HERE / "studies.csv", encoding="utf-8") as fh:
        srows = list(csv.DictReader(fh))
    for s in srows:
        if not URL_RE.match(s.get("doi_or_url", "")):
            problems.append(f"study {s.get('study_id')}: doi_or_url not a URL")
    geo = json.loads((HERE / "stations.geojson").read_text(encoding="utf-8"))
    if geo.get("type") != "FeatureCollection":
        problems.append("stations.geojson: not a FeatureCollection")
    for f in geo.get("features", []):
        p = f.get("properties", {})
        sid = p.get("station_id", "?")
        if p.get("location_precision") not in {"exact", "approx", "city-centroid"}:
            problems.append(f"{sid}: bad location_precision")
        if not p.get("coord_source"):
            problems.append(f"{sid}: empty coord_source")
        g = f.get("geometry", {})
        if g.get("type") != "Point" or len(g.get("coordinates", [])) != 2:
            problems.append(f"{sid}: geometry not a 2-coord Point")
    return problems


def main():
    problems = validate()
    for p in problems:
        print("PROBLEM:", p)
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
