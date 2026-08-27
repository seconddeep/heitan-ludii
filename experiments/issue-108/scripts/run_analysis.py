#!/usr/bin/env python3
"""Analyze corrected Issue #108 production against frozen #82/#105 inputs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import platform
import random
from typing import Iterable

import protocol


FINAL=protocol.RESULTS_ROOT/"final";REPORT=protocol.REPO_ROOT/"experiments/issue-108.md"


def read_csv(path: Path) -> list[dict[str,str]]:
    with path.open(newline="",encoding="utf-8-sig") as handle:return list(csv.DictReader(handle))


def write_csv(path: Path,rows: Iterable[dict[str,object]],fields: list[str]) -> None:
    values=list(rows);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,lineterminator="\n");writer.writeheader();writer.writerows(values)


def percentile(values: list[float],p: float) -> float:
    ordered=sorted(values)
    if not ordered:raise ValueError("percentile requires values")
    location=(len(ordered)-1)*p;low,high=math.floor(location),math.ceil(location)
    return ordered[low] if low==high else ordered[low]*(high-location)+ordered[high]*(location-low)


def wilson(successes: int,total: int,z: float=1.959963984540054) -> tuple[float|None,float|None]:
    if not total:return None,None
    p=successes/total;denominator=1+z*z/total;centre=(p+z*z/(2*total))/denominator;radius=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/denominator
    return max(0.0,centre-radius),min(1.0,centre+radius)


def bootstrap_rate(values: list[int],samples: int,seed: int) -> tuple[float|None,float|None]:
    if not values:return None,None
    rng=random.Random(seed);estimates=[sum(rng.choice(values) for _ in values)/len(values) for _ in range(samples)]
    return percentile(estimates,.025),percentile(estimates,.975)


def bootstrap_difference(a: list[int],b: list[int],samples: int,seed: int) -> tuple[float|None,float|None]:
    if not a or not b:return None,None
    rng=random.Random(seed);estimates=[]
    for _ in range(samples):estimates.append(sum(rng.choice(a) for _ in a)/len(a)-sum(rng.choice(b) for _ in b)/len(b))
    return percentile(estimates,.025),percentile(estimates,.975)


def bootstrap_did(a: list[int],b: list[int],c: list[int],d: list[int],samples: int,seed: int) -> tuple[float|None,float|None]:
    """Return (rate(a)-rate(b))-(rate(c)-rate(d)); resample all four independently."""
    if not all((a,b,c,d)):return None,None
    rng=random.Random(seed);estimates=[]
    for _ in range(samples):
        rates=[sum(rng.choice(values) for _ in values)/len(values) for values in (a,b,c,d)]
        estimates.append((rates[0]-rates[1])-(rates[2]-rates[3]))
    return percentile(estimates,.025),percentile(estimates,.975)


def classify_stability(values: list[float],counts: list[int],policy: dict) -> tuple[str,dict[str,object]]:
    if len(values)!=3 or len(counts)!=3 or any(value<int(policy["minimum_games_per_primary_budget"]) for value in counts):return "unresolved",{"reason":"insufficient primary sample"}
    first,second=values[1]-values[0],values[2]-values[1];evidence={"delta_30k_minus_10k":first,"delta_100k_minus_30k":second};epsilon=1e-12
    if first*second<0 and abs(first)>float(policy["non_monotonic_material_delta_min"])+epsilon and abs(second)>float(policy["non_monotonic_material_delta_min"])+epsilon:return "non-monotonic",evidence
    if abs(first)<=float(policy["stable_absolute_delta_max"])+epsilon and abs(second)<=float(policy["stable_absolute_delta_max"])+epsilon:return "stable / converged-looking",evidence
    if first*second>=0 and abs(second)<abs(first)-epsilon and abs(second)<=float(policy["directionally_stabilizing_latest_delta_max"])+epsilon:return "directionally stabilizing",evidence
    return "unresolved",evidence


def classify_drop(primary_ci: tuple[float|None,float|None],did_ci: tuple[float|None,float|None],counts: list[int],policy: dict) -> str:
    minimum=int(policy["minimum_games_per_required_sample"])
    if any(value<minimum for value in counts) or None in primary_ci or None in did_ci:return "unresolved"
    low,high=primary_ci;did_low,_=did_ci
    assert low is not None and high is not None and did_low is not None
    if did_low>0:return "weakens"
    if high<0:return "persists"
    if low>=0:return "disappears"
    return "unresolved"


def verify_locks(config: dict) -> tuple[dict,dict,dict]:
    if config["protocol_status"]!="locked" or not protocol.FINALIZATION_PATH.is_file():raise ValueError("locked and finalized production is required")
    lock=protocol.load_json(protocol.LOCK_PATH);source_lock=protocol.load_json(protocol.SOURCE_LOCK_PATH);finalization=protocol.load_json(protocol.FINALIZATION_PATH)
    if lock["config_sha256"]!=protocol.sha256(protocol.CONFIG_PATH) or lock["source_lock_sha256"]!=protocol.sha256(protocol.SOURCE_LOCK_PATH):raise ValueError("protocol/source lock changed")
    for entry in source_lock["files"]:
        path=protocol.REPO_ROOT/entry["path"]
        if not path.is_file() or protocol.sha256(path)!=entry["sha256"]:raise ValueError(f"historical source differs: {entry['path']}")
    manifest=protocol.manifest_path("production")
    if finalization["manifest_sha256"]!=protocol.sha256(manifest):raise ValueError("production manifest changed after finalization")
    return lock,source_lock,finalization


def completed(config: dict) -> tuple[list[dict[str,str]],dict[tuple[int,int],Path],dict]:
    tasks=protocol.tasks_from_config(config,"production");manifest=protocol.load_json(protocol.manifest_path("production"));rows=[];state_paths={};seen=set();seeds=set()
    for task in tasks:
        entry=manifest["tasks"][task.task_id]
        if entry["state"]!="completed":continue
        error=protocol.artifact_error(entry)
        if error:raise ValueError(error)
        row=read_csv(protocol.REPO_ROOT/entry["artifacts"]["result"])
        if len(row)!=1:raise ValueError("completed result is not one row")
        key=(task.iteration_limit,task.game_index)
        if key in seen or task.seed in seeds:raise ValueError("duplicate game key or seed")
        seen.add(key);seeds.add(task.seed);rows.append(row[0]);state_paths[key]=(protocol.REPO_ROOT/entry["artifacts"]["validation"]).parent/"validation-raw"/"normalized-trial"
    return rows,state_paths,manifest


def historical_samples(config: dict) -> dict[int,dict[str,list[int]]]:
    rows=read_csv(protocol.REPO_ROOT/config["historical_sources"]["issue_105_per_game"]);result={budget:{"original_p1":[],"original_draw":[],"rescored_p1":[],"rescored_draw":[]} for budget in config["primary_budgets"]}
    for row in rows:
        if row["source_issue"]!="82" or row["board"]!="3x3" or int(row["iteration_limit"]) not in result or row["status"]!="resolved":continue
        budget=int(row["iteration_limit"]);old=int(row["recorded_winner"]);new=int(row["corrected_winner"])
        result[budget]["original_p1"].append(int(old==1));result[budget]["original_draw"].append(int(old==0));result[budget]["rescored_p1"].append(int(new==1));result[budget]["rescored_draw"].append(int(new==0))
    if any(any(len(values)!=100 for values in result[budget].values()) for budget in result):raise ValueError("#105 does not provide 100 resolved #82 games per budget")
    return result


def rate(values: list[int]) -> float|None:return sum(values)/len(values) if values else None
def optional(value: float|None) -> str|float:return "" if value is None else round(value,6)


def primary_outputs(config: dict,rows: list[dict[str,str]],manifest: dict) -> dict:
    samples=int(config["analysis"]["bootstrap_samples"]);seed=int(config["analysis"]["bootstrap_seed"]);historical=historical_samples(config);binary={};balance=[]
    for offset,budget in enumerate(config["primary_budgets"]):
        winners=[int(row["winner"]) for row in rows if int(row["iteration_limit"])==budget];p1=[int(value==1) for value in winners];draw=[int(value==0) for value in winners];binary[budget]={"p1":p1,"draw":draw};p1_count=sum(p1);p2_count=winners.count(2);ci=wilson(p1_count,len(winners));boot=bootstrap_rate(p1,samples,seed+offset)
        balance.append({"iteration_limit":budget,"planned_games":100,"validated_games":len(winners),"p1_wins":p1_count,"p2_wins":p2_count,"draws":sum(draw),"p1_win_rate":optional(rate(p1)),"p1_wilson_95_low":optional(ci[0]),"p1_wilson_95_high":optional(ci[1]),"p1_bootstrap_95_low":optional(boot[0]),"p1_bootstrap_95_high":optional(boot[1]),"decisive_games":p1_count+p2_count,"decisive_p1_share":optional(p1_count/(p1_count+p2_count) if p1_count+p2_count else None)})
    write_csv(FINAL/"balance-by-depth.csv",balance,list(balance[0]))
    contrasts=[]
    for offset,(higher,lower) in enumerate(((30000,10000),(100000,30000),(100000,10000))):
        for measure in ("p1","draw"):
            values_high=binary[higher][measure];values_low=binary[lower][measure];ci=bootstrap_difference(values_high,values_low,samples,seed+100+offset*10+(measure=="draw"));contrasts.append({"measure":measure,"contrast":f"corrected {higher//1000}k - corrected {lower//1000}k","higher_budget":higher,"lower_budget":lower,"difference":optional((rate(values_high)-rate(values_low)) if values_high and values_low else None),"bootstrap_95_low":optional(ci[0]),"bootstrap_95_high":optional(ci[1]),"primary_100k_drop":higher==100000 and lower==30000,"secondary_100k_drop":higher==100000 and lower==10000})
    write_csv(FINAL/"corrected-depth-contrasts.csv",contrasts,list(contrasts[0]))
    comparisons=[]
    for offset,budget in enumerate(config["primary_budgets"]):
        for baseline,key in (("issue-82-original","original"),("issue-105-terminal-rescore","rescored")):
            for measure in ("p1","draw"):
                corrected=binary[budget][measure];old=historical[budget][f"{key}_{measure}"];ci=bootstrap_difference(corrected,old,samples,seed+500+offset*20+(10 if key=="rescored" else 0)+(measure=="draw"));comparisons.append({"iteration_limit":budget,"measure":measure,"baseline":baseline,"baseline_rate":optional(rate(old)),"corrected_regenerated_rate":optional(rate(corrected)),"corrected_minus_baseline":optional((rate(corrected)-rate(old)) if corrected else None),"bootstrap_95_low":optional(ci[0]),"bootstrap_95_high":optional(ci[1])})
    write_csv(FINAL/"matched-budget-comparisons.csv",comparisons,list(comparisons[0]))
    did_rows=[]
    for offset,(higher,lower,name) in enumerate(((100000,30000,"100k - 30k"),(100000,10000,"100k - 10k"))):
        for measure in ("p1","draw"):
            a,b=binary[higher][measure],binary[lower][measure];c,d=historical[higher][f"original_{measure}"],historical[lower][f"original_{measure}"];ci=bootstrap_did(a,b,c,d,samples,seed+900+offset*10+(measure=="draw"));point=(rate(a)-rate(b))-(rate(c)-rate(d)) if a and b else None;did_rows.append({"measure":measure,"depth_contrast":name,"corrected_depth_change":optional((rate(a)-rate(b)) if a and b else None),"original_depth_change":optional(rate(c)-rate(d)),"difference_in_differences":optional(point),"bootstrap_95_low":optional(ci[0]),"bootstrap_95_high":optional(ci[1])})
    write_csv(FINAL/"difference-in-differences.csv",did_rows,list(did_rows[0]))
    values=[float(row["p1_win_rate"]) for row in balance if row["p1_win_rate"]!=""];counts=[int(row["validated_games"]) for row in balance];depth_label,evidence=classify_stability(values,counts,config["stability_classification"])
    primary=next(row for row in contrasts if row["measure"]=="p1" and row["primary_100k_drop"]);primary_did=next(row for row in did_rows if row["measure"]=="p1" and row["depth_contrast"]=="100k - 30k")
    as_ci=lambda row:(None if row["bootstrap_95_low"]=="" else float(row["bootstrap_95_low"]),None if row["bootstrap_95_high"]=="" else float(row["bootstrap_95_high"]))
    drop_label=classify_drop(as_ci(primary),as_ci(primary_did),counts+[100,100],config["analysis"]["drop_label_policy"])
    classification={"depth_classification":depth_label,"drop_classification":drop_label,"manual_override":False,**evidence};write_csv(FINAL/"classification.csv",[classification],list(classification))
    failures=[]
    for task in protocol.tasks_from_config(config,"production"):
        entry=manifest["tasks"][task.task_id]
        if entry["state"]!="completed":failures.append({"task_id":task.task_id,"iteration_limit":task.iteration_limit,"game_index":task.game_index,"seed":task.seed,"state":entry["state"],"attempts":entry["attempts"],"failure_kind":entry.get("failure_kind") or "","error":entry.get("error") or ""})
    write_csv(FINAL/"failures.csv",failures,["task_id","iteration_limit","game_index","seed","state","attempts","failure_kind","error"])
    return {"balance":balance,"corrected_depth_contrasts":contrasts,"matched_budget_comparisons":comparisons,"difference_in_differences":did_rows,"classification":classification,"failures":failures}


def corrected_leader(states: list[dict[str,str]]) -> int:
    objectives=[row for row in states if row["point_type"]=="objective"];secured=[sum(int(row["state_at_turn_end"])==value for row in objectives) for value in (3,4)];advantage=[sum(int(row["state_at_turn_end"])==value for row in objectives) for value in (1,2)];pieces=[sum(int(row["p1_at_turn_end"]) for row in objectives if int(row["state_at_turn_end"])==1),sum(int(row["p2_at_turn_end"]) for row in objectives if int(row["state_at_turn_end"])==2)]
    for values in (secured,advantage,pieces):
        if values[0]!=values[1]:return 1 if values[0]>values[1] else 2
    return 0


def central_metrics(placements: list[dict[str,str]],states: list[dict[str,str]]) -> dict[str,object]:
    central={"S11","S12","S21","S22"};p1_placements=[row for row in placements if int(row["mover"])==1 and row["target"] in central];early=[row for row in p1_placements if int(row["turn_number"])<=6];by_turn=defaultdict(list)
    for row in states:by_turn[int(row["turn_number"])].append(row)
    occupied={turn:any(row["point"] in central and int(row["p1_at_turn_end"])>0 for row in values) for turn,values in by_turn.items()};contested={turn:any(row["point"] in central and int(row["p1_at_turn_end"])>0 and int(row["p2_at_turn_end"])>0 for row in values) for turn,values in by_turn.items()};first=min((int(row["turn_number"]) for row in p1_placements),default=None)
    return {"early_central_placement_any":bool(early),"early_central_placement_count":len(early),"first_central_commitment_turn":first,"first_central_commitment_p1_turn":None if first is None else (first+1)//2,"central_occupation_after_p1_turn_1":occupied[1],"central_occupation_after_p1_turn_2":occupied[3],"central_occupation_after_p1_turn_3":occupied[5],"early_central_occupation_turn_count":sum(occupied[turn] for turn in (1,3,5)),"early_central_contest_any":any(contested[turn] for turn in range(1,7)),"early_central_contest_turn_count":sum(contested[turn] for turn in range(1,7))}


def diagnostics_for_game(row: dict[str,str],table_dir: Path) -> tuple[dict[str,object],list[dict[str,object]]]:
    placements=read_csv(table_dir/"placements.csv");states=read_csv(table_dir/"turn-states.csv");by_turn=defaultdict(list)
    for state in states:by_turn[int(state["turn_number"])].append(state)
    leaders={turn:corrected_leader(values) for turn,values in by_turn.items()};winner=int(row["winner"]);persistent=None
    if winner:
        for turn in range(1,19):
            if all(leaders[later]==winner for later in range(turn,19)):persistent=turn;break
    result={"iteration_limit":int(row["iteration_limit"]),"game_index":int(row["game_index"]),"seed":int(row["seed"]),"winner":winner,"deciding_criterion":row["deciding_criterion"],"secured_margin_p1_minus_p2":int(row["p1_secured_objectives"])-int(row["p2_secured_objectives"]),"advantage_margin_p1_minus_p2":int(row["p1_advantage_objectives"])-int(row["p2_advantage_objectives"]),"corrected_objective_piece_margin_p1_minus_p2":int(row["p1_corrected_objective_pieces"])-int(row["p2_corrected_objective_pieces"]),"first_persistent_full_lexicographic_lead_turn":persistent,**central_metrics(placements,states)}
    reversals=[]
    for checkpoint,turn in ((.75,14),(.9,17)):
        leader=leaders[turn];eligible=leader!=0 and winner!=0;reversals.append({"iteration_limit":int(row["iteration_limit"]),"game_index":int(row["game_index"]),"checkpoint":checkpoint,"turn_number":turn,"checkpoint_leader":leader,"winner":winner,"eligible":eligible,"late_reversal":eligible and leader!=winner})
    return result,reversals


def old_central(config: dict) -> list[dict[str,object]]:
    manifest=protocol.load_json(protocol.REPO_ROOT/config["historical_sources"]["issue_82_manifest"]);rows=[]
    for entry in manifest["tasks"].values():
        if entry["state"]!="completed" or int(entry["iteration_limit"]) not in config["primary_budgets"]:continue
        task_dir=(protocol.REPO_ROOT/entry["artifacts"]["validation"]).parent;metrics=central_metrics(read_csv(task_dir/"validation-raw"/"placements.csv"),read_csv(task_dir/"validation-raw"/"turn-states.csv"));rows.append({"sample":"issue-82-original","iteration_limit":int(entry["iteration_limit"]),"game_index":int(entry["game_index"]),**metrics})
    return rows


def summarize_central(rows: list[dict[str,object]]) -> list[dict[str,object]]:
    grouped=defaultdict(list)
    for row in rows:grouped[(row["sample"],row["iteration_limit"])].append(row)
    result=[]
    for (sample,budget),values in sorted(grouped.items()):
        commitments=[int(row["first_central_commitment_turn"]) for row in values if row["first_central_commitment_turn"] is not None]
        result.append({"sample":sample,"iteration_limit":budget,"games":len(values),"early_central_placement_frequency":sum(bool(row["early_central_placement_any"]) for row in values)/len(values),"mean_early_central_placement_count":sum(int(row["early_central_placement_count"]) for row in values)/len(values),"commitment_games":len(commitments),"mean_first_commitment_turn_conditional":sum(commitments)/len(commitments) if commitments else "","occupation_after_p1_turn_1_frequency":sum(bool(row["central_occupation_after_p1_turn_1"]) for row in values)/len(values),"occupation_after_p1_turn_2_frequency":sum(bool(row["central_occupation_after_p1_turn_2"]) for row in values)/len(values),"occupation_after_p1_turn_3_frequency":sum(bool(row["central_occupation_after_p1_turn_3"]) for row in values)/len(values),"early_contest_frequency":sum(bool(row["early_central_contest_any"]) for row in values)/len(values)})
    return result


def build_diagnostics(config: dict,rows: list[dict[str,str]],paths: dict[tuple[int,int],Path]) -> dict:
    games=[];reversals=[]
    for row in rows:
        game,events=diagnostics_for_game(row,paths[(int(row["iteration_limit"]),int(row["game_index"]))]);game["sample"]="issue-108-corrected";games.append(game);reversals.extend(events)
    write_csv(FINAL/"game-diagnostics.csv",games,list(games[0]) if games else ["iteration_limit"]);write_csv(FINAL/"late-reversals.csv",reversals,list(reversals[0]) if reversals else ["iteration_limit"])
    summary=[]
    for key,values in sorted(group_rows(reversals,lambda row:(row["iteration_limit"],row["checkpoint"])).items()):
        eligible=[row for row in values if row["eligible"]];summary.append({"iteration_limit":key[0],"checkpoint":key[1],"turn_number":values[0]["turn_number"],"games":len(values),"eligible_games":len(eligible),"late_reversals":sum(row["late_reversal"] for row in eligible),"late_reversal_rate":optional(sum(row["late_reversal"] for row in eligible)/len(eligible) if eligible else None)})
    write_csv(FINAL/"late-reversal-summary.csv",summary,list(summary[0]) if summary else ["iteration_limit"])
    central_keys=["early_central_placement_any","early_central_placement_count","first_central_commitment_turn","first_central_commitment_p1_turn","central_occupation_after_p1_turn_1","central_occupation_after_p1_turn_2","central_occupation_after_p1_turn_3","early_central_occupation_turn_count","early_central_contest_any","early_central_contest_turn_count"]
    corrected_central=[{"sample":"issue-108-corrected","iteration_limit":row["iteration_limit"],"game_index":row["game_index"],**{key:row[key] for key in central_keys}} for row in games]
    central_rows=old_central(config)+corrected_central;central_summary=summarize_central(central_rows);write_csv(FINAL/"central-supply-by-game.csv",central_rows,list(central_rows[0]) if central_rows else ["sample"]);write_csv(FINAL/"central-supply-summary.csv",central_summary,list(central_summary[0]) if central_summary else ["sample"])
    return {"game_diagnostics":len(games),"late_reversal_rows":len(reversals),"central_comparison_rows":len(central_rows)}


def group_rows(rows,key):
    result=defaultdict(list)
    for row in rows:result[key(row)].append(row)
    return result


def output_hashes() -> dict[str,str]:return {path.relative_to(protocol.REPO_ROOT).as_posix():protocol.sha256(path) for path in sorted(FINAL.iterdir()) if path.is_file() and path.name!="environment.json"}


def render_report(analysis: dict) -> str:
    def pct(value,signed=False):return "NA" if value=="" or value is None else f"{100*float(value):+0.1f}" if signed else f"{100*float(value):0.1f}"
    lines=["# Issue 108: corrected-rule 3x3 deep UCT","","## Corrected-rule primary balance","","| UCT | Validated | P1 | P2 | Draw | P1 rate | Bootstrap 95% CI |","|---:|---:|---:|---:|---:|---:|---:|"]
    for row in analysis["balance"]:lines.append(f"| {row['iteration_limit']:,} | {row['validated_games']} | {row['p1_wins']} | {row['p2_wins']} | {row['draws']} | {pct(row['p1_win_rate'])}% | {pct(row['p1_bootstrap_95_low'])}–{pct(row['p1_bootstrap_95_high'])}% |")
    lines += ["","Draws remain in the primary denominator. Labels below are auxiliary; point estimates and intervals are primary.","","## Preregistered interpretation","",f"- Primary 100k drop: corrected 100k minus corrected 30k.",f"- Auxiliary drop label: **{analysis['classification']['drop_classification']}**.",f"- Search-depth classification: **{analysis['classification']['depth_classification']}**.","- No material-change label is used.","","#105 remains a terminal-rescore counterfactual and is not combined with regenerated trajectories. Differences can indicate that search-generation effects may matter, but do not identify a causal mechanism.","","## Incomplete games","",("No production tasks are incomplete." if not analysis["failures"] else f"{len(analysis['failures'])} task(s) are incomplete; see `results/final/failures.csv`. Missingness may be non-random."),"","These finite self-play samples do not establish convergence, optimal play, or solved-game balance."]
    return "\n".join(lines)+"\n"


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--verify-deterministic",action="store_true");args=parser.parse_args();config=protocol.load_config();lock,_,finalization=verify_locks(config);rows,paths,manifest=completed(config)
    analysis=primary_outputs(config,rows,manifest);analysis["secondary"]=build_diagnostics(config,rows,paths);analysis.update(schema_version=1,primary_budgets=config["primary_budgets"],planned_games_by_budget=finalization["planned_games_by_budget"],completed_games_by_budget=finalization["completed_games_by_budget"],pilot_excluded=True,material_change_label_used=False)
    protocol.atomic_write_json(FINAL/"analysis.json",analysis);first=output_hashes()
    if args.verify_deterministic:
        rows2,paths2,manifest2=completed(config);repeated=primary_outputs(config,rows2,manifest2);repeated["secondary"]=build_diagnostics(config,rows2,paths2)
        if first!=output_hashes() or repeated!={key:analysis[key] for key in repeated}:raise ValueError("deterministic regeneration mismatch")
    environment={"schema_version":1,"generated_at_utc":protocol.utc_now(),"python":platform.python_version(),"os":platform.system(),"architecture":platform.machine(),"config_sha256":protocol.sha256(protocol.CONFIG_PATH),"protocol_lock_sha256":protocol.sha256(protocol.LOCK_PATH),"source_lock_sha256":protocol.sha256(protocol.SOURCE_LOCK_PATH),"finalization_sha256":protocol.sha256(protocol.FINALIZATION_PATH),"manifest_sha256":protocol.sha256(protocol.manifest_path("production")),"game_sha256":lock["game_sha256"],"output_hashes":output_hashes(),"deterministic_regeneration_verified":args.verify_deterministic,"rerun_commands":["python3 experiments/issue-108/scripts/finalize_production.py","python3 experiments/issue-108/scripts/run_analysis.py --verify-deterministic"]};protocol.atomic_write_json(FINAL/"environment.json",environment);REPORT.write_text(render_report(analysis),encoding="utf-8",newline="\n");print("Issue #108 analysis complete")


if __name__=="__main__":main()
