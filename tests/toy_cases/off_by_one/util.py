"""跨文件 bug：调用方按 1-indexed 用，被调用方按 0-indexed 实现。"""


def get_item(lst, idx):
    return lst[idx]   # 0-indexed
