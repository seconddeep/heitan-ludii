#!/usr/bin/env python3
"""Analyze finalized Issue 120 evidence within the preregistered scope."""

from __future__ import annotations

import argparse
import csv
import math
import platform
import random
import statistics
import tempfile
from pathlib import Path

import protocol
import run_experiments


FINAL = protocol.RESULTS_ROOT / "final"
REPORT = protocol.REPO_ROOT / "experiments/issue-120.md"
DIAGNOSTIC_FIELDS = [
    "game_index", "seed", "winner", "deciding_layer",
    "secured_margin_p1_minus_p2", "advantage_margin_p1_minus_p2",
    "corrected_objective_piece_margin_p1_minus_p2",
]
MARGIN_FIELDS = DIAGNOSTIC_FIELDS[-3:]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def rate(values: list[int]) -> float:
    return sum(values) / len(values)


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total == 0:
        return math.nan, math.nan
    estimate = successes / total
    denominator = 1 + z * z / total
    centre = (estimate + z * z / (2 * total)) / denominator
    half = z * math.sqrt(estimate * (1 - estimate) / total + z * z / (4 * total * total)) / denominator
    return centre - half, centre + half


def bootstrap_difference(a: list[int], b: list[int], samples: int, seed: int) -> tuple[float, float]:
    if not a or not b:
        return math.nan, math.nan
    rng = random.Random(seed)
    estimates = [
        sum(rng.choice(a) for _ in a) / len(a) - sum(rng.choice(b) for _ in b) / len(b)
        for _ in range(samples)
    ]
    return percentile(estimates, .025), percentile(estimates, .975)


