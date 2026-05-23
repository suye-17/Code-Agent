from util import get_item


def first_item(lst):
    # BUG：传入 1，期望 1-indexed，但 get_item 是 0-indexed。
    # 修这里，或者把 get_item 改成 1-indexed 都可以。
    return get_item(lst, 1)
