import pytest

from gcp_label_audit.audit import check_resource, run_audit
from gcp_label_audit.inputs import Resource
from gcp_label_audit.policy import PolicyError, policy_from_dict

POLICY = policy_from_dict({
    "required": ["env", "owner"],
    "allowed_values": {"env": ["prod", "dev"]},
    "patterns": {"owner": "^team-"},
    "asset_types": {"storage.googleapis.com/Bucket": {"required": ["data-class"],
                                                      "allowed_values": {"env": ["prod"]}}},
    "ignore": {"name_patterns": ["/gke-"], "projects": ["projects/999"], "asset_types": ["x/Ignored"]},
})


def res(name="r1", t="compute.googleapis.com/Instance", project="projects/1", **labels):
    return Resource(name, t, project, {k.replace("_", "-"): v for k, v in labels.items()})


def codes(r, policy=POLICY):
    return sorted((v.code, v.key) for v in check_resource(r, policy))


def test_compliant():
    assert codes(res(env="prod", owner="team-a")) == []


def test_missing_and_empty():
    assert codes(res(env="")) == [("EMPTY_VALUE", "env"), ("MISSING_LABEL", "owner")]


def test_allow_empty():
    p = policy_from_dict({"required": ["env"], "allow_empty": ["env"]})
    assert codes(res(env=""), p) == []


def test_allowed_values_and_patterns():
    assert codes(res(env="production", owner="ops")) == [("PATTERN_MISMATCH", "owner"), ("VALUE_NOT_ALLOWED", "env")]


def test_per_type_rules_merge_and_override():
    b = res(t="storage.googleapis.com/Bucket", env="dev", owner="team-a")
    assert codes(b) == [("MISSING_LABEL", "data-class"), ("VALUE_NOT_ALLOWED", "env")]


def test_syntax_violations_and_too_many():
    r = Resource("r", "t", "p", {"Env": "x", "ok": "Bad Value"})
    got = codes(r, policy_from_dict({}))
    assert got == [("INVALID_KEY", "Env"), ("INVALID_VALUE", "ok")]
    many = Resource("r", "t", "p", {f"k{i}": "v" for i in range(65)})
    assert ("TOO_MANY_LABELS", "") in codes(many, policy_from_dict({}))
    assert codes(Resource("r", "t", "p", {f"k{i}": "v" for i in range(64)}), policy_from_dict({})) == []


def test_owner_recorded_on_violation():
    [v] = check_resource(res(owner="team-a"), POLICY)
    assert v.owner == "team-a" and v.project == "projects/1"


def test_ignores_dedup_and_grouping():
    rs = [res("a", env="prod", owner="team-a"), res("a", env="prod", owner="team-a"),
          res("b", owner="team-b"), res("c/gke-node"), res("d", project="projects/999"),
          res("e", t="x/Ignored"), res("f", project="projects/2")]
    result = run_audit(rs, POLICY)
    assert [r.name for r in result.checked] == ["a", "b", "f"]
    assert result.skipped == 3
    by_project = {g["project"]: g for g in result.group("project")}
    assert by_project["projects/1"] == {"project": "projects/1", "resources": 2, "non_compliant": 1, "violations": 1}
    assert by_project["projects/2"]["violations"] == 2
    owners = {g["owner"] for g in result.group("owner")}
    assert owners == {"team-a", "team-b", "(none)"}


def test_include_asset_types():
    p = policy_from_dict({"required": ["env"], "include_asset_types": ["storage.googleapis.com/Bucket"]})
    result = run_audit([res("a"), res("b", t="storage.googleapis.com/Bucket")], p)
    assert [r.name for r in result.checked] == ["b"] and result.skipped == 1


@pytest.mark.parametrize("bad", [
    {"required": "env"},
    {"required": ["Env"]},
    {"patterns": {"env": "("}},
    {"unknown_key": 1},
    {"asset_types": []},
    {"allowed_values": {"env": "prod"}},
    {"ignore": {"name_patterns": ["["]}},
    [],
])
def test_policy_errors(bad):
    with pytest.raises(PolicyError):
        policy_from_dict(bad)
