from csv_utils import split_csv


def test_split_csv_trims_cells():
    assert split_csv("a, b, c") == ["a", "b", "c"]
