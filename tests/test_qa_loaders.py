import pandas as pd
from qa import geo
from qa.loaders import load_context, AQ_VARS, WX_VARS


def test_nearest_cell_id_picks_closest():
    g = pd.DataFrame({"cell_id": ["43.0000_75.0000", "39.0000_66.0000"],
                      "lat": [43.0, 39.0], "lon": [75.0, 66.0]})
    assert geo.nearest_cell_id(g) == "43.0000_75.0000"


def test_var_lists_match_build_dataset():
    from fetch.build_dataset import AQ_VARS as A2, WX_VARS as W2
    assert AQ_VARS == A2 and WX_VARS == W2


def test_load_context_tolerates_missing_inputs(tmp_path):
    ctx = load_context(dataset_dir=str(tmp_path), proc_dir=str(tmp_path),
                       qa_dir="qa", kepler_dir=str(tmp_path))
    assert ctx.grid.empty and ctx.stations.empty
    assert ctx.standards["epa_aqi_unhealthy_pm25"] == 55.4
    assert ctx.thresholds["completeness"]["warn_pct"] == 80
    assert ctx.reference_values["isaev_table4_exceed35"]["low"] == 52
