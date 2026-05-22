from main import first_item


def test_first_item():
    assert first_item([10, 20, 30]) == 10
    assert first_item(["a", "b", "c"]) == "a"
