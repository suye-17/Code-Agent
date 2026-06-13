from ranges import overlaps


def test_detects_range_overlap():
    assert overlaps((1, 5), (4, 8)) is True
    assert overlaps((1, 2), (3, 4)) is False
