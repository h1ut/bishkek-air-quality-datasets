from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import requests
from fetch import common

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WX_URL = "https://archive-api.open-meteo.com/v1/archive"
AQ_VARS = ["pm2_5", "pm10", "carbon_monoxide", "nitrogen_dioxide",
           "sulphur_dioxide", "ozone", "aerosol_optical_depth", "dust"]
WX_VARS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
           "wind_direction_10m", "surface_pressure", "boundary_layer_height"]


def _get(url, params):
    """common.cached_get, but a transport/HTTP failure (e.g. Open-Meteo 429 while
    walking a large grid) is logged and downgraded to an empty body so the caller
    skips that point and the batch continues — same intent as the brief's
    ``error: true`` handling, which only covers JSON error payloads."""
    try:
        return common.cached_get(url, params)
    except (requests.exceptions.RequestException, ValueError) as exc:
        print(f"[open-meteo] request failed for {url}: {exc}")
        return {}


def _hourly_frame(body, varlist):
    h = body.get("hourly")
    if not h or body.get("error"):
        if body.get("error"):
            print(f"[open-meteo] error: {body.get('reason')}")
        return pd.DataFrame(columns=["time"] + varlist)
    df = pd.DataFrame({"time": h["time"]})
    for v in varlist:
        df[v] = h.get(v)
    return df


def fetch_point(lat, lon, cfg) -> pd.DataFrame:
    base = {"latitude": lat, "longitude": lon, "start_date": cfg["date_start"],
            "end_date": cfg["date_end"], "timezone": "UTC"}
    aq = _hourly_frame(_get(
        AQ_URL, {**base, "hourly": ",".join(AQ_VARS), "domains": "cams_global"}), AQ_VARS)
    wx = _hourly_frame(_get(
        WX_URL, {**base, "hourly": ",".join(WX_VARS)}), WX_VARS)
    daily = []
    if not aq.empty:
        daily.append(common.to_daily(aq, AQ_VARS))
    if not wx.empty:
        daily.append(common.to_daily(wx, WX_VARS))
    if not daily:
        return pd.DataFrame()
    # Controller ruling: merge the AQ and WX daily frames on `date` only.
    # `sparse` is a per-date OR of both sources (sparse if either was sparse);
    # never merge on `sparse` or it splits dates into duplicate half-empty rows.
    sparse_by_date = (pd.concat([f[["date", "sparse"]] for f in daily], ignore_index=True)
                      .groupby("date", as_index=False)["sparse"].any())
    out = daily[0].drop(columns=["sparse"])
    for f in daily[1:]:
        out = out.merge(f.drop(columns=["sparse"]), on="date",
                        how="outer", suffixes=("", "_dup"))
    out = out.loc[:, ~out.columns.str.endswith("_dup")]
    out = out.merge(sparse_by_date, on="date", how="left")
    out["lat"], out["lon"] = lat, lon
    return out.sort_values("date").reset_index(drop=True)


def _dedup_points(cfg):
    pts = [(f"city:{n}", lat, lon) for n, (lat, lon) in cfg["cities"].items()]
    staging = Path("data/processed/_stations_staging.csv")
    if staging.exists():
        s = pd.read_csv(staging).dropna(subset=["lat", "lon"])
        for _, r in s.iterrows():
            pts.append((f"station:{r['station_id']}", float(r["lat"]), float(r["lon"])))
    seen, out = set(), []
    for site, lat, lon in pts:
        key = (round(lat, 3), round(lon, 3))
        if key in seen:
            continue
        seen.add(key)
        out.append((site, lat, lon))
    return out


def run_points(cfg) -> pd.DataFrame:
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    frames = []
    for site, lat, lon in _dedup_points(cfg):
        df = fetch_point(lat, lon, cfg)
        if df.empty:
            print(f"[open-meteo] {site}: no data")
            continue
        df["site"] = site
        frames.append(df)
        print(f"[open-meteo] {site}: {len(df)} days")
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_csv("data/processed/openmeteo_points_daily.csv", index=False)
    if not out.empty:
        common.write_quality_report("openmeteo_points", out, AQ_VARS + WX_VARS)
    return out


def run_grid(cfg) -> None:
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    cells = common.build_grid(cfg["region_bbox"], cfg["grid_spacing_deg"])
    frames = []
    for i, c in enumerate(cells, 1):
        df = fetch_point(c["lat"], c["lon"], cfg)
        if df.empty:
            continue
        df["cell_id"] = c["cell_id"]
        frames.append(df)
        if i % 25 == 0:
            print(f"[open-meteo grid] {i}/{len(cells)} cells")
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_parquet("data/processed/openmeteo_grid_daily.parquet", index=False)
    if not out.empty:
        common.write_quality_report("openmeteo_grid", out, AQ_VARS + WX_VARS)
    print(f"[open-meteo grid] wrote {len(out)} rows from {len(frames)} cells")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["points", "grid"], required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--grid-spacing", type=float, default=None)
    args = ap.parse_args(argv)
    cfg = common.load_config(args.config)
    if args.grid_spacing:
        cfg["grid_spacing_deg"] = args.grid_spacing
    if args.mode == "points":
        run_points(cfg)
    else:
        run_grid(cfg)


if __name__ == "__main__":
    main()
