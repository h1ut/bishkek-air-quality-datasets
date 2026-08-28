from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
from fetch import common

API = "https://zenodo.org/api/records"


def list_files(record_id: str = "12720883") -> list[dict]:
    body = common.cached_get(f"{API}/{record_id}", {})
    out = []
    for f in body.get("files", []):
        out.append({"key": f["key"], "size": f.get("size", 0),
                    "checksum": f.get("checksum", ""),
                    "url": f.get("links", {}).get("self", "")})
    return out


def _download(url: str) -> bytes:
    resp = common.requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def download_all(record_id="12720883", dest="data/raw/zenodo_12720883") -> str:
    d = Path(dest)
    d.mkdir(parents=True, exist_ok=True)
    lines = [f"# Zenodo {record_id} manifest", ""]
    for f in list_files(record_id):
        target = d / f["key"]
        blob = _download(f["url"])
        ok = ""
        if f["checksum"].startswith("md5:"):
            got = hashlib.md5(blob).hexdigest()
            ok = "checksum OK" if got == f["checksum"][4:] else f"CHECKSUM MISMATCH ({got})"
        target.write_bytes(blob)
        lines.append(f"- `{f['key']}` — {f['size']} bytes — {ok}")
        if f["key"].endswith(".rar"):
            lines.append(f"  - RAR: extract manually with `unrar x {target}` "
                         f"(rarfile/unrar not required by this script)")
    (d / "manifest.md").write_text("\n".join(lines), encoding="utf-8")
    return str(d)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default="12720883")
    ap.add_argument("--dest", default="data/raw/zenodo_12720883")
    args = ap.parse_args(argv)
    path = download_all(args.record, args.dest)
    print(f"[zenodo] downloaded to {path}; see manifest.md")


if __name__ == "__main__":
    main()
