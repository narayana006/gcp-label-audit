# gcp-label-audit

Check Google Cloud resources against a labeling policy using a Cloud Asset Inventory export: missing, empty or invalid labels by project and type.

## Planned scope

Input: Cloud Asset Inventory export (JSON lines from `gcloud asset search-all-resources --format=json` or export to GCS), where labels are present. Policy file: required keys, allowed values/regex, per asset type rules, ignore list; also validate GCP label syntax rules (lowercase, length, allowed chars — verify the exact rules in Google docs). Report by project, asset type and owner label; CSV/JSON/table; exit codes.
