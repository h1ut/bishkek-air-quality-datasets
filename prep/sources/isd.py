"""NOAA Integrated Surface Database (ISD / global-hourly) for Bishkek.

Raw: yearly station CSVs from the AWS Open Data mirror
``s3://noaa-global-hourly-pds/<year>/<station>.csv`` (anonymous HTTPS), saved unchanged.
Parsed: hourly UTC observations of measured surface weather, with ISD quality codes applied.

Why this source: ERA5 is a 0.25° reanalysis published with ~5 days latency, so it is not
strictly available at forecast issue time, and its cell elevation differs from the city.
ISD SYNOP/METAR reports are *measured* at Bishkek / Manas airport and are distributed in
near-real time over the WMO GTS, so day-D values are legitimately known at issue time.
Visibility and present-weather codes (haze/smoke/fog) are independent aerosol proxies.

Licence note: ISD is distributed by NOAA NCEI without charge; data from non-US WMO members
may carry WMO Resolution 40 restrictions on commercial redistribution. Raw files are
therefore NOT committed; they are re-downloadable and hash-verified via MANIFEST.jsonl.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from prep.sources import common

BAD_QC = {"2", "3", "6", "7"}  # ISD: suspect / erroneous


def raw_path(station: str, year: int) -> Path:
    return common.RAW / "isd" / station / f"{year}.csv"


def download(station: str, years, bucket: str) -> list[Path]:
    out = []
    for y in years:
        url = f"{bucket}{y}/{station}.csv"
        try:
            out.append(common.download_once(url, raw_path(station, y),
                                            extra={"source": "noaa_isd", "station": station}))
        except Exception as e:  # noqa: BLE001
            print(f"[isd] {station} {y}: {type(e).__name__}: {e}")
    return out


def _field(s: pd.Series, idx: int, missing: str) -> pd.Series:
    parts = s.fillna("").str.split(",", expand=True)
    if idx >= parts.shape[1]:
        return pd.Series(np.nan, index=s.index)
    v = parts[idx]
    return v.where(v != missing)


def _val_qc(s: pd.Series, vidx: int, qidx: int, missing: str, scale: float) -> pd.Series:
    v = pd.to_numeric(_field(s, vidx, missing), errors="coerce") / scale
    q = _field(s, qidx, "")
    return v.mask(q.isin(BAD_QC))


def parse_station(station: str, years) -> pd.DataFrame:
    frames = []
    for y in years:
        p = raw_path(station, y)
        if p.exists():
            frames.append(pd.read_csv(p, dtype=str, low_memory=False))
    if not frames:
        return pd.DataFrame()
    d = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame({"time_utc": pd.to_datetime(d["DATE"], utc=True)})
    out["report_type"] = d["REPORT_TYPE"].str.strip()
    out["temp_c"] = _val_qc(d["TMP"], 0, 1, "+9999", 10)
    out["dewpoint_c"] = _val_qc(d["DEW"], 0, 1, "+9999", 10)
    out["slp_hpa"] = _val_qc(d["SLP"], 0, 1, "99999", 10)
    wdir = _val_qc(d["WND"], 0, 1, "999", 1)
    wtype = _field(d["WND"], 2, "9")
    wspd = _val_qc(d["WND"], 3, 4, "9999", 10)
    calm = wtype.eq("C") | wspd.eq(0)
    out["wind_speed_ms"] = wspd
    out["wind_dir_deg"] = wdir.mask(calm | wtype.eq("V"))
    out["visibility_m"] = _val_qc(d["VIS"], 0, 1, "999999", 1)
    # present weather (manual MW1 or automated AW1): WMO 4677 codes 04 smoke, 05 haze,
    # 10 mist, 40-49 fog. Missing column means not reported, not "no phenomenon".
    mw = d["MW1"].fillna("").str.split(",").str[0] if "MW1" in d else pd.Series("", index=d.index)
    out["wx_code"] = pd.to_numeric(mw.replace("", np.nan), errors="coerce")
    # report types: keep the routine reports, drop specials (FM-16 SPECI) to avoid double counts
    out = out[out["report_type"].isin(["FM-12", "FM-15"])]
    out = out.sort_values("time_utc").drop_duplicates("time_utc", keep="first")
    out["station"] = station
    return out.reset_index(drop=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="prep/config.yaml")
    args = ap.parse_args(argv)
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    y0 = int(cfg["study"]["period_start"][:4])
    y1 = int(cfg["study"]["period_end"][:4])
    for name, st in cfg["sources"]["isd_stations"].items():
        files = download(st, range(y0, y1 + 1), cfg["sources"]["isd_bucket"])
        print(f"[isd] {name} {st}: {len(files)} yearly files")


if __name__ == "__main__":
    main()
