#!/usr/bin/env python3
"""Revalidate completed Issue #108 artifacts without generating games."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import protocol
import run_experiments


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--namespace",choices=("pilot","production"),required=True);parser.add_argument("--budget",type=int,choices=(10000,30000,100000));parser.add_argument("--ludii-jar",default=os.environ.get("LUDII_JAR",""));args=parser.parse_args()
    jar=Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():parser.error("pass --ludii-jar or set LUDII_JAR")
    config=protocol.load_config();tasks=protocol.tasks_from_config(config,args.namespace);manifest=protocol.load_json(protocol.manifest_path(args.namespace));game=protocol.REPO_ROOT/config["game"];failures=[];validated=0
    for task in tasks:
        if args.budget is not None and task.iteration_limit!=args.budget:continue
        row=manifest["tasks"][task.task_id]
        if row["state"]!="completed":continue
        task_dir=(protocol.REPO_ROOT/row["artifacts"]["validation"]).parent
        try:
            result=run_experiments.validate_generated(task,task_dir,jar,game,config)
            if result["normalized_trial_sha256"]!=row["artifacts"]["trial_sha256"]:raise ValueError("normalized trial hash differs from manifest")
            validated+=1
        except run_experiments.ScoreWinnerMismatch as error:
            protocol.block_production(task,str(error));failures.append({"task_id":task.task_id,"error":str(error),"global_block":True})
        except Exception as error:failures.append({"task_id":task.task_id,"error":str(error),"global_block":False})
    print(json.dumps({"validated":validated,"failures":failures},indent=2,sort_keys=True))
    if failures:raise SystemExit("revalidation failures detected")


if __name__=="__main__":main()
