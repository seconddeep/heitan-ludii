#!/usr/bin/env python3
"""Analyze the finalized 7x7 screen without expanding its frozen scope."""

from __future__ import annotations

import argparse, csv, math, platform, random, tempfile
from pathlib import Path
import protocol
import run_experiments

FINAL = protocol.RESULTS_ROOT / "final"
REPORT = protocol.REPO_ROOT / "experiments/issue-118.md"

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:return list(csv.DictReader(handle))

def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,lineterminator="\n");writer.writeheader();writer.writerows(rows)

def percentile(values: list[float], probability: float) -> float:
    ordered=sorted(values);position=(len(ordered)-1)*probability;lower=math.floor(position);upper=math.ceil(position)
    return ordered[lower] if lower==upper else ordered[lower]+(ordered[upper]-ordered[lower])*(position-lower)

def rate(values: list[int]) -> float:return sum(values)/len(values)

def wilson(successes: int,total: int,z: float=1.959963984540054)->tuple[float,float]:
    if total==0:return math.nan,math.nan
    estimate=successes/total;denominator=1+z*z/total;centre=(estimate+z*z/(2*total))/denominator
    half=z*math.sqrt(estimate*(1-estimate)/total+z*z/(4*total*total))/denominator
    return centre-half,centre+half

def bootstrap_difference(a:list[int],b:list[int],samples:int,seed:int)->tuple[float,float]:
    if not a or not b:return math.nan,math.nan
    rng=random.Random(seed);estimates=[]
    for _ in range(samples):estimates.append(sum(rng.choice(a) for _ in a)/len(a)-sum(rng.choice(b) for _ in b)/len(b))
    return percentile(estimates,.025),percentile(estimates,.975)

def one_result(path:Path)->dict[str,str]:
    rows=read_csv(path)
    if len(rows)!=1:raise ValueError(f"expected one result row: {path}")
    return rows[0]

def historical(config:dict,key:str)->list[dict[str,str]]:
    manifest=protocol.load_json(protocol.REPO_ROOT/config["historical_sources"][key]);selected=[]
    for row in manifest["tasks"].values():
        if row["state"]=="completed" and int(row["iteration_limit"])==10000:selected.append(one_result(protocol.REPO_ROOT/row["artifacts"]["result"]))
    if len(selected)!=100:raise ValueError(f"{key} does not contain exactly 100 corrected UCT 10k games")
    return selected

def binaries(rows:list[dict[str,str]])->dict[str,list[int]]:
    winners=[int(row["winner"]) for row in rows];return {"p1":[int(value==1) for value in winners],"draw":[int(value==0) for value in winners]}

