def overlaps(left, right):
    return left[1] < right[0] or right[1] < left[0]
