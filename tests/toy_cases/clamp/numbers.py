def clamp(value, minimum, maximum):
    if value < minimum:
        return maximum
    if value > maximum:
        return minimum
    return value
