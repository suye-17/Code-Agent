def fizzbuzz(n):
    """返回 1..n 的 FizzBuzz 序列（字符串列表）。"""
    out = []
    for i in range(1, n + 1):
        if i % 3 == 0 and i % 5 == 0:
            out.append("Fizz")  # BUG：应该是 "FizzBuzz"
        elif i % 3 == 0:
            out.append("Fizz")
        elif i % 5 == 0:
            out.append("Buzz")
        else:
            out.append(str(i))
    return out
