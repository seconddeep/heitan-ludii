#!/usr/bin/env python3
"""Run Issue #39 analysis and record its reproducibility environment."""

from __future__ import annotations

import csv
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
ANALYZER = SCRIPT.parent / "analyze_site_value.py"
REPORT = REPO_ROOT / "experiments" / "issue-39.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def top_sites(rows: list[dict[str, str]], metric: str, count: int = 5) -> str:
    selected = [row for row in rows if row["experiment_id"] == "uct-10000-self-play"]
    selected.sort(key=lambda row: float(row[metric]), reverse=True)
    return ", ".join(f"{row['supply_point']} ({float(row[metric]):.3f})" for row in selected[:count])


def site_rank(rows: list[dict[str, str]], site: str, metric: str) -> int:
    selected = [row for row in rows if row["experiment_id"] == "uct-10000-self-play"]
    selected.sort(key=lambda row: (-float(row[metric]), row["supply_point"]))
    return next(index for index, row in enumerate(selected, 1) if row["supply_point"] == site)


def build_report() -> None:
    analysis = json.loads((RESULTS / "analysis.json").read_text(encoding="utf-8"))
    rows = read_csv(RESULTS / "site-value-summary.csv")
    phase_rows = read_csv(RESULTS / "site-phase-summary.csv")
    outcome_rows = read_csv(RESULTS / "winner-loser-site-comparison.csv")
    s22 = analysis["s22_vs_other_interior_8"]["uct-10000-self-play"]
    correlation = analysis["placement_usage_correlation"]["uct-10000-self-play"]
    concentration = analysis["usage_concentration"]["uct-10000-self-play"]
    labels = {
        "pieces_placed_per_player_game": "Pieces placed per player-game",
        "unsecured_controlled_turn_share": "unsecured Control turn share",
        "secured_turn_share": "Secured turn share",
        "controlled_or_secured_turn_share": "combined ownership/control turn share",
        "objective_placements_supplied_per_player_game": "Objective placements supplied per player-game",
        "mean_objective_coverage": "normalized Objective coverage",
    }
    comparison_lines = [
        f"| {labels[metric]} | {values['s22']:.3f} | {values['other_interior_8_mean']:.3f} | {values['difference']:+.3f} | {site_rank(rows, 'S22', metric)} |"
        for metric, values in s22.items()
    ]
    primary = [row for row in rows if row["experiment_id"] == "uct-10000-self-play"]
    most_contested = sorted(primary, key=lambda row: float(row["contested_turn_share"]), reverse=True)[:9]
    contested_low_secured = sorted(most_contested, key=lambda row: (float(row["secured_frequency"]), -float(row["contested_turn_share"])))[:5]
    contested_text = ", ".join(
        f"{row['supply_point']} (contest {float(row['contested_turn_share']):.3f}, Secured frequency {float(row['secured_frequency']):.3f})"
        for row in contested_low_secured
    )
    heavy_after_securing = sorted(
        (row for row in primary if int(row["player_games_secured"]) >= 10),
        key=lambda row: float(row["mean_usage_after_securing_per_secured_player_site"]),
        reverse=True,
    )[:5]
    heavy_text = ", ".join(
        f"{row['supply_point']} ({float(row['mean_usage_after_securing_per_secured_player_site']):.2f} later uses; {int(row['player_games_secured'])} Secured player-sites)"
        for row in heavy_after_securing
    )

    outcome_summary: dict[str, dict[str, float]] = {}
    for status in ("winner", "loser", "draw"):
        selected = [row for row in outcome_rows if row["experiment_id"] == "uct-10000-self-play" and row["player_result_status"] == status]
        outcome_summary[status] = {
            "pieces": sum(float(row["pieces_placed_per_player_game"]) for row in selected),
            "unsecured": sum(float(row["unsecured_controlled_turn_share"]) for row in selected),
            "secured": sum(float(row["secured_turn_share"]) for row in selected),
            "combined": sum(float(row["controlled_or_secured_turn_share"]) for row in selected),
            "usage": sum(float(row["objective_placements_supplied_per_player_game"]) for row in selected),
        }
    outcome_lines = [
        f"| {status} | {values['pieces']:.2f} | {values['unsecured']:.3f} | {values['secured']:.3f} | {values['combined']:.3f} | {values['usage']:.2f} |"
        for status, values in outcome_summary.items()
    ]

    phase_lines: list[str] = []
    for phase_name in ("early", "midgame", "late"):
        selected = [row for row in phase_rows if row["experiment_id"] == "uct-10000-self-play" and row["turn_phase"] == phase_name]
        top_usage = max(selected, key=lambda row: int(row["objective_placements_supplied"]))
        phase_lines.append(
            f"| {phase_name} | {sum(int(row['pieces_placed']) for row in selected)} | "
            f"{sum(int(row['unsecured_controlled_turns']) for row in selected)} | "
            f"{sum(int(row['secured_turns']) for row in selected)} | "
            f"{sum(int(row['objective_placements_supplied']) for row in selected)} | "
            f"{top_usage['supply_point']} ({top_usage['objective_placements_supplied']}) |"
        )

    strength_lines: list[str] = []
    for experiment, label in (("uct-3000-self-play", "UCT 3,000"), ("uct-10000-self-play", "UCT 10,000")):
        selected = [row for row in rows if row["experiment_id"] == experiment]
        values = analysis["usage_concentration"][experiment]
        strength_lines.append(
            f"| {label} | {sum(float(row['unsecured_controlled_turn_share']) for row in selected):.3f} | "
            f"{sum(float(row['secured_turn_share']) for row in selected):.3f} | "
            f"{sum(float(row['objective_placements_supplied_per_player_game']) for row in selected):.2f} | "
            f"{values['usage_top_5_share']:.1%} | {values['usage_hhi']:.4f} |"
        )
    report = f"""# Issue 39: Supply Point site value

## Summary

This analysis reconstructs every Supply Point lifecycle in the 100 primary
UCT 10,000 games and the 100 UCT 3,000 comparison games. No new self-play was
generated. Value is deliberately reported as separate placement, reversible
unsecured Control, permanent Secured infrastructure, combined ownership/control,
actual Supply use, coverage, contest, and outcome dimensions.

The primary data's top sites by placement are {top_sites(rows, 'pieces_placed_per_player_game')}.
The top sites by actual Objective placements supplied are
{top_sites(rows, 'objective_placements_supplied_per_player_game')}.
Placement and use have Pearson correlation
{correlation['placement_usage_pearson']:.3f} and Spearman rank correlation
{correlation['placement_usage_spearman']:.3f} across the 25 sites.

## S22 versus the other eight interior points

| Dimension | S22 | Other interior mean | Difference | 25-site rank |
|---|---:|---:|---:|---:|
{chr(10).join(comparison_lines)}

S22 is therefore not the single leader in every dimension: it ranks
{site_rank(rows, 'S22', 'pieces_placed_per_player_game')}th in placement and
{site_rank(rows, 'S22', 'objective_placements_supplied_per_player_game')}th in
actual Supply use, while its reversible-Control, Secured, and combined shares
are independently reported above. S23, S21, S12, and S13 all supplied more
Objective placements per player-game in this sample. The table must not be
interpreted as a single composite site-value score.

## Competition and post-Securing utility

Among the nine sites with the greatest contested-turn share, the five with the
lowest Secured frequency are: {contested_text}. This is a two-stage descriptive
filter, not a composite value score.

Requiring at least ten Secured player-sites, the highest mean actual usage
after Securing is: {heavy_text}. These are the points that most clearly behave
as selectively fixed infrastructure followed by substantial use.

## Winner and loser association

The following primary-sample values are per player-game. Control columns are
the expected number of sites in each state on a randomly selected game turn
(the sum of the 25 site shares).

| Result | Supply Pieces placed | Unsecured Control | Secured | Combined | Objective placements supplied |
|---|---:|---:|---:|---:|---:|
{chr(10).join(outcome_lines)}

Winner/loser differences are associations within these self-play samples and
are not evidence that a site state causes the result. Site-specific values are
retained in `results/winner-loser-site-comparison.csv`.

## Phase shift

| Phase | Supply Pieces placed | Unsecured-Control turns | Secured turns | Objective placements supplied | Most-used site |
|---|---:|---:|---:|---:|---|
{chr(10).join(phase_lines)}

The phase table keeps reversible Control and permanent Secured occupancy
separate. All site-by-phase values are available in
`results/site-phase-summary.csv`.

## Search strength and concentration

| Search | Unsecured Control | Secured | Supply uses/player-game | Top-5 usage share | Usage HHI |
|---|---:|---:|---:|---:|---:|
{chr(10).join(strength_lines)}

For actual Supply usage in the primary data, the top three sites account for
{concentration['usage_top_3_share']:.1%}. Search-strength differences are
between two independent 100-game samples, not paired causal estimates. Every
site-level delta is retained in `results/search-strength-site-comparison.csv`.

## Definitions

Under the game rules, Secured belongs to the owner's Control. Analytically,
`unsecured_controlled_turns` and `secured_turns` are disjoint, and
`controlled_or_secured_turns` is their sum. All three measures and shares are
retained in lifecycle, phase, site, outcome, and strength-comparison outputs.
Objective coverage is normalized by each site's number of adjacent Objectives.
Repeated legal Securing opportunities and ever-securable player-sites use
separate denominators.

## Integrity

- {analysis['integrity']['source_trials_hashed_and_verified']} source trial paths and SHA-256 hashes were verified.
- {analysis['integrity']['issue_37_natural_end_replays_reused']} legally completed Issue #37 replays were reused.
- {analysis['integrity']['site_turn_lifecycle_rows']} player-site-turn records and {analysis['integrity']['site_lifecycle_rows']} player-site lifecycle records were generated.
- Control separation identities were checked for all lifecycle and phase rows.
- {analysis['integrity']['objective_supply_sources_verified']} actual Objective Supply-source uses were checked for adjacency, ownership/control, and per-turn uniqueness.

See `experiments/issue-39/README.md` for frozen definitions, output inventory,
and reproduction commands.
"""
    REPORT.write_text(report, encoding="utf-8")


def main() -> None:
    started = time.time()
    subprocess.run(["python3", str(ANALYZER)], cwd=REPO_ROOT, check=True)
    build_report()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    source_files = read_csv(RESULTS / "source-files.csv")
    environment = {
        "schema_version": 1,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - started, 3),
        "git_commit": commit, "python": platform.python_version(),
        "os": platform.platform(), "machine": platform.machine(),
        "config": CONFIG.relative_to(REPO_ROOT).as_posix(), "config_sha256": sha256(CONFIG),
        "readme_sha256": sha256(ISSUE_ROOT / "README.md"),
        "analyzer_sha256": sha256(ANALYZER), "run_script_sha256": sha256(SCRIPT),
        "test_script_sha256": sha256(SCRIPT.parent / "test_analysis.py"),
        "source_files": source_files,
        "new_uct_self_play_games": 0,
    }
    (RESULTS / "environment.json").write_text(
        json.dumps(environment, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {REPORT.relative_to(REPO_ROOT)} and reproducibility environment")


if __name__ == "__main__":
    main()
