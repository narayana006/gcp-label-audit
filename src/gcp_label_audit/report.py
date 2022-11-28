"""Table, CSV and JSON output."""

from __future__ import annotations

import csv
import io
import json

from .audit import Result, Violation

GROUPS = ("project", "asset_type", "owner")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]
    fmt = lambda r: "  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip()  # noqa: E731
    return "\n".join([fmt(headers), fmt(["-" * w for w in widths])] + [fmt(r) for r in rows])


def headline(res: Result) -> str:
    bad = len({v.resource for v in res.violations})
    return (f"Checked {len(res.checked)} resource(s), skipped {res.skipped} by policy: "
            f"{bad} non-compliant, {len(res.violations)} violation(s)")


def render_table(res: Result, group_by: list[str], details: bool = True) -> str:
    out = [headline(res)]
    for g in group_by:
        rows = [[str(r[g]), str(r["resources"]), str(r["non_compliant"]), str(r["violations"])]
                for r in res.group(g)]
        out += ["", f"By {g.replace('_', ' ')}:", _table([g.upper().replace("_", " "), "RESOURCES", "NON-COMPLIANT", "VIOLATIONS"], rows)]
    if details and res.violations:
        rows = [[v.project, v.asset_type, _shorten(v.resource), v.code, v.key, v.message]
                for v in sorted(res.violations, key=lambda v: (v.project, v.asset_type, v.resource, v.code, v.key))]
        out += ["", "Violations:", _table(["PROJECT", "ASSET TYPE", "RESOURCE", "CODE", "KEY", "DETAIL"], rows)]
    return "\n".join(out)


def _shorten(name: str) -> str:
    """'//compute.googleapis.com/projects/p/zones/z/instances/web-1' -> '.../zones/z/instances/web-1'."""
    parts = name.lstrip("/").split("/")
    if len(parts) <= 4:
        return name
    return ".../" + "/".join(parts[-4:])


def render_csv(violations: list[Violation]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(Violation.FIELDS), lineterminator="\n")
    w.writeheader()
    for v in violations:
        w.writerow(v.to_dict())
    return buf.getvalue().rstrip("\n")


def render_json(res: Result) -> str:
    return json.dumps({
        "checked": len(res.checked),
        "skipped": res.skipped,
        "non_compliant": len({v.resource for v in res.violations}),
        "by_project": res.group("project"),
        "by_asset_type": res.group("asset_type"),
        "by_owner": res.group("owner"),
        "violations": [v.to_dict() for v in res.violations],
    }, indent=2, ensure_ascii=False)
