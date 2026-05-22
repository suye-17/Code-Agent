from strings import is_palindrome, reverse_string


def test_reverse():
    assert reverse_string("hello") == "olleh"
    assert reverse_string("abc") == "cba"


def test_palindrome():
    assert is_palindrome("racecar")
    assert is_palindrome("level")
    assert not is_palindrome("hello")
