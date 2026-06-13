def merge_defaults(defaults, overrides):
    result = dict(overrides)
    result.update(defaults)
    return result
