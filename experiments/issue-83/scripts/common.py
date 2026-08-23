#!/usr/bin/env python3
"""Shared paths and deterministic file helpers for Issue #83."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable


SCRIPT = Path(__file__).resolve()
ISSUE_ROOT = SCRIPT.parent.parent
REPO_ROOT = ISSUE_ROOT.parent.parent
CONFIG_PATH = ISSUE_ROOT / "config.json"
PROTOCOL_LOCK = ISSUE_ROOT / "protocol-lock.json"
SOURCE_LOCK = ISSUE_ROOT / "source-lock.json"
FINAL = ISSUE_ROOT / "results" / "final"
REPORT = REPO_ROOT / "experiments" / "issue-83.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_csv(path: Path, rows: Iterable[dict[str, object]], fields: list[str] | None = None) -> None:
    values = list(rows)
    if fields is None:
        fields = list(values[0]) if values else []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)
