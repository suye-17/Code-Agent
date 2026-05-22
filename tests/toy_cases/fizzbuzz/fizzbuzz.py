def fizzbuzz(n):
    """Return FizzBuzz output for numbers 1..n as a list of strings."""
    out = []
    for i in range(1, n + 1):
        if i % 3 == 0 and i % 5 == 0:
            out.append("Fizz")  # BUG: should be "FizzBuzz"
        elif i % 3 == 0:
            out.append("Fizz")
        elif i % 5 == 0:
            out.append("Buzz")
        else:
            out.append(str(i))
    return out