def build_outputs(output:Path)->dict:
    config=protocol.load_config();lock=protocol.load_json(protocol.LOCK_PATH);finalization=protocol.load_json(protocol.FINALIZATION_PATH);manifest=protocol.load_json(protocol.manifest_path("production"))
    if lock["config_sha256"]!=protocol.sha256(protocol.CONFIG_PATH) or lock["source_lock_sha256"]!=protocol.sha256(protocol.SOURCE_LOCK_PATH):raise ValueError("protocol or source lock changed")
    if finalization["manifest_sha256"]!=protocol.sha256(protocol.manifest_path("production")):raise ValueError("production manifest changed after finalization")
    protocol.verify_source_lock(lock)
    completed_rows=[row for row in manifest["tasks"].values() if row["state"]=="completed"]
    failed_rows=[row for row in manifest["tasks"].values() if row["state"] in {"failed","corrupt"}]
    production=[one_result(protocol.REPO_ROOT/row["artifacts"]["result"]) for row in completed_rows]
    planned,validated,failed=30,len(production),len(failed_rows)
    if validated+failed!=planned:raise ValueError("production tasks are not all terminal")
    values=binaries(production);p1=sum(values["p1"]);draws=sum(values["draw"]);p2=validated-p1-draws;p1_ci=wilson(p1,validated);draw_ci=wilson(draws,validated)
    primary=[{"uct":10000,"planned":planned,"validated":validated,"failed":failed,"p1_wins":p1,"p2_wins":p2,"draws":draws,"p1_rate":round(p1/validated,6) if validated else "","p1_wilson_95_low":round(p1_ci[0],6) if validated else "","p1_wilson_95_high":round(p1_ci[1],6) if validated else "","draw_rate":round(draws/validated,6) if validated else "","draw_wilson_95_low":round(draw_ci[0],6) if validated else "","draw_wilson_95_high":round(draw_ci[1],6) if validated else "","denominator":"validated completed games"}]
    write_csv(output/"primary-7x7.csv",primary,list(primary[0]))
    samples=int(config["analysis"]["bootstrap_samples"]);seed=int(config["analysis"]["bootstrap_seed"])
    history={"3x3":historical(config,"issue_108_manifest"),"4x4":historical(config,"issue_112_manifest")}
    comparison=[]
    for board,rows in [("3x3",history["3x3"]),("4x4",history["4x4"]),("7x7",production)]:
        binary=binaries(rows);comparison.append({"board":board,"games":len(rows),"p1_rate":round(rate(binary["p1"]),6) if rows else "","draw_rate":round(rate(binary["draw"]),6) if rows else ""})
    write_csv(output/"board-size-comparison.csv",comparison,list(comparison[0]))
    contrasts=[]
    for offset,board in enumerate(("4x4","3x3")):
        old=binaries(history[board])
        for measure_offset,measure in enumerate(("p1","draw")):
            ci=bootstrap_difference(values[measure],old[measure],samples,seed+offset*10+measure_offset)
            contrasts.append({"contrast":f"7x7 - {board}","measure":measure,"games_7x7":validated,"games_historical":len(old[measure]),"rate_7x7":round(rate(values[measure]),6) if validated else "","rate_historical":round(rate(old[measure]),6),"difference":round(rate(values[measure])-rate(old[measure]),6) if validated else "","bootstrap_95_low":round(ci[0],6) if validated else "","bootstrap_95_high":round(ci[1],6) if validated else ""})
    write_csv(output/"board-size-contrasts.csv",contrasts,list(contrasts[0]))
    diagnostics=[];draw_ties=[]
    for result in production:
        metrics=run_experiments.audit_board(result["final_board"],config)
        row={"game_index":int(result["game_index"]),"seed":int(result["seed"]),"winner":int(result["winner"]),"deciding_layer":metrics["deciding_criterion"],"secured_margin_p1_minus_p2":int(metrics["p1_secured_objectives"])-int(metrics["p2_secured_objectives"]),"advantage_margin_p1_minus_p2":int(metrics["p1_advantage_objectives"])-int(metrics["p2_advantage_objectives"]),"corrected_objective_piece_margin_p1_minus_p2":int(metrics["p1_corrected_objective_pieces"])-int(metrics["p2_corrected_objective_pieces"])}
        diagnostics.append(row)
        if row["winner"]==0:
            if any(row[key]!=0 for key in ("secured_margin_p1_minus_p2","advantage_margin_p1_minus_p2","corrected_objective_piece_margin_p1_minus_p2")):raise ValueError("draw does not tie every lexicographic layer")
            draw_ties.append(row.copy())
    diagnostics.sort(key=lambda row:row["game_index"]);draw_ties.sort(key=lambda row:row["game_index"])
    fields=["game_index","seed","winner","deciding_layer","secured_margin_p1_minus_p2","advantage_margin_p1_minus_p2","corrected_objective_piece_margin_p1_minus_p2"]
    write_csv(output/"terminal-diagnostics.csv",diagnostics,fields);write_csv(output/"draw-terminal-ties.csv",draw_ties,fields)
    failures=[{"task_id":row["task_id"],"seed":row["seed"],"state":row["state"],"attempts":row["attempts"],"failure_kind":row.get("failure_kind") or "","error":row.get("error") or ""} for row in failed_rows]
    write_csv(output/"failures.csv",failures,["task_id","seed","state","attempts","failure_kind","error"])
    analysis={"schema_version":1,"planned":planned,"validated":validated,"failed":failed,"primary_denominator":"validated completed games","failed_seed_replacement_allowed":False,"primary":primary[0],"comparison":comparison,"contrasts":contrasts,"terminal_diagnostic_scope":config["terminal_diagnostics"],"limitations":["30 planned games provide a screening estimate with wide uncertainty","UCT 10k is not a convergence claim and is not equal effective depth across board sizes","self-play does not establish optimal play or solved balance","board-size contrasts are descriptive and not pure causal effects"]}
    protocol.atomic_write_json(output/"analysis.json",analysis);return analysis

