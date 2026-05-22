from util import get_item


def first_item(lst):
    # BUG: passes 1, expecting 1-indexed, but get_item is 0-indexed.
    # Either fix here OR make get_item 1-indexed.
    return get_item(lst, 1)
