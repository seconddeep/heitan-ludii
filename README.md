# Heitan

Heitan is a two-player abstract strategy game about building supply networks and competing over Objectives.

[Play Heitan in your browser](https://play.seconddeep.com/)

Each turn, players place three Pieces, deciding whether to concentrate them or spread them across the board.

This repository contains the Ludii implementation of Heitan, its canonical rules, and analysis materials. The browser-playable implementation is maintained in [seconddeep/heitan-web](https://github.com/seconddeep/heitan-web).

## Documentation

### Rules

- [Rules (English)](docs/rules.md)
- [Rules (Japanese)](docs/rules-ja.md)

### Board Definition

- [Board Definition](docs/board.md)

### Repository Principles

- [Repository Safety and Experiment Integrity Principles](docs/repository-principles.md)

## Implementation

The game definition is located at:

```text
games/Heitan.lud
```

## Development

The project is developed incrementally using GitHub Issues.

Development guidelines and AI agent context are defined in:

```text
AGENTS.md
```

## Project Structure

```text
.
├── games/
│   └── Heitan.lud
├── docs/
│   ├── rules.md
│   ├── rules-ja.md
│   ├── board.md
│   └── repository-principles.md
├── experiments/
├── AGENTS.md
└── README.md
```

## Usage

This repository is published to make the development and analysis of Heitan open and verifiable.

You may use the contents of this repository for:

- playing Heitan locally;
- reading and referencing the game rules;
- inspecting the Ludii implementation and analysis results;
- personal, non-commercial research, analysis, and verification;
- local copying and modification when needed for those purposes.

Commercial use, including selling or productizing Heitan or commercial derivatives based on it, requires prior permission from the author.

## Status

Heitan is publicly playable in the browser and remains under active development and analysis.

The 4x4 version has undergone Ludii UCT self-play analysis at search budgets up to 100,000 iterations.
