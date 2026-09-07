#!/usr/bin/env python3
"""Apply the second, post-pilot operational freeze for Issue #116."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import re
import subprocess

import protocol
from run_benchmark import physical_ram_bytes


def sources() -> list[Path]:
    names = ["README.md", "config.json", "prepilot-lock.json", "scripts/protocol.py", "scripts/run_benchmark.py", "scripts/freeze_protocol.py",
             "scripts/summarize.py", "scripts/status.py", "scripts/public_safety_audit.py",
             "scripts/HeitanBenchmark.java", "scripts/HeitanBenchmarkReplay.java", "scripts/test_protocol.py"]
    return [protocol.ISSUE_ROOT / name for name in names] + [protocol.REPO_ROOT / "games/Heitan.lud"]


def safe_cpu() -> str:
    completed=subprocess.run(["system_profiler","SPHardwareDataType"],text=True,capture_output=True,check=True)
    match=re.search(r"^\s*Chip:\s*(.+?)\s*$",completed.stdout,re.MULTILINE)
    return match.group(1) if match else "unavailable"


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--ludii-jar",default=os.environ.get("LUDII_JAR",""))
    parser.add_argument("--xmx",default="8g")
    parser.add_argument("--hard-timeout-seconds",type=int,default=28800)
    parser.add_argument("--soft-runtime-seconds",type=int,default=7200)
    parser.add_argument("--soft-rss-fraction",type=float,default=0.60)
    parser.add_argument("--hard-rss-fraction",type=float,default=0.75)
    args=parser.parse_args()
    jar=Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():parser.error("set LUDII_JAR or pass --ludii-jar")
    if not 0 < args.soft_rss_fraction < args.hard_rss_fraction < 1 or args.soft_runtime_seconds >= args.hard_timeout_seconds:
        parser.error("soft limits must be below hard limits")
    config=protocol.load_config();protocol.validate_prepilot_config(config)
    if config["protocol_status"]!="prepilot-frozen" or protocol.LOCK_PATH.exists() or protocol.SOURCE_LOCK_PATH.exists():
        raise ValueError("post-pilot freeze may run exactly once from the prepilot-frozen state")
    pilot_path=protocol.manifest_path("pilot")
    if not pilot_path.is_file():raise ValueError("pilot manifest is missing")
    manifest=protocol.load_json(pilot_path);pilot_tasks=protocol.tasks(config,"pilot")
    rows=[manifest["tasks"][task.task_id] for task in pilot_tasks]
    if any(row["state"]!="completed" or row["replay_validation_status"]!="validated" for row in rows):raise ValueError("all outcome-blind pilots must validate")
    ram=physical_ram_bytes();game=protocol.REPO_ROOT/config["game"]
    derived=protocol.extract_board_values(game,config["expected_board_values"])
    config["operational_parameters"]={
        "status":"postpilot-frozen", "jvm_xmx":args.xmx,
        "hard_timeout_seconds_per_game":args.hard_timeout_seconds,
        "soft_runtime_seconds_per_game":args.soft_runtime_seconds,
        "soft_rss_fraction_of_physical_ram":args.soft_rss_fraction,
        "hard_rss_fraction_of_physical_ram":args.hard_rss_fraction,
        "gc_logging":{"role":"diagnostic heap-pressure evidence; not a machine-memory ratio",
                      "java_argument":"-Xlog:gc*,safepoint:file={gc_log}:time,uptime,level,tags"}}
    config["protocol_status"]="postpilot-locked";config["postpilot_locked_at_utc"]=protocol.utc_now();protocol.atomic_json(protocol.CONFIG_PATH,config)
    required=sources();missing=[path for path in required if not path.is_file()]
    if missing:raise ValueError(f"required sources are missing: {missing}")
    source_lock={"schema_version":1,"locked_before_measured_benchmark":True,"outcomes_inspected_during_lock":False,
                 "game_outcomes_in_scope":False,"files":[protocol.source_entry(path) for path in required]}
    protocol.atomic_json(protocol.SOURCE_LOCK_PATH,source_lock)
    java=subprocess.run(["java","--version"],text=True,capture_output=True,check=True);java_version=(java.stdout or java.stderr).splitlines()[0]
    game_commit=subprocess.run(["git","log","-1","--format=%H","--",config["game"]],cwd=protocol.REPO_ROOT,text=True,capture_output=True,check=True).stdout.strip()
    pilot_evidence={"tasks":len(rows),"manifest_sha256":protocol.sha256(pilot_path),"outcomes_inspected":False,
                    "maximum_elapsed_seconds":max(float(row["elapsed_seconds"]) for row in rows),
                    "maximum_peak_rss_bytes":max(int(row["peak_rss_bytes"]) for row in rows if row["peak_rss_bytes"] is not None),
                    "all_replays_validated":True}
    lock={"schema_version":1,"experiment_version":config["experiment_version"],"postpilot_locked_at_utc":config["postpilot_locked_at_utc"],
          "config_sha256":protocol.sha256(protocol.CONFIG_PATH),"source_lock_sha256":protocol.sha256(protocol.SOURCE_LOCK_PATH),
          "game_sha256":protocol.sha256(game),"game_definition_commit":game_commit,"source_derived_board_values":derived,
          "ludii_version":config["ludii_version"],"ludii_jar_sha256":protocol.sha256(jar),"pilot_operational_evidence":pilot_evidence,
          "operational_parameters":config["operational_parameters"],
          "environment":{"os":platform.system(),"os_version":platform.mac_ver()[0],"architecture":platform.machine(),"cpu":safe_cpu(),
                         "physical_ram_bytes":ram,"java":java_version,"python":platform.python_version(),"worker_count":1},
          "memory_roles":{"peak_rss":"whole-process machine-safety measurement","physical_ram":"machine-safety denominator",
                          "jvm_xmx":"configured Java heap ceiling; not compared as an RSS ratio","gc_evidence":"diagnostic heap-pressure evidence"},
          "rerun_command":"caffeinate -i env HEITAN116_CAFFEINATE=1 HEITAN116_RUNNER_ID=opaque LUDII_JAR=$LUDII_JAR python3 experiments/issue-116/scripts/run_benchmark.py measured --board BOARD --budget UCT"}
    protocol.atomic_json(protocol.LOCK_PATH,lock);print(f"post-pilot protocol locked: {lock['config_sha256']}")


if __name__=="__main__":main()
