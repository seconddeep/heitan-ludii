#!/usr/bin/env python3
"""Run outcome-blind pilot or measured Issue #116 tasks, one JVM at a time."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

import protocol

RUNNER = Path(__file__).with_name("HeitanBenchmark.java")
REPLAYER = Path(__file__).with_name("HeitanBenchmarkReplay.java")


class MachineMemoryLimit(RuntimeError):
    pass


def physical_ram_bytes() -> int:
    completed = subprocess.run(["system_profiler", "SPHardwareDataType"], text=True, capture_output=True, check=True)
    match = re.search(r"^\s*Memory:\s*([0-9]+)\s*(GB|MB)\s*$", completed.stdout, re.MULTILINE)
    if not match:
        raise ValueError("physical RAM could not be obtained without retaining identifying hardware output")
    scale = 1024 ** 3 if match.group(2) == "GB" else 1024 ** 2
    return int(match.group(1)) * scale


def normalize_trial(raw: Path, normalized: Path, game_path: str) -> None:
    lines = raw.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n").splitlines()
    if not lines or not lines[0].startswith("game="):
        raise ValueError("trial lacks leading game field")
    lines[0] = f"game={game_path}"
    normalized.parent.mkdir(parents=True, exist_ok=True)
    temporary = normalized.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.flush();os.fsync(handle.fileno())
    os.replace(temporary, normalized)


def parse_peak_rss(stderr: str) -> int | None:
    match = re.search(r"(\d+)\s+maximum resident set size", stderr, re.IGNORECASE)
    return int(match.group(1)) if match else None


def gc_evidence(path: Path) -> tuple[str, int, float]:
    if not path.is_file():
        return "missing", 0, 0.0
    text = path.read_text(encoding="utf-8", errors="replace")
    pauses = [float(value) for value in re.findall(r"Pause .*? ([0-9.]+)ms(?:\s|$)", text)]
    return "recorded", len(pauses), round(sum(pauses) / 1000.0, 6)


def update(namespace: str, all_tasks: list[protocol.Task], config_hash: str, task_id: str, **values: object) -> None:
    with protocol.locked_manifest(namespace, all_tasks, config_hash) as manifest:
        manifest["tasks"][task_id].update(values)


def process_group_rss_bytes(group: int) -> int | None:
    try:
        completed=subprocess.run(["ps","-o","rss=","-g",str(group)],text=True,capture_output=True,check=False)
    except OSError:
        return None
    if completed.returncode:return None
    values=[int(value.strip())*1024 for value in completed.stdout.splitlines() if value.strip().isdigit()]
    return sum(values) if values else None


def execute(command: list[str], timeout: int, hard_rss_bytes: int | None) -> tuple[int, str, str, float, int | None]:
    started = time.monotonic()
    process = subprocess.Popen(["/usr/bin/time", "-l", *command], cwd=protocol.REPO_ROOT, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    peak=None
    while process.poll() is None:
        elapsed=time.monotonic()-started
        rss=process_group_rss_bytes(process.pid)
        if rss is not None:peak=rss if peak is None else max(peak,rss)
        reason=None
        if timeout>0 and elapsed>timeout:reason="timeout"
        elif hard_rss_bytes is not None and rss is not None and rss>=hard_rss_bytes:reason="memory"
        if reason:
            os.killpg(process.pid, signal.SIGTERM)
            try:stdout,stderr=process.communicate(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate()
            if reason=="memory":raise MachineMemoryLimit(f"process-group RSS reached the frozen hard machine-memory limit; sampled peak={peak}")
            raise subprocess.TimeoutExpired(command,timeout,output=stdout,stderr=stderr)
        time.sleep(0.5)
    stdout,stderr=process.communicate()
    measured=parse_peak_rss(stderr)
    if measured is not None:peak=measured if peak is None else max(peak,measured)
    return process.returncode,stdout,stderr,time.monotonic()-started,peak


def validate_trial(task: protocol.Task, trial: Path, stamp: Path, jar: Path, game: Path, values: dict) -> None:
    command = ["java", "-cp", str(jar), str(REPLAYER), str(game), task.board, str(trial), str(values["sites"]),
               str(values["pieces_per_player"]), str(values["total_placements"]), str(values["turns"]), str(stamp)]
    completed = subprocess.run(command, cwd=protocol.REPO_ROOT, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise ValueError(f"legal replay failed: {completed.stderr.strip() or completed.stdout.strip()}")


def classify_failure(error: BaseException, stderr: str) -> str:
    text = f"{error} {stderr}".lower()
    if isinstance(error, subprocess.TimeoutExpired): return "hard_timeout"
    if isinstance(error, MachineMemoryLimit): return "machine_memory_hard_limit"
    if "outofmemory" in text or "out of memory" in text: return "oom"
    if "fatal error" in text or "fatal exception" in text: return "fatal_jvm"
    if isinstance(error, (ValueError, FileNotFoundError)): return "validation_failure"
    return "abnormal_exit"


def run_task(task: protocol.Task, namespace: str, all_tasks: list[protocol.Task], config: dict, jar: Path,
             derived: dict, xmx: str, timeout: int, gc_setting: str, ram: int) -> str:
    config_hash = protocol.sha256(protocol.CONFIG_PATH)
    manifest = protocol.load_json(protocol.manifest_path(namespace)) if protocol.manifest_path(namespace).exists() else protocol.empty_manifest(namespace, all_tasks, config_hash)
    current = manifest["tasks"][task.task_id]
    if current["state"] == "completed": return "completed"
    if current["state"] == "failed" and namespace == "measured": return "failed"
    output_root = protocol.RESULTS_ROOT / namespace / "tasks" / task.task_id
    temp_root = protocol.RESULTS_ROOT / namespace / ".tmp";temp_root.mkdir(parents=True, exist_ok=True)
    task_dir = Path(tempfile.mkdtemp(prefix=f"{task.task_id}-", dir=temp_root))
    raw = task_dir / "raw" / f"{task.task_id}.trl";raw.parent.mkdir(parents=True)
    normalized = task_dir / f"{task.task_id}.trl";result = task_dir / "result.csv";gc_log = task_dir / "gc.log"
    started_utc = protocol.utc_now();stderr="";exit_code=None;elapsed=0.0;peak=None
    update(namespace, all_tasks, config_hash, task.task_id, state="running", attempts=int(current["attempts"])+1,
           start_utc=started_utc, jvm_xmx=xmx, physical_ram_bytes=ram, error=None)
    values = derived[task.board]
    try:
        gc_arg = gc_setting.replace("{gc_log}", str(gc_log))
        command = ["java", f"-Xmx{xmx}", gc_arg, "-cp", str(jar), str(RUNNER), str(protocol.REPO_ROOT / config["game"]),
                   task.board, task.task_id, str(task.seed), str(task.iteration_limit), str(result), str(raw), str(protocol.REPO_ROOT / config["game"]),
                   str(values["sites"]), str(values["pieces_per_player"]), str(values["total_placements"]), str(values["turns"])]
        hard_rss=None if namespace=="pilot" else int(ram*float(config["operational_parameters"]["hard_rss_fraction_of_physical_ram"]))
        exit_code, _, stderr, elapsed, peak = execute(command, timeout, hard_rss)
        if exit_code != 0:
            raise RuntimeError(f"Java exit {exit_code}: {stderr}")
        normalize_trial(raw, normalized, config["game"])
        stamp = task_dir / "validation.txt";validate_trial(task, raw, task_dir / "raw-validation.txt", jar, protocol.REPO_ROOT / config["game"], values)
        validate_trial(task, normalized, stamp, jar, protocol.REPO_ROOT / config["game"], values)
        gc_status,gc_count,gc_seconds=gc_evidence(gc_log)
        validation = {"schema_version": 1, "validated": True, "validation_scope": "operational-only-outcome-blind",
                      "aggregate_outcomes_inspected": False, "legal_replay": True, "natural_completion": True,
                      "three_placements_per_turn": True, "piece_totals_match_source_derived_values": True}
        protocol.atomic_json(task_dir / "validation.json", validation)
        if output_root.exists():
            raise ValueError("existing task directory would be overwritten")
        output_root.parent.mkdir(parents=True, exist_ok=True);os.replace(task_dir, output_root)
        artifacts = {}
        for name, path in (("trial", output_root / normalized.name), ("result", output_root / "result.csv"),
                           ("validation", output_root / "validation.json"), ("gc_log", output_root / "gc.log")):
            artifacts[name] = path.relative_to(protocol.REPO_ROOT).as_posix();artifacts[f"{name}_sha256"] = protocol.sha256(path)
        update(namespace, all_tasks, config_hash, task.task_id, state="completed", end_utc=protocol.utc_now(), elapsed_seconds=round(elapsed,3),
               exit_code=exit_code, failure_classification=None, peak_rss_bytes=peak, gc_log_status=gc_status,
               gc_pause_count=gc_count, gc_pause_seconds=gc_seconds, trial_status="retained-normalized",
               trial_sha256=protocol.sha256(output_root / normalized.name), replay_validation_status="validated", artifacts=artifacts)
        return "completed"
    except Exception as error:
        elapsed = elapsed or 0.0
        kind = classify_failure(error, stderr)
        if task_dir.exists():
            quarantine = protocol.RESULTS_ROOT / namespace / "quarantine";quarantine.mkdir(parents=True, exist_ok=True)
            os.replace(task_dir, quarantine / f"{task.task_id}-{time.time_ns()}")
        update(namespace, all_tasks, config_hash, task.task_id, state="failed", end_utc=protocol.utc_now(), elapsed_seconds=round(elapsed,3),
               exit_code=exit_code, failure_classification=kind, peak_rss_bytes=peak, trial_status="failed-or-quarantined",
               replay_validation_status="failed", error=protocol.sanitize(error))
        return kind


def mark_stopped(config: dict, board: str, lower_budget: int) -> None:
    all_tasks=protocol.tasks(config,"measured");config_hash=protocol.sha256(protocol.CONFIG_PATH)
    with protocol.locked_manifest("measured",all_tasks,config_hash) as manifest:
        for task in all_tasks:
            if task.board==board and task.iteration_limit>lower_budget and manifest["tasks"][task.task_id]["state"]=="pending":
                manifest["tasks"][task.task_id].update(state="not_attempted",failure_classification="lower_depth_stopping_gate",error=f"Board/{board} stopped after UCT {lower_budget}",end_utc=protocol.utc_now())


def mark_condition_remainder(config: dict, board: str, budget: int, reason: str) -> None:
    all_tasks=protocol.tasks(config,"measured");config_hash=protocol.sha256(protocol.CONFIG_PATH)
    with protocol.locked_manifest("measured",all_tasks,config_hash) as manifest:
        for task in all_tasks:
            if task.board==board and task.iteration_limit==budget and manifest["tasks"][task.task_id]["state"]=="pending":
                manifest["tasks"][task.task_id].update(state="not_attempted",failure_classification="condition_hard_safety_stop",error=reason,end_utc=protocol.utc_now())


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("namespace",choices=("pilot","measured"));parser.add_argument("--board",choices=protocol.BOARDS);parser.add_argument("--budget",type=int,choices=protocol.BUDGETS);parser.add_argument("--ludii-jar",default=os.environ.get("LUDII_JAR",""));args=parser.parse_args()
    config=protocol.load_config();protocol.validate_prepilot_config(config)
    jar=Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():parser.error("set LUDII_JAR or pass --ludii-jar")
    game=protocol.REPO_ROOT/config["game"];derived=protocol.extract_board_values(game,config["expected_board_values"]);ram=physical_ram_bytes()
    if args.namespace=="pilot":
        if args.board or args.budget:parser.error("pilot runs all three preregistered board checks")
        selected=protocol.tasks(config,"pilot");xmx=config["pilot"]["candidate_jvm_xmx"];timeout=3600;gc_setting="-Xlog:gc*,safepoint:file={gc_log}:time,uptime,level,tags"
    else:
        if not args.board or args.budget is None:parser.error("measured requires --board and --budget")
        if not os.environ.get("TMUX") or os.environ.get("HEITAN116_CAFFEINATE")!="1" or not os.environ.get("HEITAN116_RUNNER_ID"):
            raise ValueError("measured execution requires tmux, caffeinate marker, and an opaque runner ID")
        if not re.fullmatch(r"[A-Za-z0-9_-]+",os.environ["HEITAN116_RUNNER_ID"]):raise ValueError("runner ID must be opaque alphanumeric/dash/underscore")
        lock=protocol.measured_gate(config)
        if protocol.sha256(jar)!=lock["ludii_jar_sha256"]:raise ValueError("Ludii JAR differs from lock")
        op=config["operational_parameters"];xmx=op["jvm_xmx"];timeout=int(op["hard_timeout_seconds_per_game"]);gc_setting=op["gc_logging"]["java_argument"]
        lower=[value for value in config["uct_budgets"] if value<args.budget]
        for prior in lower:
            path=protocol.RESULTS_ROOT/"measured"/"conditions"/f"{args.board}-uct-{prior:05d}.json"
            if not path.is_file():raise ValueError(f"lower-depth condition lacks classification: {args.board} UCT {prior}")
            if protocol.load_json(path)["classification"]=="infeasible in current environment":
                mark_stopped(config,args.board,prior);print(f"Board/{args.board} deeper conditions marked not attempted");return
        selected=[task for task in protocol.tasks(config,"measured") if task.board==args.board and task.iteration_limit==args.budget]
    all_tasks=protocol.tasks(config,args.namespace);config_hash=protocol.sha256(protocol.CONFIG_PATH)
    if not protocol.manifest_path(args.namespace).exists():protocol.atomic_json(protocol.manifest_path(args.namespace),protocol.empty_manifest(args.namespace,all_tasks,config_hash))
    for task in selected:
        status=run_task(task,args.namespace,all_tasks,config,jar,derived,xmx,timeout,gc_setting,ram);print(f"{task.task_id}: {status}",flush=True)
        if args.namespace=="measured":
            row=protocol.load_json(protocol.manifest_path("measured"))["tasks"][task.task_id]
            hard_rss=row["peak_rss_bytes"] is not None and int(row["peak_rss_bytes"])/ram>=float(config["operational_parameters"]["hard_rss_fraction_of_physical_ram"])
            if status!="completed" or hard_rss:
                reason=status if status!="completed" else "machine_memory_hard_limit"
                mark_condition_remainder(config,args.board,args.budget,reason);mark_stopped(config,args.board,args.budget);break
    if args.namespace=="measured":
        completed=subprocess.run(["python3",str(Path(__file__).with_name("summarize.py")),"--condition","--board",args.board,"--budget",str(args.budget)],cwd=protocol.REPO_ROOT)
        if completed.returncode:raise SystemExit(completed.returncode)


if __name__=="__main__":main()
