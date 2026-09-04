import pandas as pd
from qa import report
from qa.loaders import QAContext


def _ctx(grid):
    return QAContext(stations=pd.DataFrame(), grid=grid, grid_long=None, points=None,
        openaq={}, airnow=None, zenodo={},
        standards={"epa_aqi_unhealthy_pm25": 55.4, "kg_mpc_daily_pm25": 35.0},
        thresholds={"ranges": {"pm2_5": [0, 1000]}, "plausibility": {"fail_fraction": 0.001},
                    "completeness": {"warn_pct": 80, "fail_pct": 50}, "gap": {"warn_days": 7},
                    "cams_boundary_date": "2022-08-04", "agreement": {}, "seasonality": {}},
        reference_values={}, bishkek_cell_id="43.0000_75.0000", data_dictionary="")


def test_render_has_header_and_sections():
    grid = pd.DataFrame({"cell_id": ["43.0000_75.0000"], "lat": [43.0], "lon": [75.0],
                         "date": pd.to_datetime(["2022-09-01"]), "pm2_5": [40.0],
                         "dangerous_day": pd.array([False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([True], dtype="boolean")})
    ctx = _ctx(grid)
    fs = report.run_all(ctx)
    txt = report.render(fs, ctx, "2026-08-29")
    assert "PASS" in txt and "## structure" in txt.lower() or "structure" in txt.lower()
    assert txt.splitlines()[0].startswith("# QA report")


def test_run_all_survives_a_module_crash(monkeypatch):
    grid = pd.DataFrame({"cell_id": ["43.0000_75.0000"], "lat": [43.0], "lon": [75.0],
                         "date": pd.to_datetime(["2022-09-01"]), "pm2_5": [40.0],
                         "dangerous_day": pd.array([False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([True], dtype="boolean")})
    ctx = _ctx(grid)

    def boom(_ctx):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(report.plausibility, "run", boom)
    fs = report.run_all(ctx)
    ids = {f.check_id for f in fs}
    assert "plausibility.crashed" in ids
    crashed = next(f for f in fs if f.check_id == "plausibility.crashed")
    assert crashed.level == "FAIL" and "RuntimeError" in crashed.summary
    # the other three modules still contributed findings
    assert any(f.check_id.startswith("structure.") for f in fs)
    assert any(f.check_id.startswith("agreement.") for f in fs)
    assert any(f.check_id.startswith("reference.") for f in fs)


def test_main_returns_1_when_a_module_crashes(tmp_path, monkeypatch):
    grid = pd.DataFrame({"cell_id": ["43.0000_75.0000"], "lat": [43.0], "lon": [75.0],
                         "date": pd.to_datetime(["2022-09-01"]), "pm2_5": [40.0],
                         "dangerous_day": pd.array([False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([True], dtype="boolean")})

    def boom(_ctx):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(report, "load_context", lambda *a, **k: _ctx(grid))
    monkeypatch.setattr(report.structure, "run", boom)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "qa").mkdir()
    rc = report.main([])
    assert rc == 1


def test_main_returns_1_on_fail(tmp_path, monkeypatch):
    grid = pd.DataFrame({"cell_id": ["60.0000_75.0000"], "lat": [60.0], "lon": [75.0],
                         "date": pd.to_datetime(["2022-09-01"]), "pm2_5": [40.0],
                         "dangerous_day": pd.array([False], dtype="boolean"),
                         "exceeds_kg_limit": pd.array([True], dtype="boolean")})
    monkeypatch.setattr(report, "load_context", lambda *a, **k: _ctx(grid))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "qa").mkdir()
    rc = report.main([])
    assert rc == 1
    assert (tmp_path / "qa" / "QA_REPORT.md").exists()
