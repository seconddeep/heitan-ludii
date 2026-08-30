#!/usr/bin/env python3
"""Report Issue #112 manifest state without inspecting game outcomes."""

from __future__ import annotations

import argparse
from collections import Counter
import json

import protocol


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--namespace",choices=("pilot","production"),required=True);parser.add_argument("--budget",type=int);args=parser.parse_args()
    config=protocol.load_config();tasks=protocol.tasks_from_config(config,args.namespace);manifest=protocol.reconcile_manifest(args.namespace,tasks,protocol.sha256(protocol.CONFIG_PATH));selected=[manifest["tasks"][task.task_id] for task in tasks if args.budget is None or task.iteration_limit==args.budget]
    states=Counter(row["state"] for row in selected);failures=Counter(row.get("failure_kind") for row in selected if row.get("failure_kind"))
    print(json.dumps({"namespace":args.namespace,"budget":args.budget,"tasks":len(selected),"states":states,"failure_kinds":failures,"production_blocked":protocol.PRODUCTION_BLOCK_PATH.exists()},indent=2,sort_keys=True))


if __name__=="__main__":main()
