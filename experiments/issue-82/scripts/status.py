#!/usr/bin/env python3
"""Show Issue #82 manifest status without exposing pilot outcomes."""

from __future__ import annotations

import argparse
from collections import Counter
import json

import protocol


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", choices=("pilot", "production"), required=True)
    parser.add_argument("--operational-only", action="store_true")
    args = parser.parse_args()
    path = protocol.manifest_path(args.namespace)
    if not path.is_file():
        raise SystemExit(f"manifest does not exist: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    rows = list(manifest["tasks"].values())
    print(json.dumps({
        "namespace": args.namespace,
        "states": dict(Counter(row["state"] for row in rows)),
        "tasks": [
            {
                "task_id": row["task_id"], "budget": row["iteration_limit"], "state": row["state"],
                "attempts": row["attempts"], "elapsed_seconds": row.get("elapsed_seconds"),
                "peak_rss_bytes": row.get("peak_rss_bytes"), "failure_kind": row.get("failure_kind"),
                "error": row.get("error"),
            }
            for row in rows
        ],
        "outcomes_hidden": args.namespace == "pilot" or args.operational_only,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
