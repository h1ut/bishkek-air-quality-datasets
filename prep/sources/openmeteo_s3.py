"""ERA5 and CAMS-global point series from the Open-Meteo AWS Open Data bucket.

The Open-Meteo HTTP APIs used by ``fetch/fetch_open_meteo.py`` are rate-limited (the
original grid sweep was truncated by the daily quota) and are not reachable from every
environment. The same model data are published as ``.om`` files in the anonymous S3
bucket ``s3://openmeteo`` (https://github.com/open-meteo/open-data). Only the byte ranges
covering one grid cell are fetched, so a 7-year hourly series costs a few MB.

Layout (verified 2026-10-05 from the bucket's ``static/meta.json``):
* regular lat/lon grid, latitude ascending from -90, longitude from -180;
  ERA5 0.25° (721 x 1440), CAMS global 0.4° (451 x 900);
* ``year_YYYY.om``: hourly, starting YYYY-01-01T00Z;
* ``chunk_N.om``: hourly, starting N * chunk_time_length hours after 1970-01-01T00Z.

Raw output: ``data/raw/openmeteo_s3/<domain>/<variable>.csv.gz`` (time_utc,value) as read,
plus provenance (S3 key + ETag for every file touched) in MANIFEST.jsonl.
Licence: Open-Meteo data CC BY 4.0; ERA5 / CAMS: Copernicus licence (attribution required).
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from prep.sources import common

ERA5_VARS = ["temperature_2m", "dew_point_2m", "wind_u_component_10m", "wind_v_component_10m",
             "boundary_layer_height", "pressure_msl", "precipitation", "cloud_cover",
             "shortwave_radiation"]
CAMS_VARS = ["pm2_5", "pm10", "dust", "carbon_monoxide", "nitrogen_dioxide",
             "sulphur_dioxide", "ozone", "aerosol_optical_depth"]
DOMAINS = {"copernicus_era5": (0.25, ERA5_VARS), "cams_global": (0.4, CAMS_VARS)}


def _fs():
    import s3fs
    return s3fs.S3FileSystem(anon=True)


def cell_index(lat: float, lon: float, res: float) -> tuple[int, int]:
    return int(round((lat + 90) / res)), int(round((lon + 180) / res))


def _read_point(fs, key: str, y: int, x: int) -> np.ndarray:
    import omfiles
    r = omfiles.OmFileReader.from_fsspec(fs, key)
    a = r.read_array((slice(y, y + 1), slice(x, x + 1), slice(0, r.shape[2])))
    return np.asarray(a[0, 0, :], dtype="float64")


def extract(bucket: str, domain: str, var: str, lat: float, lon: float,
            t0: pd.Timestamp, t1: pd.Timestamp) -> tuple[pd.DataFrame, list[dict]]:
    fs = _fs()
    res, _ = DOMAINS[domain]
    y, x = cell_index(lat, lon, res)
    meta = json.loads(fs.cat(f"{bucket}/data/{domain}/static/meta.json"))
    L = int(meta["chunk_time_length"])
    files = {p.split("/")[-1]: p for p in fs.ls(f"{bucket}/data/{domain}/{var}")}
    series, prov = [], []
    covered_years = set()
    for yr in range(t0.year, t1.year + 1):
        k = f"year_{yr}.om"
        if k in files:
            v = _read_point(fs, files[k], y, x)
            idx = pd.date_range(f"{yr}-01-01", periods=len(v), freq="h", tz="UTC")
            series.append(pd.Series(v, idx)); covered_years.add(yr)
            prov.append({"key": files[k], "etag": fs.info(files[k]).get("ETag")})
    epoch_h0 = int(t0.timestamp() // 3600)
    epoch_h1 = int(t1.timestamp() // 3600)
    for n in range(epoch_h0 // L, epoch_h1 // L + 1):
        k = f"chunk_{n}.om"
        start = pd.Timestamp(n * L * 3600, unit="s", tz="UTC")
        end = start + pd.Timedelta(hours=L - 1)
        if k not in files or (start.year in covered_years and end.year in covered_years):
            continue
        v = _read_point(fs, files[k], y, x)
        series.append(pd.Series(v, pd.date_range(start, periods=len(v), freq="h")))
        prov.append({"key": files[k], "etag": fs.info(files[k]).get("ETag")})
    if not series:
        return pd.DataFrame(columns=["time_utc", "value"]), prov
    s = pd.concat(series)
    s = s[~s.index.duplicated(keep="first")].sort_index()  # year files (final ERA5) win over chunks
    s = s[(s.index >= t0) & (s.index <= t1)]
    out = s.rename("value").rename_axis("time_utc").reset_index()
    return out, prov


def raw_path(domain: str, var: str) -> Path:
    return common.RAW / "openmeteo_s3" / domain / f"{var}.csv.gz"


def run(cfg: dict) -> None:
    src = cfg["sources"]
    t0 = pd.Timestamp(cfg["study"]["period_start"], tz="UTC") - pd.Timedelta(days=20)
    t1 = pd.Timestamp(cfg["study"]["period_end"], tz="UTC") + pd.Timedelta(days=2)
    cells = {"copernicus_era5": src["era5_cell"], "cams_global": src["cams_cell"]}
    for domain, (res, varlist) in DOMAINS.items():
        c = cells[domain]
        for var in varlist:
            p = raw_path(domain, var)
            if p.exists():
                continue
            df, prov = extract(src["openmeteo_bucket"], domain, var, c["lat"], c["lon"], t0, t1)
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
                gz.write(df.to_csv(index=False).encode())
            yx = cell_index(c["lat"], c["lon"], res)
            common.write_raw(p, buf.getvalue(), url=f"s3://{src['openmeteo_bucket']}/data/{domain}/{var}/",
                             extra={"source": f"openmeteo_s3:{domain}", "variable": var,
                                    "cell_lat": c["lat"], "cell_lon": c["lon"], "grid_yx": yx,
                                    "files": prov})
            print(f"[openmeteo_s3] {domain}/{var}: {len(df)} hours, {df['value'].notna().sum()} non-null")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="prep/config.yaml")
    args = ap.parse_args(argv)
    run(yaml.safe_load(Path(args.config).read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
