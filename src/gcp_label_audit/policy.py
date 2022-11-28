"""Labeling policy: required keys, allowed values, regex patterns, per-type rules, ignores.

Example (JSON):

{
  "required": ["env", "owner", "cost-center"],
  "allowed_values": {"env": ["prod", "staging", "dev"]},
  "patterns": {"cost-center": "^cc-[0-9]{4}$"},
  "asset_types": {
    "storage.googleapis.com/Bucket": {"required": ["data-class"],
                                      "allowed_values": {"data-class": ["public", "internal", "restricted"]}}
  },
  "include_asset_types": ["compute.googleapis.com/Instance", "storage.googleapis.com/Bucket"],
  "ignore": {"asset_types": [], "projects": ["projects/123"], "name_patterns": ["/instances/gke-"]},
  "owner_key": "owner"
}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .syntax import key_problem

KNOWN_KEYS = {"required", "allowed_values", "patterns", "asset_types", "include_asset_types", "ignore",
              "owner_key", "allow_empty"}


class PolicyError(ValueError):
    pass


@dataclass
class Rules:
    required: list[str] = field(default_factory=list)
    allowed_values: dict[str, list[str]] = field(default_factory=dict)
    patterns: dict[str, re.Pattern] = field(default_factory=dict)
    allow_empty: list[str] = field(default_factory=list)


@dataclass
class Policy:
    base: Rules = field(default_factory=Rules)
    per_type: dict[str, Rules] = field(default_factory=dict)
    include_asset_types: list[str] = field(default_factory=list)
    ignore_asset_types: list[str] = field(default_factory=list)
    ignore_projects: list[str] = field(default_factory=list)
    ignore_name_patterns: list[re.Pattern] = field(default_factory=list)
    owner_key: str = "owner"

    def rules_for(self, asset_type: str) -> Rules:
        extra = self.per_type.get(asset_type)
        if not extra:
            return self.base
        required = list(dict.fromkeys(self.base.required + extra.required))
        return Rules(
            required=required,
            allowed_values={**self.base.allowed_values, **extra.allowed_values},
            patterns={**self.base.patterns, **extra.patterns},
            allow_empty=list(dict.fromkeys(self.base.allow_empty + extra.allow_empty)),
        )

    def is_ignored(self, name: str, asset_type: str, project: str) -> bool:
        if self.include_asset_types and asset_type not in self.include_asset_types:
            return True
        if asset_type in self.ignore_asset_types or project in self.ignore_projects:
            return True
        return any(p.search(name) for p in self.ignore_name_patterns)


def _str_list(v, what: str) -> list[str]:
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise PolicyError(f"{what} must be a list of strings")
    return list(v)


def _compile(p: str, what: str) -> re.Pattern:
    try:
        return re.compile(p)
    except re.error as exc:
        raise PolicyError(f"{what}: invalid regex {p!r} ({exc})") from None


def _rules(d: dict, where: str) -> Rules:
    if not isinstance(d, dict):
        raise PolicyError(f"{where} must be an object")
    required = _str_list(d.get("required"), f"{where}.required")
    for k in required:
        problem = key_problem(k)
        if problem:
            raise PolicyError(f"{where}.required: {k!r} can never be a valid label key ({problem})")
    allowed = d.get("allowed_values", {})
    if not isinstance(allowed, dict):
        raise PolicyError(f"{where}.allowed_values must be an object")
    patterns = d.get("patterns", {})
    if not isinstance(patterns, dict):
        raise PolicyError(f"{where}.patterns must be an object")
    return Rules(
        required=required,
        allowed_values={k: _str_list(v, f"{where}.allowed_values.{k}") for k, v in allowed.items()},
        patterns={k: _compile(v, f"{where}.patterns.{k}") for k, v in patterns.items()},
        allow_empty=_str_list(d.get("allow_empty"), f"{where}.allow_empty"),
    )


def policy_from_dict(d: dict) -> Policy:
    if not isinstance(d, dict):
        raise PolicyError("policy must be a JSON object")
    unknown = set(d) - KNOWN_KEYS
    if unknown:
        raise PolicyError(f"unknown policy keys: {', '.join(sorted(unknown))}")
    per_type_raw = d.get("asset_types", {})
    if not isinstance(per_type_raw, dict):
        raise PolicyError("asset_types must be an object keyed by asset type")
    ignore = d.get("ignore", {})
    if not isinstance(ignore, dict):
        raise PolicyError("ignore must be an object")
    return Policy(
        base=_rules(d, "policy"),
        per_type={t: _rules(v, f"asset_types[{t}]") for t, v in per_type_raw.items()},
        include_asset_types=_str_list(d.get("include_asset_types"), "include_asset_types"),
        ignore_asset_types=_str_list(ignore.get("asset_types"), "ignore.asset_types"),
        ignore_projects=_str_list(ignore.get("projects"), "ignore.projects"),
        ignore_name_patterns=[_compile(p, "ignore.name_patterns")
                              for p in _str_list(ignore.get("name_patterns"), "ignore.name_patterns")],
        owner_key=d.get("owner_key", "owner"),
    )


def load_policy(path: str) -> Policy:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise PolicyError(f"{path}: not valid JSON ({exc})") from None
    return policy_from_dict(data)