def report(analysis:dict)->str:
    p=analysis["primary"];pct=lambda value:f"{100*float(value):.1f}%"
    lines=["# Issue 118: corrected-rule 7x7 UCT 10k screen","",f"Production accounting: planned={p['planned']} / validated={p['validated']} / failed={p['failed']}.","","Rates use validated completed games as the denominator. Failed seeds were not replaced.","","## Primary 7x7 result","","| UCT | Planned | Validated | Failed | P1 | P2 | Draw | P1 rate | 95% CI | Draw rate | 95% CI |","|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",f"| 10k | {p['planned']} | {p['validated']} | {p['failed']} | {p['p1_wins']} | {p['p2_wins']} | {p['draws']} | {pct(p['p1_rate'])} | {pct(p['p1_wilson_95_low'])}–{pct(p['p1_wilson_95_high'])} | {pct(p['draw_rate'])} | {pct(p['draw_wilson_95_low'])}–{pct(p['draw_wilson_95_high'])} |","","## Corrected UCT 10k board-size comparison","","| Board | Games | P1 rate | Draw rate |","|---|---:|---:|---:|"]
    for row in analysis["comparison"]:lines.append(f"| {row['board']} | {row['games']} | {pct(row['p1_rate'])} | {pct(row['draw_rate'])} |")
    lines += ["","## Preregistered contrasts","","| Contrast | Measure | Difference | Bootstrap 95% CI |","|---|---|---:|---:|"]
    for row in analysis["contrasts"]:lines.append(f"| {row['contrast']} | {row['measure']} | {pct(row['difference'])} | {pct(row['bootstrap_95_low'])}–{pct(row['bootstrap_95_high'])} |")
    lines += ["","## Limitations",""]+[f"- {item}" for item in analysis["limitations"]]
    return "\n".join(lines)+"\n"

def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--verify-deterministic",action="store_true");args=parser.parse_args()
    if not protocol.FINALIZATION_PATH.is_file():raise ValueError("analysis is forbidden before production finalization")
    FINAL.mkdir(parents=True,exist_ok=True);analysis=build_outputs(FINAL);REPORT.write_text(report(analysis),encoding="utf-8",newline="\n")
    if args.verify_deterministic:
        with tempfile.TemporaryDirectory(prefix="heitan-118-analysis-") as directory:
            other=Path(directory);second=build_outputs(other)
            if second!=analysis:raise ValueError("deterministic analysis regeneration differs")
            for path in FINAL.iterdir():
                candidate=other/path.name
                if path.name not in {"environment.json","artifact-manifest.json"} and candidate.is_file() and candidate.read_bytes()!=path.read_bytes():raise ValueError(f"deterministic output differs: {path.name}")
    hashes={path.name:protocol.sha256(path) for path in sorted(FINAL.iterdir()) if path.is_file() and path.name not in {"environment.json","artifact-manifest.json"}}
    protocol.atomic_write_json(FINAL/"artifact-manifest.json",{"schema_version":1,"inputs":{"config":protocol.sha256(protocol.CONFIG_PATH),"protocol_lock":protocol.sha256(protocol.LOCK_PATH),"source_lock":protocol.sha256(protocol.SOURCE_LOCK_PATH),"production_manifest":protocol.sha256(protocol.manifest_path("production")),"finalization":protocol.sha256(protocol.FINALIZATION_PATH)},"outputs":hashes,"report":{"path":REPORT.relative_to(protocol.REPO_ROOT).as_posix(),"sha256":protocol.sha256(REPORT)}})
    protocol.atomic_write_json(FINAL/"environment.json",{"schema_version":1,"python":platform.python_version(),"os":platform.system(),"architecture":platform.machine(),"deterministic_regeneration_verified":args.verify_deterministic});print("Issue 118 analysis complete")

if __name__=="__main__":main()
