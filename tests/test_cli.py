import csv
import io
import json
import pathlib

from gcp_label_audit.cli import main

EX = pathlib.Path(__file__).resolve().parent.parent / "examples"
RES, POL = str(EX / "resources.json"), str(EX / "policy.json")


def test_example_table(capsys):
    rc = main([RES, "--policy", POL])
    out = capsys.readouterr().out
    assert rc == 1
    assert "Checked 12 resource(s), skipped 2 by policy: 6 non-compliant, 11 violation(s)" in out
    assert "By asset type:" in out and "By owner:" in out
    assert "'production' is not one of: prod, staging, dev" in out
    assert "gke-staging-pool" not in out  # ignored by name pattern


def test_example_json(capsys):
    main([RES, "--policy", POL, "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert data["checked"] == 12 and data["skipped"] == 2 and data["non_compliant"] == 6
    assert {g["asset_type"] for g in data["by_asset_type"]} >= {"storage.googleapis.com/Bucket"}


def test_example_csv(capsys):
    main([RES, "--policy", POL, "--format", "csv"])
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert len(rows) == 11
    assert set(rows[0]) == {"project", "asset_type", "resource", "owner", "code", "key", "value", "message"}


def test_required_flag_without_policy_and_no_fail(capsys):
    rc = main([RES, "--required", "env", "--no-fail", "--summary-only", "--group-by", "project"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Violations:" not in out and "By owner" not in out
    # without a policy: dataset, firewall rule and GKE node lack env
    assert "3 non-compliant" in out


def test_syntax_only_mode(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO('[{"name": "x", "labels": {"env": "prod"}}]'))
    assert main([]) == 0
    assert "checking label syntax only" in capsys.readouterr().err


def test_owner_key_override(capsys):
    main([RES, "--policy", POL, "--owner-key", "env", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert {g["owner"] for g in data["by_owner"]} >= {"prod", "staging"}


def test_errors(capsys, tmp_path):
    assert main([RES, "--group-by", "region"]) == 2
    assert main([str(tmp_path / "missing.json")]) == 2
    assert main([RES, "--required", "Env"]) == 2
    bad = tmp_path / "p.json"
    bad.write_text("{not json")
    assert main([RES, "--policy", str(bad)]) == 2
