from fizzbuzz import fizzbuzz


def test_fizzbuzz_15():
    out = fizzbuzz(15)
    assert out[0] == "1"
    assert out[2] == "Fizz"
    assert out[4] == "Buzz"
    assert out[14] == "FizzBuzz"


def test_fizzbuzz_length():
    assert len(fizzbuzz(100)) == 100
