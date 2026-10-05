"""Shared helpers for raw-data acquisition.

Raw files are written once, byte-for-byte as served, under ``data/raw/<source>/``
and are never modified afterwards. Every download is recorded in
``data/raw/MANIFEST.jsonl`` (url, local path, size, sha256, retrieval time) so a
later run can prove it used the same inputs.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

RAW = Path("data/raw")
MANIFEST = RAW / "MANIFEST.jsonl"
_LOCK = threading.Lock()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _record(url: str, path: Path, blob: bytes, extra: dict | None = None) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    rec = {"url": url, "path": str(path), "bytes": len(blob), "sha256": sha256_bytes(blob),
           "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if extra:
        rec.update(extra)
    with _LOCK, MANIFEST.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def get(url: str, session: requests.Session | None = None, params=None, timeout=60,
        retries=4) -> requests.Response:
    s = session or requests
    delay = 2
    for attempt in range(retries):
        try:
            r = s.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay); delay *= 2; continue
            r.raise_for_status()
        except requests.exceptions.ConnectionError:
            if attempt == retries - 1:
                raise
            time.sleep(delay); delay *= 2
    raise RuntimeError(f"GET {url} failed")


def download_once(url: str, dest: Path, session=None, extra: dict | None = None) -> Path:
    """Download ``url`` to ``dest`` unless it already exists (raw files are immutable)."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    blob = get(url, session=session).content
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(blob)
    tmp.replace(dest)
    _record(url, dest, blob, extra)
    return dest


def write_raw(path: Path, blob: bytes, url: str, extra: dict | None = None) -> Path:
    """Persist an extracted raw blob (e.g. a point series cut from a 5 GB remote file)."""
    path = Path(path)
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    _record(url, path, blob, extra)
    return path
