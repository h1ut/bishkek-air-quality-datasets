from catalog import validate_catalog as vc


def test_catalog_is_valid():
    problems = vc.validate()
    assert problems == [], "\n".join(problems)
