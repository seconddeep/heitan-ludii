#!/usr/bin/env python3
"""Run Issue #43 analysis and record reproducibility metadata."""

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
ANALYZER = SCRIPT.parent / "analyze_reversals.py"
TESTS = SCRIPT.parent / "test_analysis.py"
REPORT = REPO_ROOT / "experiments" / "issue-43.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    started = time.time()
    subprocess.run(["python3", str(ANALYZER)], cwd=REPO_ROOT, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    analysis = json.loads((RESULTS / "analysis.json").read_text(encoding="utf-8"))
    environment = {
        "schema_version": 1,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - started, 3),
        "git_commit": commit,
        "python": platform.python_version(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "new_uct_self_play_games": 0,
        "config_sha256": sha256(CONFIG),
        "readme_sha256": sha256(README),
        "analyzer_sha256": sha256(ANALYZER),
        "run_script_sha256": sha256(SCRIPT),
        "test_script_sha256": sha256(TESTS),
        "report_sha256": sha256(REPORT),
        "source_files": json.loads((RESULTS / "analysis.json").read_text(encoding="utf-8"))["integrity"]["source_files_hashed"],
        "analysis_integrity": analysis["integrity"],
    }
    (RESULTS / "environment.json").write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
