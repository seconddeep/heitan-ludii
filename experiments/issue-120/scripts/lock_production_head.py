#!/usr/bin/env python3
"""Lock the already-committed clean HEAD before Issue 120 production starts."""

from __future__ import annotations

import subprocess

import protocol


def main() -> None:
    if not protocol.LOCK_PATH.is_file() or not protocol.SOURCE_LOCK_PATH.is_file():
        raise ValueError("freeze protocol and source inputs before locking production HEAD")
    if protocol.PRODUCTION_HEAD_LOCK_PATH.exists():
        raise ValueError("production HEAD is already locked")
    if protocol.manifest_path("production").exists():
        raise ValueError("production manifest already exists")
    lock = protocol.load_json(protocol.LOCK_PATH)
    if lock.get("config_sha256") != protocol.sha256(protocol.CONFIG_PATH):
        raise ValueError("config differs from protocol lock")
    if lock.get("source_lock_sha256") != protocol.sha256(protocol.SOURCE_LOCK_PATH):
        raise ValueError("source lock differs from protocol lock")
    for args in (("diff", "--quiet"), ("diff", "--cached", "--quiet")):
        if subprocess.run(["git", *args], cwd=protocol.REPO_ROOT, check=False).returncode:
            raise ValueError("tracked files differ from HEAD")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=protocol.REPO_ROOT, text=True, capture_output=True, check=True,
    ).stdout.splitlines()
    if status:
        raise ValueError(f"worktree must be clean before production HEAD lock: {status}")
    head = protocol.git("rev-parse", "HEAD")
    protocol.atomic_write_json(protocol.PRODUCTION_HEAD_LOCK_PATH, {
        "schema_version": 1,
        "production_head_commit": head,
        "locked_at_utc": protocol.utc_now(),
        "protocol_lock_sha256": protocol.sha256(protocol.LOCK_PATH),
        "policy": lock["production_head_lock_policy"],
    })
    print(f"locked Issue 120 production HEAD: {head}")


if __name__ == "__main__":
    main()
