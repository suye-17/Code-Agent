from config import get_timeout


def test_get_timeout_uses_default_when_missing():
    assert get_timeout({}) == 30
    assert get_timeout({"timeout": 10}) == 10
