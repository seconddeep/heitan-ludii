#!/usr/bin/env python3
"""Mechanical feasibility classification and outcome-free final report."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics

import protocol


def condition(config: dict, board: str, budget: int, write: bool=True) -> dict:
    manifest=protocol.load_json(protocol.manifest_path("measured"));selected=[row for row in manifest["tasks"].values() if row["board"]==board and int(row["iteration_limit"])==budget]
    if len(selected)!=3:raise ValueError("condition must contain exactly three fixed identities")
    if all(row["state"]=="not_attempted" for row in selected):classification="not attempted"
    else:
        completed=[row for row in selected if row["state"]=="completed" and row["replay_validation_status"]=="validated"]
        op=config["operational_parameters"];ram=int(protocol.load_json(protocol.LOCK_PATH)["environment"]["physical_ram_bytes"])
        hard=any(row["failure_classification"] in config["classification"]["hard_safety_conditions"] for row in selected)
        hard=hard or any(row["peak_rss_bytes"] is not None and int(row["peak_rss_bytes"])/ram>=float(op["hard_rss_fraction_of_physical_ram"]) for row in selected)
        soft=any(float(row["elapsed_seconds"])>float(op["soft_runtime_seconds_per_game"]) for row in completed)
        soft=soft or any(row["peak_rss_bytes"] is not None and int(row["peak_rss_bytes"])/ram>=float(op["soft_rss_fraction_of_physical_ram"]) for row in completed)
        classification="infeasible in current environment" if len(completed)<3 or hard else "borderline" if soft else "feasible"
    completed=[row for row in selected if row["state"]=="completed" and row["replay_validation_status"]=="validated"]
    elapsed=[float(row["elapsed_seconds"]) for row in completed];rss=[int(row["peak_rss_bytes"]) for row in completed if row["peak_rss_bytes"] is not None]
    result={"schema_version":1,"board":board,"uct_iterations":budget,"classification":classification,"planned_games":3,
            "validated_completions":len(completed),"median_elapsed_seconds":statistics.median(elapsed) if elapsed else None,
            "maximum_elapsed_seconds":max(elapsed) if elapsed else None,"median_peak_rss_bytes":statistics.median(rss) if rss else None,
            "maximum_peak_rss_bytes":max(rss) if rss else None,"failed_tasks":sum(row["state"]=="failed" for row in selected),
            "not_attempted_tasks":sum(row["state"]=="not_attempted" for row in selected),"manual_override":False}
    if write:
        path=protocol.RESULTS_ROOT/"measured"/"conditions"/f"{board}-uct-{budget:05d}.json";protocol.atomic_json(path,result)
    return result


def fmt_seconds(value):return "—" if value is None else f"{value/60:.1f} min"
def fmt_rss(value):return "—" if value is None else f"{value/1024**3:.2f} GiB"


def final_report(config: dict) -> None:
    results=[]
    for board in config["boards"]:
        for budget in config["uct_budgets"]:results.append(condition(config,board,int(budget)))
    final=protocol.RESULTS_ROOT/"final";final.mkdir(parents=True,exist_ok=True)
    fields=list(results[0]);
    with (final/"feasibility.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(results)
    ceilings=[]
    for board in config["boards"]:
        board_rows=[row for row in results if row["board"]==board]
        technical=max((row["uct_iterations"] for row in board_rows if row["classification"] in {"feasible","borderline"}),default=None)
        practical=max((row["uct_iterations"] for row in board_rows if row["classification"]=="feasible"),default=None)
        ceilings.append({"board":board,"technically_completable_max_uct":technical,"recommended_repeated_production_max_uct":practical})
    with (final/"recommended-ceilings.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(ceilings[0]));writer.writeheader();writer.writerows(ceilings)
    scaling=[]
    for board in config["boards"]:
        rows=[row for row in results if row["board"]==board and row["median_elapsed_seconds"] is not None]
        for before,after in zip(rows,rows[1:]):
            scaling.append({"dimension":"uct_at_fixed_board","board_or_uct":board,"from":before["uct_iterations"],"to":after["uct_iterations"],
                            "median_elapsed_ratio":after["median_elapsed_seconds"]/before["median_elapsed_seconds"],
                            "median_peak_rss_ratio":after["median_peak_rss_bytes"]/before["median_peak_rss_bytes"] if before["median_peak_rss_bytes"] and after["median_peak_rss_bytes"] else None})
    for budget in config["uct_budgets"]:
        rows=[row for row in results if row["uct_iterations"]==budget and row["median_elapsed_seconds"] is not None]
        for before,after in zip(rows,rows[1:]):
            scaling.append({"dimension":"board_at_fixed_uct","board_or_uct":budget,"from":before["board"],"to":after["board"],
                            "median_elapsed_ratio":after["median_elapsed_seconds"]/before["median_elapsed_seconds"],
                            "median_peak_rss_ratio":after["median_peak_rss_bytes"]/before["median_peak_rss_bytes"] if before["median_peak_rss_bytes"] and after["median_peak_rss_bytes"] else None})
    with (final/"scaling.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=["dimension","board_or_uct","from","to","median_elapsed_ratio","median_peak_rss_ratio"]);writer.writeheader();writer.writerows(scaling)
    lines=["# Issue 116: larger-board UCT execution benchmark","","This report measures execution capability only. It does not inspect or summarize game outcomes.","","## Feasibility map","","| Board | 1k | 3k | 10k | 30k |","|---|---|---|---|---|"]
    for board in config["boards"]:
        cells=[]
        for row in [item for item in results if item["board"]==board]:cells.append(f"{row['classification']} ({row['validated_completions']}/3; median {fmt_seconds(row['median_elapsed_seconds'])}; max RSS {fmt_rss(row['maximum_peak_rss_bytes'])})")
        lines.append(f"| {board} | "+" | ".join(cells)+" |")
    lines += ["","## Recommended production ceilings","","| Board | Technically completable | Repeated-production recommendation |","|---|---:|---:|"]
    for row in ceilings:lines.append(f"| {row['board']} | {row['technically_completable_max_uct'] or 'none'} | {row['recommended_repeated_production_max_uct'] or 'none'} |")
    lines += ["","Peak RSS relative to physical RAM supplies the machine-memory gate. JVM `-Xmx` and GC evidence are reported separately and are not treated as the same ratio.",""]
    (protocol.ISSUE_ROOT.parent/"issue-116.md").write_text("\n".join(lines),encoding="utf-8")
    analysis={"schema_version":1,"game_outcomes_inspected":False,"conditions":results,"recommended_ceilings":ceilings,"scaling":scaling,
              "runtime_scaling_note":"Use adjacent median elapsed-time ratios; no linearity is assumed.","memory_scaling_note":"Use adjacent median peak-RSS ratios separately from JVM heap configuration."}
    protocol.atomic_json(final/"analysis.json",analysis)
    lock=protocol.load_json(protocol.LOCK_PATH)
    environment={"schema_version":1,**lock["environment"],"jvm_xmx":config["operational_parameters"]["jvm_xmx"],
                 "gc_logging":config["operational_parameters"]["gc_logging"],"worker_count":1,"game_outcomes_inspected":False}
    protocol.atomic_json(final/"environment.json",environment)
    outputs={path.relative_to(protocol.REPO_ROOT).as_posix():protocol.sha256(path) for path in sorted(final.iterdir()) if path.is_file() and path.name!="artifact-manifest.json"}
    outputs[(protocol.ISSUE_ROOT.parent/"issue-116.md").relative_to(protocol.REPO_ROOT).as_posix()]=protocol.sha256(protocol.ISSUE_ROOT.parent/"issue-116.md")
    protocol.atomic_json(final/"artifact-manifest.json",{"schema_version":1,"inputs":{"config":protocol.sha256(protocol.CONFIG_PATH),"protocol_lock":protocol.sha256(protocol.LOCK_PATH),"source_lock":protocol.sha256(protocol.SOURCE_LOCK_PATH),"measured_manifest":protocol.sha256(protocol.manifest_path("measured"))},"outputs":outputs})


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--condition",action="store_true");parser.add_argument("--final",action="store_true");parser.add_argument("--board",choices=protocol.BOARDS);parser.add_argument("--budget",type=int,choices=protocol.BUDGETS);args=parser.parse_args()
    config=protocol.load_config()
    if args.condition:
        if not args.board or args.budget is None:parser.error("--condition requires board and budget")
        result=condition(config,args.board,args.budget);print(json.dumps(result,sort_keys=True))
    elif args.final:final_report(config);print("Issue #116 outcome-blind report generated")
    else:parser.error("choose --condition or --final")


if __name__=="__main__":main()
