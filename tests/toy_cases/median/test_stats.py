from stats import median


def test_median_handles_even_and_odd_lengths():
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 2, 3]) == 2.5
