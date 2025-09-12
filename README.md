# gcp-label-audit

Check Google Cloud resources against a labeling policy using Cloud Asset Inventory output: missing, empty and invalid labels, reported by project, asset type and owner.

**Status:** v0.1. Works today, offline: reads `gcloud asset search-all-resources` JSON (and Asset-shaped list/export JSON lines), checks required keys, allowed values, regex patterns, per-asset-type rules and Google's label syntax rules, and prints table, CSV or JSON with exit codes. It never calls Google Cloud.

## Install

```bash
pip install git+https://github.com/narayana006/gcp-label-audit
```

Python 3.10+; no runtime dependencies.

## Quick start

```bash
gcloud asset search-all-resources --scope=projects/acme-prod-1234 --format=json > resources.json
gcp-label-audit resources.json --policy policy.json
```

On the bundled examples (`examples/resources.json` and `examples/policy.json`; hand-written, illustrative fixtures for fictional projects):

```text
$ gcp-label-audit examples/resources.json --policy examples/policy.json
Checked 12 resource(s), skipped 2 by policy: 6 non-compliant, 11 violation(s)

By project:
PROJECT                RESOURCES  NON-COMPLIANT  VIOLATIONS
---------------------  ---------  -------------  ----------
projects/482915370164  10         5              9
projects/907315842261  2          1              2

By asset type:
ASSET TYPE                                   RESOURCES  NON-COMPLIANT  VIOLATIONS
-------------------------------------------  ---------  -------------  ----------
compute.googleapis.com/Instance              4          2              4
storage.googleapis.com/Bucket                3          2              3
bigquery.googleapis.com/Dataset              1          1              3
sqladmin.googleapis.com/Instance             1          1              1
cloudresourcemanager.googleapis.com/Project  1          0              0
compute.googleapis.com/Disk                  1          0              0
pubsub.googleapis.com/Topic                  1          0              0

By owner:
OWNER          RESOURCES  NON-COMPLIANT  VIOLATIONS
-------------  ---------  -------------  ----------
(none)         2          2              5
data-eng       1          1              1
payments       1          1              1
team-api       2          1              2
team-web       4          1              2
platform       1          0              0
team-payments  1          0              0

Violations:
PROJECT                ASSET TYPE                        RESOURCE                                          CODE               KEY          DETAIL
---------------------  --------------------------------  ------------------------------------------------  -----------------  -----------  -----------------------------------------------------------------
projects/482915370164  bigquery.googleapis.com/Dataset   .../projects/acme-prod-1234/datasets/analytics    MISSING_LABEL      cost-center  required label 'cost-center' is missing
projects/482915370164  bigquery.googleapis.com/Dataset   .../projects/acme-prod-1234/datasets/analytics    MISSING_LABEL      env          required label 'env' is missing
projects/482915370164  bigquery.googleapis.com/Dataset   .../projects/acme-prod-1234/datasets/analytics    MISSING_LABEL      owner        required label 'owner' is missing
projects/482915370164  compute.googleapis.com/Instance   .../zones/us-central1-a/instances/web-2           PATTERN_MISMATCH   cost-center  '1042' does not match /^cc-[0-9]{4}$/
projects/482915370164  compute.googleapis.com/Instance   .../zones/us-central1-a/instances/web-2           VALUE_NOT_ALLOWED  env          'production' is not one of: prod, staging, dev
projects/482915370164  compute.googleapis.com/Instance   .../zones/us-central1-b/instances/batch-worker-7  EMPTY_VALUE        cost-center  required label 'cost-center' is empty
projects/482915370164  compute.googleapis.com/Instance   .../zones/us-central1-b/instances/batch-worker-7  MISSING_LABEL      owner        required label 'owner' is missing
projects/482915370164  sqladmin.googleapis.com/Instance  .../projects/acme-prod-1234/instances/orders-db   PATTERN_MISMATCH   owner        'payments' does not match /^(team-[a-z0-9-]+|platform|data-eng)$/
projects/482915370164  storage.googleapis.com/Bucket     //storage.googleapis.com/acme-prod-1234-exports   MISSING_LABEL      data-class   required label 'data-class' is missing
projects/907315842261  storage.googleapis.com/Bucket     //storage.googleapis.com/acme-staging-5678-tmp    MISSING_LABEL      cost-center  required label 'cost-center' is missing
projects/907315842261  storage.googleapis.com/Bucket     //storage.googleapis.com/acme-staging-5678-tmp    MISSING_LABEL      data-class   required label 'data-class' is missing
$ echo $?
1
```

