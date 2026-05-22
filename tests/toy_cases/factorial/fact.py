def factorial(n):
    if n < 0:
        raise ValueError("negative")
    if n == 0:
        return 0  # BUG: 0! should be 1
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
