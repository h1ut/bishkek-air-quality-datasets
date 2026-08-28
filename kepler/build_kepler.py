from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd

COLS = ["name", "latitude", "longitude", "network", "operator", "pollutants",
        "period_start", "period_end", "quality_grade"]


def stations_to_csv(geojson_path, out_path="kepler/stations_kepler.csv") -> str:
    geo = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    rows = []
    for f in geo.get("features", []):
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        rows.append({"name": p.get("name"), "latitude": lat, "longitude": lon,
                     "network": p.get("network"), "operator": p.get("operator"),
                     "pollutants": p.get("pollutants"),
                     "period_start": p.get("period_start"),
                     "period_end": p.get("period_end"),
                     "quality_grade": p.get("quality_grade")})
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=COLS).to_csv(out_path, index=False)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", default="catalog/stations.geojson")
    ap.add_argument("--out", default="kepler/stations_kepler.csv")
    args = ap.parse_args(argv)
    print(f"[kepler] wrote {stations_to_csv(args.stations, args.out)}")


if __name__ == "__main__":
    main()