The two skipped resources are a firewall rule (not in `include_asset_types`) and a GKE node (matched by `ignore.name_patterns`).

No policy file? Pass required keys directly:

```text
$ gcp-label-audit examples/resources.json --required env,owner --summary-only --group-by asset_type --no-fail
Checked 14 resource(s), skipped 0 by policy: 4 non-compliant, 7 violation(s)

By asset type:
ASSET TYPE                                   RESOURCES  NON-COMPLIANT  VIOLATIONS
-------------------------------------------  ---------  -------------  ----------
compute.googleapis.com/Instance              5          2              3
bigquery.googleapis.com/Dataset              1          1              2
compute.googleapis.com/Firewall              1          1              2
cloudresourcemanager.googleapis.com/Project  1          0              0
compute.googleapis.com/Disk                  1          0              0
pubsub.googleapis.com/Topic                  1          0              0
sqladmin.googleapis.com/Instance             1          0              0
storage.googleapis.com/Bucket                3          0              0
```

CSV for a spreadsheet (`--format csv`, one row per violation):

```text
project,asset_type,resource,owner,code,key,value,message
projects/482915370164,compute.googleapis.com/Instance,//compute.googleapis.com/projects/acme-prod-1234/zones/us-central1-a/instances/web-2,team-web,VALUE_NOT_ALLOWED,env,production,"'production' is not one of: prod, staging, dev"
projects/482915370164,compute.googleapis.com/Instance,//compute.googleapis.com/projects/acme-prod-1234/zones/us-central1-a/instances/web-2,team-web,PATTERN_MISMATCH,cost-center,1042,'1042' does not match /^cc-[0-9]{4}$/
projects/482915370164,compute.googleapis.com/Instance,//compute.googleapis.com/projects/acme-prod-1234/zones/us-central1-b/instances/batch-worker-7,(none),MISSING_LABEL,owner,,required label 'owner' is missing
...
```

## Input

| Source | Shape | Labels read from | Project read from |
| --- | --- | --- | --- |
| `gcloud asset search-all-resources --format=json` | JSON list of results | `labels` | `project` (`projects/NUMBER`) |
| REST `searchAllResources` response | `{"results": [...]}` | `labels` | `project` |
| `gcloud asset list --content-type=resource --format=json`, or an export to Cloud Storage | Asset objects (list or one per line) | `resource.data.labels` | first `projects/...` entry in `ancestors` |

Several files can be combined (duplicates by `name` are checked once); `-` or no file reads stdin. JSON lines are accepted for every shape. `asset_type` and `assetType` are both accepted.

A resource with no labels has no (or an empty) `labels` field, so a resource type that does not support labels at all looks the same as an unlabeled one. Use `include_asset_types` to audit only the types you label.

## Policy file

```json
{
  "required": ["env", "owner", "cost-center"],
  "allowed_values": {"env": ["prod", "staging", "dev"]},
  "patterns": {"cost-center": "^cc-[0-9]{4}$", "owner": "^(team-[a-z0-9-]+|platform|data-eng)$"},
  "asset_types": {
    "storage.googleapis.com/Bucket": {
      "required": ["data-class"],
      "allowed_values": {"data-class": ["public", "internal", "restricted"]}
    }
  },
  "include_asset_types": ["compute.googleapis.com/Instance", "storage.googleapis.com/Bucket"],
  "ignore": {"asset_types": [], "projects": ["projects/123456789012"], "name_patterns": ["/instances/gke-"]},
  "allow_empty": [],
  "owner_key": "owner"
}
```

