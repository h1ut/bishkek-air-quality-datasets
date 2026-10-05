"""Run the whole preparation pipeline in order.

    python -m prep.run_all            # use raw files already in data/raw (hash-verified)
    python -m prep.run_all --fetch    # first download any missing raw files (idempotent)
"""
from __future__ import annotations

import argparse
import sys

from prep import audit, baseline, build, checks, compare, dictionary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    args = ap.parse_args(argv)
    if args.fetch:
        from prep.sources import isd, openaq_archive, openmeteo_s3
        openaq_archive.main([])
        isd.main([])
        openmeteo_s3.main([])
    build.main([])
    audit.main()
    rc = checks.main()
    baseline.main()
    compare.main()
    dictionary.main()
    return rc


if __name__ == "__main__":
    sys.exit(main())
