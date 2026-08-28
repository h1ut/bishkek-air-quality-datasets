import json, hashlib
from pathlib import Path
import pytest
from fetch import fetch_zenodo_bishkek as fz

FIX = Path(__file__).parent / "fixtures"


def test_list_files_parses_record(monkeypatch):
    rec = json.loads((FIX / "zenodo_record.json").read_text())
    monkeypatch.setattr(fz.common, "cached_get", lambda *a, **k: rec)
    files = fz.list_files("12720883")
    assert {f["key"] for f in files} == {
        "bishkek_monitoring_us.embassy2019-2024.rar", "bishkek_camx_pm25_monthlyavg.csv"}
    assert files[0]["checksum"].startswith("md5:")


def test_download_all_verifies_checksum(monkeypatch, tmp_path):
    payload = b"hello world"
    md5 = hashlib.md5(payload).hexdigest()
    rec = {"files": [{"key": "x.csv", "size": len(payload),
                      "checksum": f"md5:{md5}",
                      "links": {"self": "https://zenodo.org/x.csv"}}]}
    monkeypatch.setattr(fz.common, "cached_get", lambda *a, **k: rec)

    class R:
        status_code = 200
        content = payload
        def raise_for_status(self): pass

    monkeypatch.setattr(fz.common.requests, "get", lambda *a, **k: R())
    dest = fz.download_all("12720883", dest=str(tmp_path))
    assert (Path(dest) / "x.csv").read_bytes() == payload
    assert "x.csv" in (Path(dest) / "manifest.md").read_text()
