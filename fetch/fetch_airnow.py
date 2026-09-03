from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from fetch import common
from fetch.common import load_config

BASE = "https://www.airnowapi.org/aq/observation/latLong/historical/"
FALLBACK = ("[airnow] no API key. Offline fallback: run fetch_zenodo_bishkek.py "
            "and use Zenodo record 12720883 archive "
            "'bishkek_monitoring_us.embassy2019-2024'.")


def fetch_bishkek(cfg) -> pd.DataFrame:
    lat, lon = cfg["cities"]["Bishkek"]
    days = pd.date_range(cfg["date_start"], cfg["date_end"], freq="D")
    rows = []
    for day in days:
        params = {"format": "application/json", "latitude": lat, "longitude": lon,
                  "date": day.strftime("%Y-%m-%dT00-0000"), "distance": 25,
                  "API_KEY": cfg["airnow_api_key"]}
        try:
            body = common.cached_get(BASE, params)
        except Exception as e:  # noqa: BLE001
            # never interpolate the exception message: it embeds the request URL,
            # which carries API_KEY=... as a query param
            print(f"[airnow] {day.date()} failed: {type(e).__name__}")
            continue
        for rec in body:
            if rec.get("ParameterName") != "PM2.5":
                continue
            val = rec.get("Value") if str(rec.get("Unit", "")).upper() == "UG/M3" else None
            ts = f"{rec['DateObserved']}T{int(rec.get('HourObserved', 0)):02d}:00:00Z"
            rows.append({"time": ts, "pm2_5": val})
    if not rows:
        return pd.DataFrame(columns=["date", "pm2_5", "n_hours_pm2_5"])
    daily = common.to_daily(pd.DataFrame(rows), ["pm2_5"])
    return daily[["date", "pm2_5", "n_hours_pm2_5"]]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.start:
        cfg["date_start"] = args.start
    if args.end:
        cfg["date_end"] = args.end
    if not cfg.get("airnow_api_key"):
        print(FALLBACK)
        return 0
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    df = fetch_bishkek(cfg)
    # spec: quality report is always written, even on partial / empty data
    common.write_quality_report("airnow_bishkek", df, ["pm2_5"])
    if df.empty:
        return 1
    df.to_csv("data/processed/airnow_bishkek_daily.csv", index=False)
    print(f"[airnow] Bishkek: {len(df)} days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
