#!/usr/bin/env python3
"""Replay Issue #32 trials with Ludii and run the Issue #37 analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
CONFIG_PATH = ISSUE_ROOT / "config.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ludii-jar", default=os.environ.get("LUDII_JAR", ""))
    args = parser.parse_args()
    jar = Path(args.ludii_jar).expanduser().resolve()
    if not jar.is_file():
        parser.error("pass --ludii-jar or set LUDII_JAR to an existing file")

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["ludii_version"] != "1.3.14":
        raise ValueError("this workflow is validated against Ludii 1.3.14")
    game = REPO_ROOT / config["game"]
    trials = REPO_ROOT / config["source"]["trial_root"]
    experiment_ids = ",".join(item["id"] for item in config["source"]["experiments"])
    results = ISSUE_ROOT / "results"
    raw = results / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    runner = SCRIPT.parent / "HeitanSupplyReplay.java"
    analyzer = SCRIPT.parent / "analyze_results.py"

    started = time.time()
    subprocess.run([
        "java", "-cp", str(jar), str(runner), str(game), str(trials), experiment_ids,
        str(raw / "replay-summary.csv"), str(raw / "placements.csv"),
        str(raw / "supply-turn-states.csv"), str(raw / "objective-turn-states.csv"),
    ], cwd=REPO_ROOT, check=True)
    subprocess.run(["python3", str(analyzer)], cwd=REPO_ROOT, check=True)

    java_version = subprocess.run(
        ["java", "--version"], text=True, capture_output=True, check=True
    ).stdout.splitlines()[0]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    source_index = results / "source-trials.csv"
    environment = {
        "schema_version": 1,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - started, 3),
        "config": CONFIG_PATH.relative_to(REPO_ROOT).as_posix(),
        "config_sha256": sha256(CONFIG_PATH),
        "game": config["game"], "game_sha256": sha256(game),
        "replay_runner": runner.relative_to(REPO_ROOT).as_posix(),
        "replay_runner_sha256": sha256(runner),
        "run_script_sha256": sha256(SCRIPT),
        "analysis_script_sha256": sha256(analyzer),
        "source_trial_index_sha256": sha256(source_index),
        "git_commit": commit, "ludii_version": config["ludii_version"],
        "ludii_jar_sha256": sha256(jar), "java": java_version,
        "python": platform.python_version(), "os": platform.platform(),
        "machine": platform.machine(),
    }
    (results / "environment.json").write_text(
        json.dumps(environment, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
