# AGENTS.md

## Project Overview

This repository contains the Ludii implementation of **Heitan**, an abstract strategy game.

Heitan is a two-player abstract strategy game where players build supply networks and compete for control of scoring sites.

The goal of this project is to implement the game faithfully according to the defined rules and enable analysis using Ludii.

---

## Source of Truth

The game rules are defined in the following documents.

- `docs/rules.md` - Official English specification
- `docs/rules-ja.md` - Japanese development specification
- `docs/board.md` - Board structure and connection definitions

These documents are the source of truth for game behavior.

Do not modify game rules in code without updating the specification documents.

---

## Implementation Guidelines

### Incremental Development

Implement Heitan incrementally according to GitHub Issues.

Each implementation change should:

- correspond to a specific issue
- keep changes focused
- avoid unrelated modifications

---

### Preserve Game Design

Do not introduce additional mechanics or simplify existing mechanics.

Important core concepts:

- Exactly three piece placements per turn
- Supply Sites and Scoring Sites are different types of sites
- Supply control determines available scoring placements
- Site states transition from contested to confirmed
- State updates occur after all three placements of a turn

---

## Ludii Implementation

The main game definition is:

```
games/Heitan.lud
```

Keep the Ludii definition readable and close to the game specification.

Prefer clear structure over premature optimization.

---

## Naming Conventions

Game name:

```
Heitan
```

Players:

```
Player 1: Black (first player)
Player 2: White (second player)
```

Site naming:

```
Supply Sites:
S00 - S44

Scoring Sites:
C00 - C33
```

---

## Documentation Rules

When changing game behavior:

1. Update `docs/rules-ja.md`
2. Update `docs/rules.md`
3. Update implementation

Documentation and implementation must remain consistent.

---

## Development Workflow

Preferred workflow:

1. Create or select a GitHub Issue
2. Create a topic branch
3. Implement the change
4. Commit changes
5. Create a Pull Request
6. Merge after review

Example:

```
topic/<issue-number>
```

---

## Testing

Before completing an implementation issue:

- Verify the Ludii game loads successfully
- Test the implemented behavior
- Confirm that existing rules are not affected

---

## Scope Control

Avoid adding features that are not part of the current specification.

Examples of out-of-scope changes:

- New game modes
- Rule variations
- Additional piece types
- Theme changes

unless explicitly requested by an issue.
