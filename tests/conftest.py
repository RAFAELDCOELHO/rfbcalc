import pytest

from rfbcalc.demo import load_fixture


@pytest.fixture(scope="session")
def official() -> dict:
    """The recorded official-motor fixture (see scripts/record_fixtures.py)."""
    return load_fixture()


@pytest.fixture(scope="session")
def cases(official: dict) -> dict:
    return official["cases"]
