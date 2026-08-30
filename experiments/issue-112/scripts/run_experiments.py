#!/usr/bin/env python3
"""Run resilient corrected-rule Issue #112 pilot and production tasks."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time

import protocol


RUNNER = Path(__file__).with_name("Heitan4x4CorrectedExperiment.java")
REPLAYER = Path(__file__).with_name("Heitan4x4CorrectedReplay.java")
MISMATCH_MARKERS = ("score mismatch", "winner mismatch", "partition mismatch", "own-secured identity mismatch", "replay score differs")


class ScoreWinnerMismatch(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_one_csv(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    if len(rows) != 1:
        raise ValueError(f"expected one row in {path.name}, found {len(rows)}")
    return rows[0]


def expected_sites() -> set[str]:
    return {f"S{row}{column}" for row in range(5) for column in range(5)} | {f"O{row}{column}" for row in range(4) for column in range(4)}


def audit_board(value: str, config: dict | None = None) -> dict[str, int | str]:
    config = config or protocol.load_config()
    encoded = value.split("|")
    if len(encoded) != 41:
        raise ValueError("final board must contain 41 sites")
    sites: dict[str, tuple[int, int, int]] = {}
    for item in encoded:
        name, state, p1, p2 = item.split(":")
        if name in sites:
            raise ValueError(f"duplicate site: {name}")
        sites[name] = int(state), int(p1), int(p2)
    if set(sites) != expected_sites():
        raise ValueError("final-board site set differs from Board/4x4")
    objectives = [(state, p1, p2) for name, (state, p1, p2) in sites.items() if name.startswith("O")]
    secured = [sum(state == owner for state, _, _ in objectives) for owner in (3, 4)]
    advantage = [sum(state == owner for state, _, _ in objectives) for owner in (1, 2)]
    corrected = [sum(p1 for state, p1, _ in objectives if state == 1), sum(p2 for state, _, p2 in objectives if state == 2)]
    total_objective = [sum(p1 for _, p1, _ in objectives), sum(p2 for _, _, p2 in objectives)]
    categories = {
        "own_secured": [sum(p1 for state, p1, _ in objectives if state == 3), sum(p2 for state, _, p2 in objectives if state == 4)],
        "opponent_secured": [sum(p1 for state, p1, _ in objectives if state == 4), sum(p2 for state, _, p2 in objectives if state == 3)],
        "opponent_advantage": [sum(p1 for state, p1, _ in objectives if state == 2), sum(p2 for state, _, p2 in objectives if state == 1)],
        "neutral": [sum(p1 for state, p1, _ in objectives if state == 0), sum(p2 for state, _, p2 in objectives if state == 0)],
    }
    for player in (0, 1):
        if total_objective[player] != corrected[player] + sum(values[player] for values in categories.values()):
            raise ScoreWinnerMismatch("Objective-piece partition mismatch")
        if categories["own_secured"][player] != 3 * secured[player]:
            raise ScoreWinnerMismatch("own-Secured identity mismatch")
    secured_weight = int(config["board"]["secured_weight"])
    advantage_weight = int(config["board"]["advantage_weight"])
    scores = [secured_weight * secured[player] + advantage_weight * advantage[player] + corrected[player] for player in (0, 1)]
    winner = 1 if scores[0] > scores[1] else 2 if scores[1] > scores[0] else 0
    layer = "secured_objectives" if secured[0] != secured[1] else "advantage_objectives" if advantage[0] != advantage[1] else "objective_pieces" if corrected[0] != corrected[1] else "draw"
    metrics: dict[str, int | str] = {"winner": winner, "deciding_criterion": layer}
    for player in (0, 1):
        prefix = f"p{player + 1}"
        metrics.update({f"{prefix}_score": scores[player], f"{prefix}_secured_objectives": secured[player], f"{prefix}_advantage_objectives": advantage[player], f"{prefix}_corrected_objective_pieces": corrected[player], f"{prefix}_total_objective_pieces": total_objective[player]})
        for name, values in categories.items():
            metrics[f"{prefix}_excluded_{name}"] = values[player]
    metrics["p1_total_pieces"] = sum(p1 for _, p1, _ in sites.values())
    metrics["p2_total_pieces"] = sum(p2 for _, _, p2 in sites.values())
    return metrics


def normalize_trial(raw: Path, normalized: Path, game_path: str) -> None:
    data = raw.read_text(encoding="utf-8")
    lines = data.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    if not lines or not lines[0].startswith("game="):
        raise ValueError("trial lacks a leading game= field")
    lines[0] = f"game={game_path}"
    normalized.parent.mkdir(parents=True, exist_ok=True)
    temporary = normalized.with_suffix(".trl.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, normalized)


def process_rss_bytes(pid: int) -> int | None:
    try:
        completed = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], text=True, capture_output=True, check=False)
    except OSError:
        return None
    if completed.returncode or not completed.stdout.strip():
        return None
    return int(completed.stdout.strip().splitlines()[0]) * 1024


def parse_peak_rss(stderr: str) -> int | None:
    mac=re.search(r"(\d+)\s+maximum resident set size",stderr,re.IGNORECASE)
    if mac:return int(mac.group(1))
    linux=re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)",stderr,re.IGNORECASE)
    return int(linux.group(1))*1024 if linux else None


def timed_java(command: list[str], timeout: int, on_start=None) -> tuple[subprocess.CompletedProcess[str], int | None]:
    timed_command=["/usr/bin/time","-l",*command] if os.environ.get("HEITAN112_USE_TIME")=="1" and Path("/usr/bin/time").is_file() else command
    process = subprocess.Popen(timed_command, cwd=protocol.REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if on_start:
        on_start(process.pid)
    started = time.monotonic();peak = None
    while process.poll() is None:
        rss = process_rss_bytes(process.pid)
        peak = rss if peak is None else max(peak, rss or 0)
        if timeout and time.monotonic() - started > timeout:
            process.terminate()
            try: stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill();stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
        time.sleep(0.5)
    stdout, stderr = process.communicate()
    measured=parse_peak_rss(stderr)
    if measured is not None:peak=measured if peak is None else max(peak,measured)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr), peak


def replay(trial: Path, output: Path, jar: Path, game: Path, task: protocol.Task, full_scoring: bool) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=True)
    command = ["java", "-cp", str(jar), str(REPLAYER), str(game), str(trial), str(task.game_index), str(output / "games.csv"), str(output / "placements.csv"), str(output / "turn-states.csv"), "full" if full_scoring else "operational"]
    completed = subprocess.run(command, cwd=protocol.REPO_ROOT, text=True, capture_output=True, check=False)
    if completed.returncode:
        message = completed.stderr.strip() or completed.stdout.strip()
        if any(marker in message.lower() for marker in MISMATCH_MARKERS):
            raise ScoreWinnerMismatch(message)
        raise ValueError(f"trial legal replay failed: {message}")
    return read_one_csv(output / "games.csv")


def validate_generated(task: protocol.Task, task_dir: Path, jar: Path, game: Path, config: dict, full_scoring: bool = False, replay_root: Path | None = None) -> dict:
    raw = task_dir / "raw" / f"{task.experiment_id}-{task.game_index:04d}.trl"
    normalized = task_dir / f"{task.experiment_id}-{task.game_index:04d}.trl"
    result_path = task_dir / "result.csv"
    if not raw.is_file() or not result_path.is_file():
        raise FileNotFoundError("runner output is incomplete")
    normalized_for_replay = (replay_root / "normalized.trl") if replay_root else normalized
    normalize_trial(raw, normalized_for_replay, config["trial_normalization"]["game_path"])
    if replay_root and (not normalized.is_file() or normalized.read_bytes() != normalized_for_replay.read_bytes()):
        raise ValueError("retained normalized trial differs from a fresh raw-trial normalization")
    tables_root = replay_root or (task_dir / "validation-raw")
    raw_tables = tables_root / "raw-trial"
    normalized_tables = tables_root / "normalized-trial"
    raw_game = replay(raw, raw_tables, jar, game, task, full_scoring)
    normalized_game = replay(normalized_for_replay, normalized_tables, jar, game, task, full_scoring)
    for name in ("games.csv", "placements.csv", "turn-states.csv"):
        if (raw_tables / name).read_bytes() != (normalized_tables / name).read_bytes():
            raise ValueError(f"raw and normalized replay differ: {name}")
    result = read_one_csv(result_path)
    identity = result["experiment_id"], int(result["game_index"]), int(result["seed"]), int(result["iteration_limit"])
    if identity != (task.experiment_id, task.game_index, task.seed, task.iteration_limit):
        raise ValueError("result identity differs from fixed task")
    if result["completed"].lower() != "true" or result["end_type"] != "NaturalEnd" or (int(result["moves"]), int(result["turns"])) != (72, 24):
        raise ValueError("game is not a natural 72-placement / 24-turn completion")
    placements = read_csv(normalized_tables / "placements.csv")
    states = read_csv(normalized_tables / "turn-states.csv")
    if len(placements) != 72 or len(states) != 24 * 41:
        raise ValueError("replay table dimensions differ")
    if {int(row["mover"]) for row in placements} != {1, 2}:
        raise ValueError("both players are not represented")
    for turn in range(1, 25):
        selected = [row for row in placements if int(row["turn_number"]) == turn]
        if len(selected) != 3 or len({row["mover"] for row in selected}) != 1:
            raise ValueError(f"turn {turn} is not exactly three placements by one mover")
        if {row["point"] for row in states if int(row["turn_number"]) == turn} != expected_sites():
            raise ValueError(f"turn {turn} state table has the wrong site set")
    if {player: sum(int(row["mover"]) == player for row in placements) for player in (1, 2)} != {1: 36, 2: 36}:
        raise ValueError("per-player placement totals differ from 36/36")
    validation = {"schema_version": 1, "validated": True, "validation_scope": "full-scoring" if full_scoring else "operational-only", "legal_move_replay": True, "natural_end": True, "moves": 72, "turns": 24, "all_turns_have_three_placements": True, "p1_placements": 36, "p2_placements": 36, "raw_trial_sha256": protocol.sha256(raw), "normalized_trial_sha256": protocol.sha256(normalized), "raw_to_normalized": True, "score_reconstructed": False, "winner_reconstructed": False}
    if not full_scoring:
        return validation
    metrics = audit_board(result["final_board"], config)
    expected = (int(metrics["p1_score"]), int(metrics["p2_score"]), int(metrics["winner"]))
    reported = (int(result["p1_score"]), int(result["p2_score"]), int(result["winner"]))
    replayed = (int(raw_game["final_p1_score"]), int(raw_game["final_p2_score"]), int(raw_game["winner"]))
    if expected != reported or expected != replayed or raw_game["final_board"] != result["final_board"] or normalized_game != raw_game:
        raise ScoreWinnerMismatch("independent score, winner, or final-board reconstruction mismatch")
    for key, value in metrics.items():
        if key in result and str(value) != result[key]:
            raise ScoreWinnerMismatch(f"runner metric differs from independent reconstruction: {key}")
    validation.update(score_reconstructed=True, winner_reconstructed=True, metrics=metrics)
    return validation


def failure_kind(error: BaseException, stderr: str = "") -> str:
    text = f"{error} {stderr}".lower()
    if isinstance(error, ScoreWinnerMismatch): return "score_winner_mismatch"
    if "outofmemory" in text or "out of memory" in text or "oom" in text: return "oom"
    if isinstance(error, subprocess.TimeoutExpired): return "timeout"
    if isinstance(error, (ValueError, FileNotFoundError)): return "validation_failure"
    return "abnormal_exit"


def quarantine(path: Path, namespace: str, prefix: str) -> None:
    root = protocol.RESULTS_ROOT / namespace / "quarantine";root.mkdir(parents=True, exist_ok=True)
    os.replace(path, root / f"{prefix}-{time.time_ns()}")


def artifact_manifest(final_dir: Path, task: protocol.Task, validation: dict) -> dict[str, str]:
    trial = final_dir / f"{task.experiment_id}-{task.game_index:04d}.trl";result = final_dir / "result.csv";validated = final_dir / "validation.json"
    return {"trial": trial.relative_to(protocol.REPO_ROOT).as_posix(), "trial_sha256": protocol.sha256(trial), "result": result.relative_to(protocol.REPO_ROOT).as_posix(), "result_sha256": protocol.sha256(result), "validation": validated.relative_to(protocol.REPO_ROOT).as_posix(), "validation_sha256": protocol.sha256(validated), "raw_trial_sha256": validation["raw_trial_sha256"]}


def run_task(task: protocol.Task, all_tasks: list[protocol.Task], config_hash: str, jar: Path, game: Path, config: dict, stop: threading.Event) -> str:
    if stop.is_set() or protocol.PRODUCTION_BLOCK_PATH.exists(): return "blocked"
    final_dir = protocol.RESULTS_ROOT / task.namespace / "tasks" / task.task_id
    max_attempts = int(config["operational_parameters"]["max_attempts"]);timeout = int(config["operational_parameters"]["timeout_seconds_per_game"]);heap = config["operational_parameters"]["jvm_max_heap_by_budget"][str(task.iteration_limit)]
    with protocol.locked_manifest(task.namespace, all_tasks, config_hash) as manifest:
        row = manifest["tasks"][task.task_id]
        if row["state"] == "completed" or row["state"] in protocol.TRANSIENT_STATES:return "skipped"
        if int(row["attempts"]) >= max_attempts:return "attempts-exhausted"
        row.update(state="running", attempts=int(row["attempts"])+1, error=None, run_owner={"pid": os.getpid(), "runner_id": protocol.opaque_runner_id(), "command_marker": "issue-112/scripts/run_experiments.py", "started_at_utc": protocol.utc_now()}, updated_at_utc=protocol.utc_now())
        row.setdefault("events", []).append({"at_utc": row["updated_at_utc"], "state": "running", "attempt": row["attempts"]})
    temporary_root = protocol.RESULTS_ROOT / task.namespace / ".tmp";temporary_root.mkdir(parents=True, exist_ok=True)
    task_dir = Path(tempfile.mkdtemp(prefix=f"{task.task_id}-", dir=temporary_root));started=time.monotonic();stderr="";peak=None
    try:
        raw_trial = task_dir / "raw" / f"{task.experiment_id}-{task.game_index:04d}.trl";raw_trial.parent.mkdir(parents=True)
        command=["java",f"-Xmx{heap}","-cp",str(jar),str(RUNNER),str(game),task.experiment_id,"UCT",str(task.seed),str(task.iteration_limit),str(task_dir/"result.csv"),str(raw_trial),str(task.game_index),str(game)]
        def started_java(pid: int) -> None:
            protocol.update_task(task.namespace,all_tasks,config_hash,task.task_id,"running",run_owner={"pid":os.getpid(),"runner_id":protocol.opaque_runner_id(),"command_marker":"issue-112/scripts/run_experiments.py","java_pid":pid,"java_command_marker":"Heitan4x4CorrectedExperiment.java"})
        completed,peak=timed_java(command,timeout,started_java);stderr=completed.stderr
        if completed.returncode:
            message=stderr.strip() or completed.stdout.strip()
            if any(marker in message.lower() for marker in MISMATCH_MARKERS):raise ScoreWinnerMismatch(message)
            raise RuntimeError(f"Java exit {completed.returncode}: {message}")
        protocol.update_task(task.namespace,all_tasks,config_hash,task.task_id,"generated",peak_rss_bytes=peak)
        validation=validate_generated(task,task_dir,jar,game,config);protocol.atomic_write_json(task_dir/"validation.json",validation)
        final_dir.parent.mkdir(parents=True,exist_ok=True)
        if final_dir.exists():quarantine(final_dir,task.namespace,task.task_id)
        os.replace(task_dir,final_dir);artifacts=artifact_manifest(final_dir,task,validation)
        protocol.update_task(task.namespace,all_tasks,config_hash,task.task_id,"completed",error=None,failure_kind=None,run_owner=None,completed_at_utc=protocol.utc_now(),elapsed_seconds=round(time.monotonic()-started,3),peak_rss_bytes=peak,validation=validation,artifacts=artifacts)
        return "completed"
    except Exception as error:
        kind=failure_kind(error,stderr)
        if task_dir.exists():quarantine(task_dir,task.namespace,f"{task.task_id}-attempt")
        safe_error=protocol.sanitize_error(error)
        protocol.update_task(task.namespace,all_tasks,config_hash,task.task_id,"corrupt" if kind in {"validation_failure","score_winner_mismatch"} else "failed",error=safe_error,failure_kind=kind,run_owner=None,elapsed_seconds=round(time.monotonic()-started,3),peak_rss_bytes=peak)
        if kind=="score_winner_mismatch":
            protocol.block_production(task,safe_error);stop.set()
        return kind


def require_persistent_execution() -> None:
    if not os.environ.get("TMUX"):raise ValueError("production must run inside tmux")
    if os.environ.get("HEITAN112_CAFFEINATE")!="1":raise ValueError("production must run under caffeinate -i with HEITAN112_CAFFEINATE=1")
    if not os.environ.get("HEITAN112_RUNNER_ID"):raise ValueError("production requires an opaque HEITAN112_RUNNER_ID")


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("namespace",choices=("pilot","production"));parser.add_argument("--budget",type=int,choices=(10000,30000,100000));parser.add_argument("--ludii-jar",default=os.environ.get("LUDII_JAR",""));parser.add_argument("--workers",type=int);args=parser.parse_args()
    config=protocol.load_config();protocol.validate_config(config)
    lock=None
    if args.namespace=="production":
        if args.budget is None:parser.error("production requires --budget")
        require_persistent_execution();lock=protocol.require_production_gate(config,args.budget)
    all_tasks=protocol.tasks_from_config(config,args.namespace);tasks=[task for task in all_tasks if args.budget is None or task.iteration_limit==args.budget]
    jar=Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():parser.error("pass --ludii-jar or set LUDII_JAR to an existing file")
    if lock is not None and protocol.sha256(jar)!=lock["ludii_jar_sha256"]:raise ValueError("Ludii JAR differs from protocol lock")
    game=protocol.REPO_ROOT/config["game"];config_hash=protocol.sha256(protocol.CONFIG_PATH);manifest=protocol.reconcile_manifest(args.namespace,all_tasks,config_hash)
    candidates=[task for task in tasks if manifest["tasks"][task.task_id]["state"] in set(config["operational_parameters"]["retry_states"])]
    workers=args.workers or int(config["operational_parameters"]["worker_count_by_budget"][str(args.budget or 10000)])
    stop=threading.Event();results={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(run_task,task,all_tasks,config_hash,jar,game,config,stop):task for task in candidates}
        for future in concurrent.futures.as_completed(futures):
            task=futures[future]
            try:results[task.task_id]=future.result()
            except concurrent.futures.CancelledError:results[task.task_id]="blocked"
            print(f"{task.task_id}: {results[task.task_id]}",flush=True)
            if stop.is_set():
                for pending in futures:pending.cancel()
    final=protocol.load_json(protocol.manifest_path(args.namespace));counts={}
    for task in tasks:counts[final["tasks"][task.task_id]["state"]]=counts.get(final["tasks"][task.task_id]["state"],0)+1
    print(json.dumps({"budget":args.budget,"states":counts},sort_keys=True))
    if protocol.PRODUCTION_BLOCK_PATH.exists():raise SystemExit("production blocked by score/winner mismatch")
    if any(final["tasks"][task.task_id]["state"]!="completed" for task in tasks):raise SystemExit("some tasks remain incomplete; rerun unchanged command to resume")


if __name__=="__main__":main()
