"""Command line entry point."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .audit import run_audit
from .inputs import InputError, load_resources
from .policy import PolicyError, load_policy, policy_from_dict
from .syntax import key_problem
from .report import GROUPS, render_csv, render_json, render_table


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gcp-label-audit",
        description="Check resource labels from Cloud Asset Inventory output "
                    "(`gcloud asset search-all-resources --format=json`) against a labeling policy. Offline.",
    )
    p.add_argument("files", nargs="*", default=["-"], help="JSON or JSON-lines files, or - for stdin (default)")
    p.add_argument("--policy", help="policy JSON file (see examples/policy.json)")
    p.add_argument("--required", default="", help="comma-separated required keys (added to --policy, or used alone)")
    p.add_argument("--owner-key", help="label used for the by-owner report (default: policy owner_key or 'owner')")
    p.add_argument("--format", choices=["table", "csv", "json"], default="table")
    p.add_argument("--group-by", default="project,asset_type,owner",
                   help="table summaries to print: any of project,asset_type,owner (default all)")
    p.add_argument("--summary-only", action="store_true", help="table output: omit the per-violation list")
    p.add_argument("--no-fail", action="store_true", help="always exit 0 when the input was read")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    group_by = [g.strip().replace("-", "_") for g in args.group_by.split(",") if g.strip()]
    bad = [g for g in group_by if g not in GROUPS]
    if bad:
        print(f"gcp-label-audit: error: unknown --group-by value(s): {', '.join(bad)}", file=sys.stderr)
        return 2
    try:
        policy = load_policy(args.policy) if args.policy else policy_from_dict({})
        extra = [k.strip() for k in args.required.split(",") if k.strip()]
        for k in extra:
            if key_problem(k):
                raise PolicyError(f"--required: {k!r} can never be a valid label key ({key_problem(k)})")
        if extra:
            policy.base.required = list(dict.fromkeys(policy.base.required + extra))
        if not args.policy and not extra:
            print("gcp-label-audit: no --policy or --required given; checking label syntax only", file=sys.stderr)
        if args.owner_key:
            policy.owner_key = args.owner_key
        resources = []
        for path in args.files:
            if path == "-":
                resources += load_resources(sys.stdin.read(), "<stdin>")
            else:
                with open(path, encoding="utf-8") as fh:
                    resources += load_resources(fh.read(), path)
    except (OSError, PolicyError, InputError) as exc:
        print(f"gcp-label-audit: error: {exc}", file=sys.stderr)
        return 2

    res = run_audit(resources, policy)
    if args.format == "json":
        print(render_json(res))
    elif args.format == "csv":
        print(render_csv(res.violations))
    else:
        print(render_table(res, group_by, details=not args.summary_only))
    return 1 if res.violations and not args.no_fail else 0


if __name__ == "__main__":
    sys.exit(main())
