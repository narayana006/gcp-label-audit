import pytest

from gcp_label_audit.syntax import key_problem, value_problem


@pytest.mark.parametrize("key", ["env", "cost-center", "team_name", "a1", "a" * 63, "équipe", "環境"])
def test_valid_keys(key):
    assert key_problem(key) is None


@pytest.mark.parametrize("key,why", [
    ("", "empty"),
    ("a" * 64, "64 characters"),
    ("Env", "must start"),
    ("1env", "must start"),
    ("_env", "must start"),
    ("-env", "must start"),
    ("costCenter", "not allowed"),
    ("cost.center", "not allowed"),
    ("cost center", "not allowed"),
    ("Équipe", "must start"),
])
def test_invalid_keys(key, why):
    assert why in key_problem(key)


@pytest.mark.parametrize("value", ["", "prod", "cc-1042", "1", "_x", "-x", "a" * 63, "größe"])
def test_valid_values(value):
    assert value_problem(value) is None


@pytest.mark.parametrize("value", ["Prod", "a" * 64, "a/b", "a.b", "a b", "x@example.com", "GRÖSSE"])
def test_invalid_values(value):
    assert value_problem(value) is not None
