from lists import first


def test_first_returns_first_item():
    assert first(["a", "b", "c"]) == "a"
