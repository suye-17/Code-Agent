from merge import merge_defaults


def test_overrides_win_over_defaults():
    assert merge_defaults({"timeout": 10, "retries": 1}, {"timeout": 30}) == {
        "timeout": 30,
        "retries": 1,
    }
