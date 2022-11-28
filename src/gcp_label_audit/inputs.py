"""Read resources from Cloud Asset Inventory output.

Accepted shapes:
- `gcloud asset search-all-resources --format=json`: a JSON list of
  ResourceSearchResult objects (name, assetType, project, labels, location...).
- The REST searchAllResources response: {"results": [...]}.
- Asset objects from `gcloud asset list --format=json` or an export to Cloud
  Storage (newline-delimited JSON): labels are read from resource.data.labels,
  the project from `ancestors`. camelCase and snake_case keys are both accepted.
- Any of the above as JSON lines.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class InputError(ValueError):
    pass


@dataclass
class Resource:
    name: str
    asset_type: str
    project: str
    labels: dict[str, str] = field(default_factory=dict)
    location: str = ""

    @property
    def short_name(self) -> str:
        return self.name.rstrip("/").rsplit("/", 1)[-1]


def _get(d: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d:
            return d[k]
    return default


def _project_from_ancestors(ancestors: list[str]) -> str:
    for a in ancestors or []:
        if a.startswith("projects/"):
            return a
    return ""


def to_resource(obj: Any, where: str) -> Resource:
    if not isinstance(obj, dict) or "name" not in obj:
        raise InputError(f"{where}: expected a resource object with 'name'")
    asset_type = _get(obj, "assetType", "asset_type", default="")
    if isinstance(obj.get("resource"), dict):  # Asset shape
        res = obj["resource"]
        data = res.get("data") or {}
        labels = data.get("labels")
        project = _project_from_ancestors(obj.get("ancestors", [])) or ""
        location = res.get("location", "")
    else:  # ResourceSearchResult shape
        labels = obj.get("labels")
        project = obj.get("project", "")
        location = obj.get("location", "")
    if labels is None:
        labels = {}
    if not isinstance(labels, dict):
        raise InputError(f"{where}: labels must be an object")
    return Resource(obj["name"], asset_type, project or "", {str(k): "" if v is None else str(v)
                                                             for k, v in labels.items()}, location)


def load_resources(text: str, source: str = "<input>") -> list[Resource]:
    stripped = text.strip()
    if not stripped:
        return []
    try:
        data = json.loads(stripped)
        items = data if isinstance(data, list) else data.get("results", [data]) if isinstance(data, dict) else None
        if items is None:
            raise InputError(f"{source}: expected a JSON list or object")
    except json.JSONDecodeError:
        items = []
        for n, line in enumerate(stripped.splitlines(), 1):
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise InputError(f"{source}:{n}: not valid JSON or JSON lines ({exc.msg}); "
                                 "use --format=json with gcloud") from None
    return [to_resource(o, f"{source}[{i}]") for i, o in enumerate(items)]
