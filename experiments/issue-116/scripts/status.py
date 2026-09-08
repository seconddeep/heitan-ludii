#!/usr/bin/env python3
import json
import protocol

for namespace in ("pilot","measured"):
    path=protocol.manifest_path(namespace)
    if not path.exists():print(f"{namespace}: not started");continue
    counts={}
    for row in protocol.load_json(path)["tasks"].values():counts[row["state"]]=counts.get(row["state"],0)+1
    print(f"{namespace}: {json.dumps(counts,sort_keys=True)}")
