#!/usr/bin/env python3
"""Run Issue #44 tests and verify deterministic regeneration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
RESULTS = ISSUE_ROOT / "results"
CONFIG = ISSUE_ROOT / "config.json"
README = ISSUE_ROOT / "README.md"
ANALYZER = SCRIPT.parent / "analyze_prediction.py"
TESTS = SCRIPT.parent / "test_analysis.py"
REPORT = REPO_ROOT / "experiments" / "issue-44.md"
ENVIRONMENT = RESULTS / "environment.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def deterministic_outputs() -> list[Path]:
    return sorted(
        [path for path in RESULTS.rglob("*") if path.is_file() and path != ENVIRONMENT]
        + [REPORT]
    )


def output_hashes() -> dict[str, str]:
    return {
        path.relative_to(REPO_ROOT).as_posix(): sha256(path)
        for path in deterministic_outputs()
    }


def main() -> None:
    started = time.time()
    subprocess.run(
        ["python3", "-m", "unittest", "discover", "-s", str(SCRIPT.parent), "-p", "test_*.py"],
        cwd=REPO_ROOT, check=True,
    )
    subprocess.run(["python3", str(ANALYZER)], cwd=REPO_ROOT, check=True)
    first = output_hashes()
    subprocess.run(["python3", str(ANALYZER)], cwd=REPO_ROOT, check=True)
    second = output_hashes()
    if first != second:
        changed = sorted(
            key for key in set(first) | set(second)
            if first.get(key) != second.get(key)
        )
        raise ValueError(f"deterministic regeneration mismatch: {changed}")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    analysis_result = json.loads((RESULTS / "analysis.json").read_text(encoding="utf-8"))
    environment = {
        "schema_version": 1,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - started, 3),
        "git_commit": commit,
        "python": platform.python_version(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "external_python_dependencies": [],
        "new_uct_self_play_games": 0,
        "config_sha256": sha256(CONFIG),
        "readme_sha256": sha256(README),
        "analyzer_sha256": sha256(ANALYZER),
        "runner_sha256": sha256(SCRIPT),
        "test_script_sha256": sha256(TESTS),
        "report_sha256": sha256(REPORT),
        "deterministic_regeneration_verified": True,
        "deterministic_output_hashes": second,
        "analysis_integrity": analysis_result["integrity"],
    }
    ENVIRONMENT.write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
