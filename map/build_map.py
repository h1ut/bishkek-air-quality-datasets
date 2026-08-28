from __future__ import annotations
import argparse
import json
from pathlib import Path
import folium
import pandas as pd

GRADE_COLOR = {"A": "green", "B": "orange", "C": "red"}
COMPARISON = {"Almaty", "Tashkent", "Astana"}


def _group_for(props: dict) -> str:
    net = (props.get("network") or "").lower()
    name = props.get("name") or ""
    if any(c in name for c in COMPARISON):
        return "Comparison cities"
    if "airnow" in net or "reference" in net:
        return "Reference monitors"
    if "kyrgyzhydromet" in net:
        return "Kyrgyzhydromet sensors"
    if any(k in net for k in ("movegreen", "airkaz", "openaq", "purpleair", "clarity")):
        return "Citizen/low-cost sensors"
    return "Reference monitors"


def _popup(props: dict) -> str:
    return (f"<b>{props.get('name','')}</b><br>"
            f"operator: {props.get('operator','')}<br>"
            f"pollutants: {props.get('pollutants','')}<br>"
            f"period: {props.get('period_start','')} → {props.get('period_end','')}<br>"
            f"precision: {props.get('location_precision','')}<br>"
            f"<a href='{props.get('access_url','')}' target='_blank'>source</a>")


def build(stations_path, studies_path, grid_path=None,
          out_path="map/bishkek_air_quality_map.html",
          snapshot_var="pm2_5", snapshot_dates=None) -> str:
    m = folium.Map(location=[42.87, 74.59], zoom_start=7, tiles="cartodbpositron")
    geo = json.loads(Path(stations_path).read_text(encoding="utf-8"))

    groups = {name: folium.FeatureGroup(name=name, show=True) for name in
              ["Reference monitors", "Kyrgyzhydromet sensors", "Citizen/low-cost sensors",
               "Comparison cities", "Study & campaign sites", "Airshed extent"]}

    for f in geo.get("features", []):
        props = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        folium.CircleMarker(
            [lat, lon], radius=6, color=GRADE_COLOR.get(props.get("quality_grade"), "gray"),
            fill=True, fill_opacity=0.85, popup=folium.Popup(_popup(props), max_width=300),
        ).add_to(groups[_group_for(props)])

    studies = pd.read_csv(studies_path)
    for _, s in studies.iterrows():
        # place study markers at Bishkek unless a lat/lon column exists
        lat = s["lat"] if "lat" in studies.columns and pd.notna(s.get("lat")) else 42.87
        lon = s["lon"] if "lon" in studies.columns and pd.notna(s.get("lon")) else 74.59
        html = (f"<b>{s['citation']}</b> ({s['year']})<br>"
                f"region: {s['region']}<br>data: {s['data_made_available']}<br>"
                f"<a href='{s['doi_or_url']}' target='_blank'>{s['doi_or_url']}</a><br>"
                f"{s['relevance_notes']}")
        folium.Marker([lat, lon], icon=folium.Icon(color="blue", icon="book"),
                      popup=folium.Popup(html, max_width=340)
                      ).add_to(groups["Study & campaign sites"])

    # Airshed extent: documented bbox rectangle (replace with Zenodo polygon if parsed)
    folium.Rectangle([[42.75, 74.45], [43.00, 74.75]], color="black", weight=1,
                     dash_array="5,5", fill=False, popup="Bishkek airshed (approx bbox)"
                     ).add_to(groups["Airshed extent"])

    for g in groups.values():
        g.add_to(m)

    if grid_path and Path(grid_path).exists():
        grid = pd.read_parquet(grid_path)
        grid["date"] = pd.to_datetime(grid["date"])
        if snapshot_dates is None:
            if "dangerous_day" in grid:
                try:
                    worst = grid.groupby("date")[snapshot_var].mean().idxmax()
                    snapshot_dates = [worst]
                except (ValueError, KeyError):
                    # idxmax() raises ValueError if the series is all-NaN
                    snapshot_dates = [grid["date"].max()]
            else:
                snapshot_dates = [grid["date"].max()]
        vmax = grid[snapshot_var].quantile(0.98)
        for d in snapshot_dates:
            sub = grid[grid["date"] == pd.Timestamp(d)]
            fg = folium.FeatureGroup(name=f"CAMS grid: {snapshot_var} {pd.Timestamp(d).date()}",
                                     show=False)
            for _, r in sub.iterrows():
                val = r[snapshot_var]
                # Guard against ZeroDivisionError / NaN: if vmax is falsy or val is NaN, treat frac as 0
                if pd.isna(val) or not vmax or vmax == 0:
                    frac = 0
                else:
                    frac = min(val / vmax, 1.0)
                folium.CircleMarker(
                    [r["lat"], r["lon"]], radius=8, weight=0, fill=True,
                    fill_opacity=0.55,
                    fill_color=f"#{int(255*frac):02x}00{int(255*(1-frac)):02x}",
                    popup=f"{snapshot_var}={val:.1f} µg/m³ @ {r['cell_id']}").add_to(fg)
            fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    m.save(out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", default="catalog/stations.geojson")
    ap.add_argument("--studies", default="catalog/studies.csv")
    ap.add_argument("--grid", default="dataset/grid_daily.parquet")
    ap.add_argument("--out", default="map/bishkek_air_quality_map.html")
    args = ap.parse_args(argv)
    path = build(args.stations, args.studies,
                 grid_path=args.grid if Path(args.grid).exists() else None,
                 out_path=args.out)
    print(f"[map] wrote {path}")


if __name__ == "__main__":
    main()
