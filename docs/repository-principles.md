# Repository Safety and Experiment Integrity Principles

These principles apply across the repository. They provide a common baseline
for analysis, experiments, generated artifacts, experiment-related cleanup,
and public-release preparation. Issue-specific plans may impose stricter or
more detailed requirements.

## Public information safety

Repository content must not expose information that should remain private.
Review new and modified artifacts for machine-specific absolute paths, local
hostnames, usernames, personal contact information, private attachment paths,
temporary diagnostics, and other non-public local data.

Passwords, API keys, access tokens, private keys, and other credentials must
never be published or retained as reproducibility metadata. Other local or
personal identifiers must be classified before removal because they may be
intentional evidence. Preserve them only when their reproducibility value is
justified and publication is explicitly acceptable.

## Execution resilience

Work whose interruption would lose completed results or impose meaningful
rerun cost must tolerate unintended termination, including power loss, process
failure, OOM, operating-system restart, disconnected remote sessions, and
accidental runner termination.

Such work must preserve completed results and task state, support safe resume,
avoid regenerating completed tasks, reuse the same experiment identity and
seed where applicable, and record failures or missing results explicitly.
Each issue defines the appropriate mechanisms, such as manifests, atomic
writes, persistent sessions, or resumable runners.

## Evidence preservation

Validated evidence must not be casually modified, normalized, overwritten, or
deleted. Validated evidence means an artifact recorded as a validation target
or formal result through a manifest, validation record, source lock, hash, or
equivalent experiment record. It may include trials, generated summaries, and
final analysis outputs.

Disposable intermediate output must be explicitly designated as temporary,
cache-like, or safely reproducible. Reproducibility alone does not make a
formal result or validated artifact disposable.

Before changing existing evidence, determine the impact on reproducibility,
validation, provenance, and reported conclusions. If that impact is unclear or
would invalidate existing evidence, stop and report it rather than expanding
the change.

## Result-independent protocol

Primary analysis conditions must be defined independently of observed
production results. Before inspecting those results, define the hypotheses,
conditions, budgets, sample sizes, primary metrics, contrasts, classification
rules, and stopping or extension criteria that are relevant to the issue.

Work added or changed after results are inspected must be identified separately
as exploratory or follow-up analysis. Operational feasibility checks must not
be used to inspect outcomes selectively before the primary protocol is locked.

## Provenance and traceability

Experiment artifacts and derived results must remain traceable to the inputs
and conditions that produced them. Where applicable, record the source game
definition, commit or source lock, experiment configuration, game IDs, seeds,
trials, manifests, validation outputs, analysis scripts, and final outputs.

Provenance must use the minimum non-sensitive information needed for
traceability. Prefer repository-relative paths, content hashes, source locks,
and opaque runner identifiers over personal or machine-specific identifiers.
Derived results should be reproducible from the recorded evidence whenever
reasonably possible.

## Application to existing artifacts

These principles govern artifacts created or modified after this document is
adopted. They do not by themselves require a repository-wide audit, migration,
or rewrite of existing artifacts. Files touched by later work must be reviewed
for public-information safety, while existing validated evidence remains
protected by the evidence-preservation principle.

## Non-goals

These principles do not standardize statistical methods, confidence intervals,
bootstrap parameters, UCT budgets, board-specific validation values, runner
implementations, or directory layouts. Those choices remain issue-specific
unless a separate shared standard is justified.