- `required`: keys every checked resource must have, with a non-empty value unless listed in `allow_empty`.
- `allowed_values` / `patterns`: checked whenever the key is present and non-empty. Patterns are Python regular expressions matched with `search`, so anchor them with `^...$`.
- `asset_types`: extra rules per asset type. `required` is added to the global list; `allowed_values` and `patterns` replace the global entry for the same key.
- `include_asset_types` (optional): only these types are checked. `ignore` skips types, projects (`projects/NUMBER`, as in the input) or names matching a regex.
- `owner_key`: label used for the by-owner summary (`--owner-key` overrides it).
- Unknown keys, bad regexes and required keys that can never be valid labels are rejected.

## Checks

| Code | Meaning |
| --- | --- |
| `MISSING_LABEL` | a required key is absent |
| `EMPTY_VALUE` | a required key has an empty value |
| `VALUE_NOT_ALLOWED` | value is not in `allowed_values` |
| `PATTERN_MISMATCH` | value does not match `patterns` |
| `INVALID_KEY` | key breaks Google's label rules |
| `INVALID_VALUE` | value breaks Google's label rules |
| `TOO_MANY_LABELS` | more than 64 labels |

Label syntax rules, from the Resource Manager labels documentation: at most 64 labels per resource; keys 1-63 characters and must start with a lowercase letter or international character; values 0-63 characters; keys and values may contain only lowercase letters, numeric characters, underscores and dashes, and international (UTF-8) characters are allowed. Lengths are counted in characters here. Google Cloud rejects invalid labels when they are set, so on live exports these two checks normally find nothing; they matter for label data from other sources.

## Usage

```text
gcp-label-audit [FILE ...] [--policy policy.json] [--required k1,k2] [--owner-key KEY]
                [--format table|csv|json] [--group-by project,asset_type,owner]
                [--summary-only] [--no-fail]
```

With neither `--policy` nor `--required`, only label syntax is checked (and a note is printed to stderr). `--required` adds to the policy's global `required` list.

Exit codes: `0` no violations (or `--no-fail`), `1` violations found, `2` bad input, policy or options.

## Required permissions

The tool needs none. To produce the input: `cloudasset.assets.searchAllResources` for `gcloud asset search-all-resources`, `cloudasset.assets.listResource` for `gcloud asset list`, or `cloudasset.assets.exportResource` for an export; the Cloud Asset Viewer role (`roles/cloudasset.viewer`) covers these. Cloud Asset Inventory calls also need `serviceusage.services.use` on the project used for quota.

## Features

- [x] Required keys, empty values, allowed values and regex patterns
- [x] Per-asset-type rules, include list and ignore list (types, projects, name regex)
- [x] Google label syntax validation (characters, start character, lengths, 64-label limit)
- [x] Summaries by project, asset type and owner label; table, CSV and JSON
- [x] Reads search-all-resources output, the REST response, and Asset list/export JSON lines
- [ ] Map project numbers to project ids (search results only carry `projects/NUMBER`)
- [ ] Suggest fixes (closest allowed value) and emit `gcloud ... update --update-labels` commands, dry-run only
- [ ] Network tags and resource manager tags checks

## Limitations

- Projects are reported as `projects/NUMBER` because that is what `search-all-resources` returns.
- Exported Asset objects keep labels in `resource.data`; the tool only reads `resource.data.labels`, so a resource type that stores labels elsewhere in its data will look unlabeled.
- Labels are not the same as resource manager tags; tags are not checked.
- The tool does not know which asset types support labels. Use `include_asset_types`.
- `examples/` is hand-written and illustrative (fictional projects such as `acme-prod-1234`), not captured from a real organization.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Contributing

Issues and pull requests are welcome. If an export shape is not read correctly, please share one redacted line of it.

Built and maintained by [Narayana Vemburaj](https://github.com/narayana006).

## License

[MIT](LICENSE)
