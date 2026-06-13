from numbers import clamp


def test_clamp_bounds():
    assert clamp(-1, 0, 10) == 0
    assert clamp(12, 0, 10) == 10
    assert clamp(5, 0, 10) == 5
