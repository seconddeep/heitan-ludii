#!/usr/bin/env python3
"""Reject identifying or secret-looking text from publishable Issue #116 artifacts."""

from __future__ import annotations
import json
from pathlib import Path
import re
import protocol

PATTERNS={"absolute_user_path":re.compile(r"/Users/|[A-Za-z]:\\\\Users\\\\"),"hostname":re.compile(r'"hostname"\s*:'),
          "hardware_identifier":re.compile(r'"(?:serial_number|hardware_uuid|provisioning_udid)"\s*:',re.I),
          "secret":re.compile(r'"(?:api[_-]?key|access[_-]?token|private[_-]?key|password)"\s*:',re.I)}
targets=[protocol.ISSUE_ROOT/"README.md",protocol.ISSUE_ROOT/"config.json",protocol.LOCK_PATH,protocol.SOURCE_LOCK_PATH,
         protocol.RESULTS_ROOT/"final"/"analysis.json",protocol.RESULTS_ROOT/"final"/"feasibility.csv",
         protocol.RESULTS_ROOT/"final"/"recommended-ceilings.csv",protocol.ISSUE_ROOT.parent/"issue-116.md"]
findings=[]
for path in targets:
    if not path.is_file():continue
    text=path.read_text(encoding="utf-8",errors="replace")
    for name,pattern in PATTERNS.items():
        if pattern.search(text):findings.append({"file":path.relative_to(protocol.REPO_ROOT).as_posix(),"kind":name})
result={"schema_version":1,"status":"passed" if not findings else "failed","findings":findings}
protocol.atomic_json(protocol.RESULTS_ROOT/"final"/"public-safety-audit.json",result)
if findings:raise SystemExit(json.dumps(result,indent=2))
print("Issue #116 public safety audit passed")
