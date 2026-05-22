def reverse_string(s):
    # BUG: only reverses first half
    half = len(s) // 2
    return s[:half][::-1] + s[half:]


def is_palindrome(s):
    return s == reverse_string(s)
