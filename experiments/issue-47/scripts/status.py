#!/usr/bin/env python3
"""Display Issue #47 task state without mutating it."""

from __future__ import annotations

import argparse
from collections import Counter
import json

import protocol


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", choices=("pilot", "production"), required=True)
    args = parser.parse_args()
    path = protocol.manifest_path(args.namespace)
    if not path.is_file():
        print(f"{args.namespace}: manifest not created")
        return
    manifest = json.loads(path.read_text(encoding="utf-8"))
    finalization_path = protocol.RESULTS_ROOT / "production/finalization.json"
    finalization = None
    if args.namespace == "production" and finalization_path.is_file():
        finalization = json.loads(finalization_path.read_text(encoding="utf-8"))
    rows = list(manifest["tasks"].values())
    for budget in sorted({int(row["iteration_limit"]) for row in rows}):
        selected = [row for row in rows if int(row["iteration_limit"]) == budget]
        counts = Counter(row["state"] for row in selected)
        states = " ".join(f"{state}={counts[state]}" for state in sorted(counts))
        attempts = sum(int(row["attempts"]) for row in selected)
        if finalization and str(budget) in finalization["analyzed_games_by_budget"]:
            analyzed = int(finalization["analyzed_games_by_budget"][str(budget)])
            excluded = len([row for row in finalization["excluded_tasks"] if int(row.get("game_index", 0)) and budget == 100000])
            print(
                f"{args.namespace} UCT {budget}: planned={len(selected)} finalized={analyzed} "
                f"excluded={excluded} attempts={attempts} status=analysis-final"
            )
        else:
            print(f"{args.namespace} UCT {budget}: total={len(selected)} attempts={attempts} {states}")


if __name__ == "__main__":
    main()
