import json

import pytest

from gcp_label_audit.inputs import InputError, load_resources

SEARCH = {"name": "//storage.googleapis.com/b1", "assetType": "storage.googleapis.com/Bucket",
          "project": "projects/111", "labels": {"env": "prod"}, "location": "us"}


def test_search_all_resources_list():
    [r] = load_resources(json.dumps([SEARCH]))
    assert (r.asset_type, r.project, r.labels, r.location) == (
        "storage.googleapis.com/Bucket", "projects/111", {"env": "prod"}, "us")
    assert r.short_name == "b1"


def test_rest_response_and_jsonl():
    assert len(load_resources(json.dumps({"results": [SEARCH, SEARCH]}))) == 2
    jsonl = json.dumps(SEARCH) + "\n\n" + json.dumps(SEARCH) + "\n"
    assert len(load_resources(jsonl)) == 2


def test_missing_labels_is_empty_dict_and_null_value():
    [r] = load_resources(json.dumps([{"name": "x", "assetType": "t"}]))
    assert r.labels == {} and r.project == ""
    [r] = load_resources(json.dumps([{"name": "x", "labels": {"k": None}}]))
    assert r.labels == {"k": ""}


@pytest.mark.parametrize("key", ["assetType", "asset_type"])
def test_asset_shape(key):
    asset = {"name": "//compute.googleapis.com/projects/p/zones/z/instances/i", key: "compute.googleapis.com/Instance",
             "ancestors": ["projects/222", "folders/3", "organizations/4"],
             "resource": {"data": {"labels": {"env": "dev"}, "name": "i"}, "location": "z"}}
    [r] = load_resources(json.dumps(asset) + "\n")
    assert (r.asset_type, r.project, r.labels, r.location) == (
        "compute.googleapis.com/Instance", "projects/222", {"env": "dev"}, "z")


def test_empty_input():
    assert load_resources("  \n") == []


@pytest.mark.parametrize("text", ["name: x", '{"a": 1}\nnot json', "[1]", '"str"', '[{"name": "x", "labels": []}]'])
def test_bad_input(text):
    with pytest.raises(InputError):
        load_resources(text)
