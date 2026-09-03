from __future__ import annotations
import csv
from pathlib import Path

_REQUIRED_IDS = {"epa_aqi_unhealthy_pm25", "kg_mpc_daily_pm25", "kg_mpc_daily_co"}
_KINDS = {"alert", "limit"}
_COLS = ["standard_id", "authority", "pollutant", "averaging_period",
         "value_ug_m3", "kind", "citation", "url", "notes"]


def _rows(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"standards file not found: {path}")
    with p.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_standards(path="catalog/standards.csv") -> dict[str, float]:
    out: dict[str, float] = {}
    for r in _rows(path):
        out[r["standard_id"]] = float(r["value_ug_m3"])
    return out


def require(standards: dict, standard_id: str) -> float:
    try:
        return standards[standard_id]
    except KeyError:
        raise KeyError(f"standards.csv missing required id: {standard_id}") from None


def problems(path="catalog/standards.csv") -> list[str]:
    out = []
    rows = _rows(path)
    if rows and list(rows[0].keys()) != _COLS:
        out.append(f"standards.csv columns != expected: {list(rows[0].keys())}")
    ids = set()
    for r in rows:
        sid = r.get("standard_id", "?")
        if sid in ids:
            out.append(f"standards.csv: duplicate id {sid}")
        ids.add(sid)
        if r.get("kind") not in _KINDS:
            out.append(f"{sid}: bad kind {r.get('kind')!r}")
        try:
            v = float(r["value_ug_m3"])
            if v <= 0:
                out.append(f"{sid}: value_ug_m3 must be > 0")
        except (KeyError, ValueError):
            out.append(f"{sid}: value_ug_m3 not a number")
        if not (r.get("url", "").startswith("http")):
            out.append(f"{sid}: url not a URL")
        if not r.get("citation"):
            out.append(f"{sid}: empty citation")
    for req in _REQUIRED_IDS:
        if req not in ids:
            out.append(f"standards.csv: missing required id {req}")
    return out
