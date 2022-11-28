"""Check resources against a policy and the label syntax rules."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .inputs import Resource
from .policy import Policy
from .syntax import MAX_LABELS, key_problem, value_problem

NONE = "(none)"


@dataclass
class Violation:
    resource: str
    asset_type: str
    project: str
    owner: str
    code: str
    key: str
    value: str
    message: str

    FIELDS = ("project", "asset_type", "resource", "owner", "code", "key", "value", "message")

    def to_dict(self) -> dict[str, Any]:
        return {f: getattr(self, f) for f in self.FIELDS}


@dataclass
class Result:
    checked: list[Resource]
    skipped: int
    violations: list[Violation]
    owner_key: str

    def owner_of(self, r: Resource) -> str:
        return r.labels.get(self.owner_key) or NONE

    def group(self, by: str) -> list[dict[str, Any]]:
        """Per-group counts: resources checked, non-compliant resources, violations."""
        key = {"project": lambda r: r.project or NONE,
               "asset_type": lambda r: r.asset_type or NONE,
               "owner": self.owner_of}[by]
        bad: dict[str, set[str]] = defaultdict(set)
        counts: dict[str, int] = defaultdict(int)
        total: dict[str, int] = defaultdict(int)
        by_name = {r.name: r for r in self.checked}
        for r in self.checked:
            total[key(r)] += 1
        for v in self.violations:
            g = key(by_name[v.resource])
            bad[g].add(v.resource)
            counts[g] += 1
        rows = [{by: g, "resources": total[g], "non_compliant": len(bad[g]), "violations": counts[g]}
                for g in total]
        return sorted(rows, key=lambda x: (-x["non_compliant"], str(x[by])))


def check_resource(r: Resource, policy: Policy) -> list[Violation]:
    owner = r.labels.get(policy.owner_key) or NONE
    out: list[Violation] = []

    def add(code: str, key: str, value: str, msg: str) -> None:
        out.append(Violation(r.name, r.asset_type, r.project or NONE, owner, code, key, value, msg))

    if len(r.labels) > MAX_LABELS:
        add("TOO_MANY_LABELS", "", "", f"{len(r.labels)} labels (max {MAX_LABELS})")
    for k, v in r.labels.items():
        p = key_problem(k)
        if p:
            add("INVALID_KEY", k, v, p)
        p = value_problem(v)
        if p:
            add("INVALID_VALUE", k, v, p)
    rules = policy.rules_for(r.asset_type)
    for k in rules.required:
        if k not in r.labels:
            add("MISSING_LABEL", k, "", f"required label '{k}' is missing")
        elif r.labels[k] == "" and k not in rules.allow_empty:
            add("EMPTY_VALUE", k, "", f"required label '{k}' is empty")
    for k, allowed in rules.allowed_values.items():
        v = r.labels.get(k)
        if v is not None and v != "" and v not in allowed:
            add("VALUE_NOT_ALLOWED", k, v, f"'{v}' is not one of: {', '.join(allowed)}")
    for k, pat in rules.patterns.items():
        v = r.labels.get(k)
        if v is not None and v != "" and not pat.search(v):
            add("PATTERN_MISMATCH", k, v, f"'{v}' does not match /{pat.pattern}/")
    return out


def run_audit(resources: list[Resource], policy: Policy) -> Result:
    checked, violations, skipped = [], [], 0
    seen: set[str] = set()
    for r in resources:
        if r.name in seen:
            continue  # the same resource can appear twice when inputs are combined
        seen.add(r.name)
        if policy.is_ignored(r.name, r.asset_type, r.project):
            skipped += 1
            continue
        checked.append(r)
        violations.extend(check_resource(r, policy))
    return Result(checked, skipped, violations, policy.owner_key)
