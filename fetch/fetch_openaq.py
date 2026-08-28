from __future__ import annotations
import argparse
import sys
from pathlib import Path
import pandas as pd
from fetch import common

BASE = "https://api.openaq.org/v3"
PARAM_MAP = {"pm25": "pm2_5", "pm10": "pm10", "so2": "sulphur_dioxide",
             "no2": "nitrogen_dioxide", "co": "carbon_monoxide", "o3": "ozone",
             "relativehumidity": "relative_humidity", "temperature": "temperature"}
STAGING = "data/processed/_stations_staging.csv"


def _record_hours(rec):
    """Coverage-derived hour count for a /measurements/daily record, or pd.NA.

    On the daily endpoint a record already represents a whole day, so the
    "≥18 of 24 hours" rule cannot be applied from a raw row count. Use the
    API's own coverage/expectedCount if present; otherwise NA (unknown).
    """
    cov = rec.get("coverage") or {}
    for k in ("observedCount", "expectedCount", "observed_count", "expected_count"):
        if cov.get(k) is not None:
            return cov[k]
    for k in ("expectedCount", "expected_count"):
        if rec.get(k) is not None:
            return rec[k]
    return pd.NA


def _sensor_daily(sensor_id, cfg, headers):
    url = f"{BASE}/sensors/{sensor_id}/measurements/daily"
    params = {"date_from": cfg["date_start"], "date_to": cfg["date_end"], "limit": 366}
    daily_path = True
    try:
        body = common.cached_get(url, params, headers=headers)
    except Exception:
        daily_path = False
        url = f"{BASE}/sensors/{sensor_id}/measurements"
        # separate params: the hourly endpoint needs a far larger page size than
        # the 366-row daily cap, or a multi-year sweep is silently truncated
        fb_params = {"date_from": cfg["date_start"], "date_to": cfg["date_end"], "limit": 1000}
        body = common.cached_get(url, fb_params, headers=headers)
        print(f"[openaq] sensor {sensor_id}: /daily unavailable, used /measurements fallback")
    rows = []
    for r in body.get("results", []):
        ts = (r.get("period", {}).get("datetimeFrom", {}) or {}).get("utc")
        row = {"time": ts, "value": r.get("value")}
        if daily_path:
            row["n_hours"] = _record_hours(r)
        rows.append(row)
    return pd.DataFrame(rows)


def fetch_city(city, lat, lon, cfg) -> pd.DataFrame:
    headers = {"X-API-Key": cfg.get("openaq_api_key", "")}
    loc_body = common.cached_get(f"{BASE}/locations",
                                 {"coordinates": f"{lat},{lon}", "radius": 25000, "limit": 1000},
                                 headers=headers)
    frames, station_rows = [], []
    for loc in loc_body.get("results", []):
        params_present = []
        for sensor in loc.get("sensors", []):
            raw = sensor.get("parameter", {}).get("name")
            canon = PARAM_MAP.get(raw)
            if not canon:
                continue
            sdf = _sensor_daily(sensor["id"], cfg, headers)
            if sdf.empty:
                continue
            sdf = sdf.rename(columns={"value": canon})
            daily = common.to_daily(sdf, [canon])
            if "n_hours" in sdf.columns:
                # daily endpoint: n_hours_<var> is NA / coverage-derived, not a
                # real hour count — overwrite to_daily's fabricated "1 row = 1 hour"
                key = pd.to_datetime(sdf["time"], utc=True).dt.tz_localize(None).dt.normalize()
                cov = dict(zip(key, sdf["n_hours"]))
                daily[f"n_hours_{canon}"] = daily["date"].map(cov)
            frames.append(daily[["date", canon, f"n_hours_{canon}"]])
            params_present.append(canon)
        c = loc.get("coordinates", {})
        station_rows.append({
            "station_id": f"openaq-{loc.get('id')}", "name": loc.get("name"),
            "network": f"OpenAQ:{loc.get('provider', {}).get('name', 'unknown')}",
            "operator": loc.get("provider", {}).get("name", "unknown"),
            "lat": c.get("latitude"), "lon": c.get("longitude"),
            "pollutants": "|".join(sorted(params_present)),
            "period_start": (loc.get("datetimeFirst") or {}).get("utc", ""),
            "period_end": (loc.get("datetimeLast") or {}).get("utc", ""),
            "location_precision": "exact", "coord_source": "OpenAQ /locations",
            "access_url": f"https://explore.openaq.org/locations/{loc.get('id')}"})
    if not frames:
        out = pd.DataFrame(columns=["date", "city"])
    else:
        # Group frames by pollutant name to handle multiple sensors per pollutant
        frames_by_pollutant = {}
        for frame in frames:
            # Extract pollutant name (exclude date and n_hours_* columns)
            pollutants = [c for c in frame.columns if c != "date" and not c.startswith("n_hours_")]
            for poll in pollutants:
                if poll not in frames_by_pollutant:
                    frames_by_pollutant[poll] = []
                frames_by_pollutant[poll].append(frame[["date", poll, f"n_hours_{poll}"]])

        # Combine frames for the same pollutant
        combined_frames = []
        for pollutant in sorted(frames_by_pollutant.keys()):
            poll_frames = frames_by_pollutant[pollutant]
            if len(poll_frames) == 1:
                combined_frames.append(poll_frames[0])
            else:
                # Concatenate all frames for this pollutant and aggregate by date
                combined = pd.concat(poll_frames, ignore_index=False)
                combined = combined.groupby("date", as_index=False).agg({
                    pollutant: "mean",
                    # "max" not "sum": summing hour counts across co-located sensors
                    # produced a sensor count, not an hours-of-day figure
                    f"n_hours_{pollutant}": "max"
                })
                combined_frames.append(combined)

        # Outer merge all pollutant frames
        out = combined_frames[0]
        for f in combined_frames[1:]:
            out = out.merge(f, on="date", how="outer")
        out = out.sort_values("date").reset_index(drop=True)
    out["city"] = city
    fetch_city._stations = station_rows  # picked up by main()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    cfg = common.load_config(args.config)
    if not cfg.get("openaq_api_key"):
        print("[openaq] no API key. Set OPENAQ_API_KEY (register free at "
              "https://explore.openaq.org/register). A missing key is not a failure.")
        return 0
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    all_stations = []
    cities_succeeded = 0
    for city, (lat, lon) in cfg["cities"].items():
        try:
            df = fetch_city(city, lat, lon, cfg)
        except Exception as e:  # noqa: BLE001
            print(f"[openaq] {city} FAILED: {e}")
            continue
        df.to_csv(f"data/processed/openaq_{city.lower()}_daily.csv", index=False)
        value_cols = [c for c in df.columns if c not in ("date", "city") and not c.startswith("n_hours_")]
        common.write_quality_report(f"openaq_{city.lower()}", df, value_cols)
        all_stations.extend(getattr(fetch_city, "_stations", []))
        print(f"[openaq] {city}: {len(df)} days, params {value_cols}")
        cities_succeeded += 1
    if all_stations:
        sdf = pd.DataFrame(all_stations).drop_duplicates("station_id")
        p = Path(STAGING)
        if p.exists():
            sdf = pd.concat([pd.read_csv(p), sdf]).drop_duplicates("station_id")
        sdf.to_csv(p, index=False)
    # Exit non-zero only if every city failed
    if cities_succeeded == 0 and len(cfg["cities"]) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
