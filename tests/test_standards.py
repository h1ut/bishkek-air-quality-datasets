import pytest
from catalog import standards as S


def test_load_standards_has_the_two_headline_ids():
    std = S.load_standards()
    assert std["epa_aqi_unhealthy_pm25"] == 55.4
    assert std["kg_mpc_daily_pm25"] == 35.0
    assert isinstance(std["kg_mpc_daily_co"], float) and std["kg_mpc_daily_co"] == 3000.0


def test_require_raises_named_error_for_missing_id():
    std = S.load_standards()
    with pytest.raises(KeyError) as e:
        S.require(std, "who_aqg_pm25")
    assert "who_aqg_pm25" in str(e.value)


def test_load_standards_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        S.load_standards("catalog/does_not_exist.csv")


def test_validate_catalog_still_passes_with_standards():
    from catalog import validate_catalog as vc
    assert vc.validate() == []
