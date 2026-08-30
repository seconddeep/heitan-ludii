#!/usr/bin/env python3
"""Audit Issue #108 publishable artifacts and branch commit metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

import protocol


PATTERNS={
    "user_home_path":re.compile(r"/(?:Users|home)/[^/\s]+/"),
    "private_key":re.compile(r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY"),
    "github_token":re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "openai_token":re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "aws_access_key":re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "secret_assignment":re.compile(r"(?i)\b(?:password|api[_-]?key|access[_-]?token|client[_-]?secret)\s*=\s*[^\s$][^\s]*"),
    "attachment_path":re.compile(r"/\.codex/attachments/"),
}


def publishable_files() -> list[Path]:
    completed=subprocess.run(["git","ls-files","--cached","--others","--exclude-standard","experiments/issue-108","experiments/issue-108.md"],cwd=protocol.REPO_ROOT,text=True,capture_output=True,check=True)
    return [protocol.REPO_ROOT/line for line in completed.stdout.splitlines() if line and (protocol.REPO_ROOT/line).is_file() and "/results/" not in line]


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--base",default="origin/main");args=parser.parse_args();findings=[]
    for path in publishable_files():
        try:text=path.read_text(encoding="utf-8")
        except UnicodeDecodeError:continue
        for name,pattern in PATTERNS.items():
            for match in pattern.finditer(text):findings.append({"file":path.relative_to(protocol.REPO_ROOT).as_posix(),"kind":name,"line":text.count("\n",0,match.start())+1})
        if path.suffix==".trl" and text.splitlines() and text.splitlines()[0]!="game=games/Heitan.lud":findings.append({"file":path.relative_to(protocol.REPO_ROOT).as_posix(),"kind":"unnormalized_trial_game_path","line":1})
    metadata=subprocess.run(["git","log",f"{args.base}..HEAD","--format=%H%x09%an%x09%ae%x09%cn%x09%ce"],cwd=protocol.REPO_ROOT,text=True,capture_output=True,check=True).stdout.splitlines();bad_metadata=[]
    for line in metadata:
        commit,author_name,author_email,committer_name,committer_email=line.split("\t")
        for role,name,email in (("author",author_name,author_email),("committer",committer_name,committer_email)):
            if email.endswith(".local") or "localhost" in email or "@local" in email:bad_metadata.append({"commit":commit,"role":role,"name":name,"email":email})
    report={"schema_version":1,"files_scanned":len(publishable_files()),"content_findings":findings,"commit_metadata_findings":bad_metadata,"passed":not findings and not bad_metadata,"limitations":["pattern-based scanning cannot prove absence of every secret","raw trials are intentionally excluded from publication and third-party replay depends on normalized trials"]}
    output=protocol.RESULTS_ROOT/"final"/"public-safety-audit.json";protocol.atomic_write_json(output,report);print(json.dumps(report,indent=2,sort_keys=True))
    if not report["passed"]:raise SystemExit("public safety audit failed")


if __name__=="__main__":main()
