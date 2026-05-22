"""Two-file bug: caller assumes 1-indexed, callee uses 0-indexed list."""


def get_item(lst, idx):
    return lst[idx]   # 0-indexed
