"""OpenAQ public S3 archive (``s3://openaq-data-archive``) for Bishkek.

Why not the OpenAQ v3 REST API used by ``fetch/fetch_openaq.py``: (1) it needs a key and is
not reachable from every environment; (2) that fetcher sends ``date_from``/``date_to`` to
``/sensors/{id}/measurements/daily``, a rollup endpoint that filters on
``datetime_from``/``datetime_to`` (see the official ``openaq`` Python SDK,
``validate_datetime_params``), and requests one 366-row page with no pagination, so it
returns only the *first* 366 days of each sensor's history regardless of the configured
window. The archive instead holds every hourly record as one gzip CSV per location-day:

    records/csv.gz/locationid=<id>/year=<YYYY>/month=<MM>/location-<id>-<YYYYMMDD>.csv.gz
    columns: location_id,sensors_id,location,datetime,lat,lon,parameter,units,value

``datetime`` is the END of the averaging hour in local time with an explicit UTC offset.

Locations were discovered by scanning the first file of all 55,943 archive locations
(2026-10-05) and keeping those within 30 km of central Bishkek; the list is frozen in
``LOCATIONS`` so the build is reproducible. Licence: OpenAQ CC BY 4.0; the US Embassy data
originate from AirNow / US Department of State (US Government public domain).
"""
from __future__ import annotations

import argparse
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from prep.sources import common

BUCKET = "https://openaq-data-archive.s3.amazonaws.com/"

# id: (archive name, lat, lon, first archive day) - from the 2026-10-05 discovery scan
LOCATIONS = {
    8225: ("US Diplomatic Post: Bishkek", 42.8273, 74.5833, "2019-03-09"),
    8827: ("Bishkek", 42.827626, 74.58384, "2019-10-28"),
    63914: ("Bishkek International School - Outside Playground", 42.853966, 74.580475, "2022-07-01"),
    65977: ("UN House", 42.87649, 74.59004, "2022-05-27"),
    69342: ("Kok-Jar", 42.813084, 74.65207, "2022-05-27"),
    70226: ("Orto Say, Bishkek", 42.80729, 74.59284, "2022-07-30"),
    70241: ("Imagine", 42.845196, 74.618, "2023-10-03"),
    276508: ("Ataturk Park Maldybaeva", 42.834583, 74.597824, "2022-05-31"),
    316828: ("Vostok-5 purple", 42.86848, 74.63468, "2023-10-03"),
    340802: ("Kant_1", 42.901928, 74.843666, "2022-05-31"),
    340806: ("Kant_2", 42.89017, 74.84798, "2022-05-27"),
    341184: ("Красный строитель", 42.9377, 74.58743, "2023-10-03"),
    345206: ("Ошский рынок", 42.873917, 74.57175, "2023-10-03"),
}
US_EMBASSY = 8225          # AirNow feed of the US Embassy BAM-1020 (2019-08 .. 2025-03)
US_EMBASSY_DUP = 8827      # second archive location carrying the same AirNow feed (fills 2023-11..2024-03)

DISCOVERY_CSV = Path(__file__).with_name("openaq_bishkek_locations.csv")


def discovered_locations() -> list[int]:
    """All archive locations within the Bishkek bbox (lat 42.5-43.2, lon 74.0-75.2)."""
    import csv
    with DISCOVERY_CSV.open(encoding="utf-8") as fh:
        return [int(r["location_id"]) for r in csv.DictReader(fh)]


def list_keys(location_id: int, session=None) -> list[str]:
    s = session or requests.Session()
    keys, tok = [], None
    while True:
        p = {"list-type": "2", "prefix": f"records/csv.gz/locationid={location_id}/", "max-keys": "1000"}
        if tok:
            p["continuation-token"] = tok
        t = common.get(BUCKET, session=s, params=p).text
        keys += re.findall(r"<Key>(.*?)</Key>", t)
        m = re.search(r"<NextContinuationToken>(.*?)</NextContinuationToken>", t)
        if not m:
            return keys
        tok = m.group(1)


def _day(key: str) -> str:
    d = re.search(r"-(\d{8})\.csv\.gz$", key).group(1)
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def raw_dir() -> Path:
    return common.RAW / "openaq_archive"


def download_location(location_id: int, start: str, end: str, threads: int = 16) -> int:
    s = requests.Session()
    keys = [k for k in list_keys(location_id, s) if start <= _day(k) <= end]

    def one(k):
        common.download_once(BUCKET + k, raw_dir() / k.removeprefix("records/csv.gz/"),
                             extra={"source": "openaq_archive", "location_id": location_id})
    with ThreadPoolExecutor(threads) as ex:
        list(ex.map(one, keys))
    return len(keys)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2019-09-01")
    ap.add_argument("--end", default="2026-01-02")
    ap.add_argument("--only", type=int, nargs="*", default=None)
    args = ap.parse_args(argv)
    for lid in args.only or discovered_locations():
        n = download_location(lid, args.start, args.end)
        print(f"[openaq_archive] {lid} {LOCATIONS.get(lid, ('',))[0]}: {n} day-files", flush=True)


if __name__ == "__main__":
    main()