def one_result(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    if len(rows) != 1:
        raise ValueError(f"expected one result row: {path}")
    return rows[0]


def historical(config: dict, key: str, budget: int, expected: int) -> list[dict[str, str]]:
    manifest = protocol.load_json(protocol.REPO_ROOT / config["historical_sources"][key])
    selected = [
        one_result(protocol.REPO_ROOT / row["artifacts"]["result"])
        for row in manifest["tasks"].values()
        if row["state"] == "completed" and int(row["iteration_limit"]) == budget
    ]
    if len(selected) != expected:
        raise ValueError(f"{key} does not contain exactly {expected} corrected UCT {budget} games")
    return selected


def binaries(rows: list[dict[str, str]]) -> dict[str, list[int]]:
    winners = [int(row["winner"]) for row in rows]
    return {"p1": [int(value == 1) for value in winners], "draw": [int(value == 0) for value in winners]}


def rate_row(uct: int, rows: list[dict[str, str]]) -> dict[str, object]:
    values = binaries(rows)
    return {"uct": uct, "validated": len(rows), "p1_rate": round(rate(values["p1"]), 6), "draw_rate": round(rate(values["draw"]), 6)}


def diagnostic_rows(results: list[dict[str, str]], config: dict) -> list[dict[str, object]]:
    rows = []
    for result in results:
        metrics = run_experiments.audit_board(result["final_board"], config)
        row = {
            "game_index": int(result["game_index"]), "seed": int(result["seed"]),
            "winner": int(result["winner"]), "deciding_layer": metrics["deciding_criterion"],
            "secured_margin_p1_minus_p2": int(metrics["p1_secured_objectives"]) - int(metrics["p2_secured_objectives"]),
            "advantage_margin_p1_minus_p2": int(metrics["p1_advantage_objectives"]) - int(metrics["p2_advantage_objectives"]),
            "corrected_objective_piece_margin_p1_minus_p2": int(metrics["p1_corrected_objective_pieces"]) - int(metrics["p2_corrected_objective_pieces"]),
        }
        if row["winner"] == 0 and any(row[name] != 0 for name in MARGIN_FIELDS):
            raise ValueError("draw does not tie every lexicographic layer")
        rows.append(row)
    return sorted(rows, key=lambda row: row["game_index"])


def terminal_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    layer_counts = {layer: sum(row["deciding_layer"] == layer for row in rows) for layer in ("secured_objectives", "advantage_objectives", "objective_pieces", "draw")}
    margins = {
        name: {"minimum": min(row[name] for row in rows), "median": statistics.median(row[name] for row in rows), "maximum": max(row[name] for row in rows)}
        for name in MARGIN_FIELDS
    } if rows else {name: {"minimum": "", "median": "", "maximum": ""} for name in MARGIN_FIELDS}
    draws = [row for row in rows if row["winner"] == 0]
    return {"deciding_layer_counts": layer_counts, "margin_p1_minus_p2": margins, "draw_games": len(draws), "all_draw_layers_tied": all(all(row[name] == 0 for name in MARGIN_FIELDS) for row in draws)}


def build_outputs(output: Path) -> dict:
    config = protocol.load_config()
    lock = protocol.load_json(protocol.LOCK_PATH)
    finalization = protocol.load_json(protocol.FINALIZATION_PATH)
    manifest = protocol.load_json(protocol.manifest_path("production"))
    if lock["config_sha256"] != protocol.sha256(protocol.CONFIG_PATH) or lock["source_lock_sha256"] != protocol.sha256(protocol.SOURCE_LOCK_PATH):
        raise ValueError("protocol or source lock changed")
    if finalization["manifest_sha256"] != protocol.sha256(protocol.manifest_path("production")):
        raise ValueError("production manifest changed after finalization")
    protocol.verify_source_lock(lock)

    completed_rows = [row for row in manifest["tasks"].values() if row["state"] == "completed"]
    failed_rows = [row for row in manifest["tasks"].values() if row["state"] in {"failed", "corrupt"}]
    production = [one_result(protocol.REPO_ROOT / row["artifacts"]["result"]) for row in completed_rows]
    planned, validated, failed = 30, len(production), len(failed_rows)
    if planned != validated + failed:
        raise ValueError("production accounting must satisfy planned = validated + failed")
    if finalization["validated_games_by_budget"]["30000"] != validated or finalization["failed_games_by_budget"]["30000"] != failed:
        raise ValueError("analysis accounting differs from finalization")

    values = binaries(production)
    p1, draws = sum(values["p1"]), sum(values["draw"])
    p2 = validated - p1 - draws
    p1_ci, draw_ci = wilson(p1, validated), wilson(draws, validated)
    primary = {
        "uct": 30000, "planned": planned, "validated": validated, "failed": failed,
        "p1_wins": p1, "p2_wins": p2, "draws": draws,
        "p1_rate": round(p1 / validated, 6), "p1_wilson_95_low": round(p1_ci[0], 6), "p1_wilson_95_high": round(p1_ci[1], 6),
        "draw_rate": round(draws / validated, 6), "draw_wilson_95_low": round(draw_ci[0], 6), "draw_wilson_95_high": round(draw_ci[1], 6),
        "denominator": "validated completed games",
    }
    write_csv(output / "primary-7x7.csv", [primary], list(primary))

    history_7x7 = historical(config, "issue_118_manifest", 10000, 30)
    context = {"3x3": historical(config, "issue_108_manifest", 30000, 100), "4x4": historical(config, "issue_112_manifest", 30000, 100)}
    depth_comparison = [rate_row(10000, history_7x7), rate_row(30000, production)]
    write_csv(output / "depth-comparison.csv", depth_comparison, list(depth_comparison[0]))

    samples, seed = int(config["analysis"]["bootstrap_samples"]), int(config["analysis"]["bootstrap_seed"])
    old_7x7 = binaries(history_7x7)
    depth_contrasts = []
    for offset, measure in enumerate(("p1", "draw")):
        ci = bootstrap_difference(values[measure], old_7x7[measure], samples, seed + offset)
        depth_contrasts.append({
            "contrast": "30k - 10k", "measure": measure, "games_30k": validated, "games_10k": len(history_7x7),
            "rate_30k": round(rate(values[measure]), 6), "rate_10k": round(rate(old_7x7[measure]), 6),
            "difference": round(rate(values[measure]) - rate(old_7x7[measure]), 6),
            "bootstrap_95_low": round(ci[0], 6), "bootstrap_95_high": round(ci[1], 6),
        })
    write_csv(output / "depth-contrasts.csv", depth_contrasts, list(depth_contrasts[0]))

    board_comparison = []
    for board, rows in (("3x3", context["3x3"]), ("4x4", context["4x4"]), ("7x7", production)):
        binary = binaries(rows)
        board_comparison.append({"board": board, "uct": 30000, "games": len(rows), "p1_rate": round(rate(binary["p1"]), 6), "draw_rate": round(rate(binary["draw"]), 6)})
    write_csv(output / "board-size-comparison.csv", board_comparison, list(board_comparison[0]))
    board_contrasts = []
    for board_offset, board in enumerate(("4x4", "3x3")):
        old = binaries(context[board])
        for measure_offset, measure in enumerate(("p1", "draw")):
            ci = bootstrap_difference(values[measure], old[measure], samples, seed + 10 + board_offset * 10 + measure_offset)
            board_contrasts.append({
                "contrast": f"7x7 - {board}", "measure": measure, "games_7x7": validated, "games_historical": len(old[measure]),
                "rate_7x7": round(rate(values[measure]), 6), "rate_historical": round(rate(old[measure]), 6),
                "difference": round(rate(values[measure]) - rate(old[measure]), 6),
                "bootstrap_95_low": round(ci[0], 6), "bootstrap_95_high": round(ci[1], 6),
            })
    write_csv(output / "board-size-contrasts.csv", board_contrasts, list(board_contrasts[0]))

    diagnostics = diagnostic_rows(production, config)
    draw_ties = [row for row in diagnostics if row["winner"] == 0]
    write_csv(output / "terminal-diagnostics.csv", diagnostics, DIAGNOSTIC_FIELDS)
    write_csv(output / "draw-terminal-ties.csv", draw_ties, DIAGNOSTIC_FIELDS)
    summary = terminal_summary(diagnostics)
    summary_rows = [{"diagnostic": "deciding_layer", "name": name, "count": count, "minimum": "", "median": "", "maximum": ""} for name, count in summary["deciding_layer_counts"].items()]
    summary_rows += [{"diagnostic": "final_margin_p1_minus_p2", "name": name, "count": validated, **numbers} for name, numbers in summary["margin_p1_minus_p2"].items()]
    write_csv(output / "terminal-summary.csv", summary_rows, ["diagnostic", "name", "count", "minimum", "median", "maximum"])

    old_diagnostics = read_csv(protocol.REPO_ROOT / config["historical_sources"]["issue_118_terminal_diagnostics"])
    terminal_comparison = []
    for uct, rows in ((10000, old_diagnostics), (30000, diagnostics)):
        normalized = [{**row, "winner": int(row["winner"]), **{name: int(row[name]) for name in MARGIN_FIELDS}} for row in rows]
        terminal = terminal_summary(normalized)
        for layer, count in terminal["deciding_layer_counts"].items():
            terminal_comparison.append({"uct": uct, "diagnostic": "deciding_layer", "name": layer, "count": count, "minimum": "", "median": "", "maximum": ""})
        for name, numbers in terminal["margin_p1_minus_p2"].items():
            terminal_comparison.append({"uct": uct, "diagnostic": "final_margin_p1_minus_p2", "name": name, "count": len(rows), **numbers})
    write_csv(output / "terminal-comparison.csv", terminal_comparison, ["uct", "diagnostic", "name", "count", "minimum", "median", "maximum"])

    failures = [{"task_id": row["task_id"], "seed": row["seed"], "state": row["state"], "attempts": row["attempts"], "failure_kind": row.get("failure_kind") or "", "error": row.get("error") or ""} for row in failed_rows]
    write_csv(output / "failures.csv", failures, ["task_id", "seed", "state", "attempts", "failure_kind", "error"])
    analysis = {
        "schema_version": 1, "planned": planned, "validated": validated, "failed": failed,
        "accounting_identity": "planned = validated + failed; corrupt is included in failed",
        "primary_denominator": "validated completed games", "failed_seed_replacement_allowed": False,
        "primary": primary, "depth_comparison": depth_comparison, "depth_contrasts": depth_contrasts,
        "board_size_comparison": board_comparison, "board_size_contrasts": board_contrasts,
        "terminal_diagnostic_scope": config["terminal_diagnostics"], "terminal_summary": summary,
        "limitations": [
            "30 planned games provide a relatively wide estimate",
            "UCT 30k does not establish convergence, optimal play, or solved balance",
            "the 7x7 UCT 10k and 30k samples are independent finite self-play samples",
            "nominal UCT 30k does not represent equal effective depth across board sizes",
            "board-size comparisons are descriptive rather than pure causal effects",
            "a 10k-to-30k change does not identify the strategic mechanism causing it",
        ],
    }
    protocol.atomic_write_json(output / "analysis.json", analysis)
    return analysis


def pct(value: object) -> str:
    return f"{100 * float(value):.1f}%"


def report(analysis: dict) -> str:
    p = analysis["primary"]
    contrasts = {(row["contrast"], row["measure"]): row for row in analysis["depth_contrasts"]}
    lines = [
        "# Issue 120: corrected-rule 7x7 UCT 30k follow-up", "",
        f"Production accounting: planned={p['planned']} / validated={p['validated']} / failed={p['failed']}. `corrupt` tasks are included in failed.", "",
        "Rates retain draws in the validated-game denominator. Failed seeds were not replaced.", "",
        "## Primary 7x7 30k result", "",
        "| UCT | Planned | Validated | Failed | P1 | P2 | Draw | P1 rate | 95% CI | Draw rate | 95% CI |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| 30k | {p['planned']} | {p['validated']} | {p['failed']} | {p['p1_wins']} | {p['p2_wins']} | {p['draws']} | {pct(p['p1_rate'])} | {pct(p['p1_wilson_95_low'])}–{pct(p['p1_wilson_95_high'])} | {pct(p['draw_rate'])} | {pct(p['draw_wilson_95_low'])}–{pct(p['draw_wilson_95_high'])} |", "",
        "## 7x7 depth comparison", "", "| UCT | Validated | P1 rate | Draw rate |", "|---:|---:|---:|---:|",
    ]
    for row in analysis["depth_comparison"]:
        lines.append(f"| {int(row['uct']) // 1000}k | {row['validated']} | {pct(row['p1_rate'])} | {pct(row['draw_rate'])} |")
    lines += ["", "## Primary depth contrasts", "", "| Contrast | Measure | Difference | Bootstrap 95% CI |", "|---|---|---:|---:|"]
    for row in analysis["depth_contrasts"]:
        lines.append(f"| {row['contrast']} | {row['measure']} | {pct(row['difference'])} | {pct(row['bootstrap_95_low'])}–{pct(row['bootstrap_95_high'])} |")
    lines += [
        "", "## Directional interpretation", "",
        f"The 30k P1 estimate is {pct(p['p1_rate'])}; the independent 30k - 10k difference is {pct(contrasts[('30k - 10k', 'p1')]['difference'])}.",
        f"The 30k draw estimate is {pct(p['draw_rate'])}; the independent 30k - 10k difference is {pct(contrasts[('30k - 10k', 'draw')]['difference'])}.",
        "These finite-sample point estimates and intervals are directional evidence, not convergence classifications.", "",
        "## Secondary corrected UCT 30k board-size context", "", "| Board | Games | P1 rate | Draw rate |", "|---|---:|---:|---:|",
    ]
    for row in analysis["board_size_comparison"]:
        lines.append(f"| {row['board']} | {row['games']} | {pct(row['p1_rate'])} | {pct(row['draw_rate'])} |")
    lines += ["", "| Contrast | Measure | Difference | Bootstrap 95% CI |", "|---|---|---:|---:|"]
    for row in analysis["board_size_contrasts"]:
        lines.append(f"| {row['contrast']} | {row['measure']} | {pct(row['difference'])} | {pct(row['bootstrap_95_low'])}–{pct(row['bootstrap_95_high'])} |")
    terminal = analysis["terminal_summary"]
    lines += ["", "## Limited terminal diagnostics", "", "| Deciding layer | Games |", "|---|---:|"]
    for name, count in terminal["deciding_layer_counts"].items():
        lines.append(f"| {name} | {count} |")
    lines += ["", "| Final margin (P1 - P2) | Minimum | Median | Maximum |", "|---|---:|---:|---:|"]
    for name, numbers in terminal["margin_p1_minus_p2"].items():
        lines.append(f"| {name} | {numbers['minimum']} | {numbers['median']} | {numbers['maximum']} |")
    lines += ["", f"Draw games: {terminal['draw_games']}. All draw games tied at every lexicographic layer: {str(terminal['all_draw_layers_tied']).lower()}.", "", "## Limitations", ""]
    lines += [f"- {item}" for item in analysis["limitations"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-deterministic", action="store_true")
    args = parser.parse_args()
    if not protocol.FINALIZATION_PATH.is_file():
        raise ValueError("analysis is forbidden before production finalization")
    FINAL.mkdir(parents=True, exist_ok=True)
    analysis = build_outputs(FINAL)
    REPORT.write_text(report(analysis), encoding="utf-8")
    if args.verify_deterministic:
        with tempfile.TemporaryDirectory(prefix="heitan-120-analysis-") as directory:
            other = Path(directory)
            second = build_outputs(other)
            if second != analysis:
                raise ValueError("deterministic analysis regeneration differs")
            for path in FINAL.iterdir():
                candidate = other / path.name
                if path.name not in {"environment.json", "artifact-manifest.json"} and candidate.is_file() and candidate.read_bytes() != path.read_bytes():
                    raise ValueError(f"deterministic output differs: {path.name}")
    hashes = {path.name: protocol.sha256(path) for path in sorted(FINAL.iterdir()) if path.is_file() and path.name not in {"environment.json", "artifact-manifest.json"}}
    protocol.atomic_write_json(FINAL / "artifact-manifest.json", {"schema_version": 1, "inputs": {"config": protocol.sha256(protocol.CONFIG_PATH), "protocol_lock": protocol.sha256(protocol.LOCK_PATH), "source_lock": protocol.sha256(protocol.SOURCE_LOCK_PATH), "production_manifest": protocol.sha256(protocol.manifest_path("production")), "finalization": protocol.sha256(protocol.FINALIZATION_PATH)}, "outputs": hashes, "report": {"path": REPORT.relative_to(protocol.REPO_ROOT).as_posix(), "sha256": protocol.sha256(REPORT)}})
    protocol.atomic_write_json(FINAL / "environment.json", {"schema_version": 1, "python": platform.python_version(), "os": platform.system(), "architecture": platform.machine(), "deterministic_regeneration_verified": args.verify_deterministic})
    print("Issue 120 analysis complete")


if __name__ == "__main__":
    main()
