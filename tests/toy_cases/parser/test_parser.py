from parser import parse_key_value


def test_parse_key_value_strips_whitespace():
    assert parse_key_value(" host : localhost ") == ("host", "localhost")
