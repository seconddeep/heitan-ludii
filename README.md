# Heitan

Heitan is an abstract strategy game implemented for Ludii.

Players build supply networks and compete over Objectives.
The game focuses on strategic decisions involving supply management and the balance between concentrated and distributed placement.

## About

Heitan is a two-player abstract strategy game.

Each turn, players place three Pieces and use Supply Points to expand their influence over Objectives.

The game is designed around simple rules that create complex strategic choices.

## Documentation

### Rules

- [Rules (English)](docs/rules.md)
- [Rules (Japanese)](docs/rules-ja.md)

### Board Definition

- [Board Definition](docs/board.md)

## Implementation

This repository contains the Ludii implementation of Heitan.

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

### VS Code syntax highlighting

This repository includes lightweight syntax highlighting for Ludii `.lud` files.
It is a repository-local VS Code language extension and does not require
publication to the VS Code Marketplace.

#### Install for normal VS Code use

Node.js, npm, and the VS Code `code` command must be available. From the
extension directory, install the packaging dependency and install the local
extension:

```sh
cd tools/vscode-ludii
npm ci
npm run install-local
```

The install command packages `ludii-syntax-highlighting.vsix` and installs it
into VS Code. Reload or restart VS Code after installation. A `.lud` file opened
in a normal VS Code window should then automatically use the **Ludii** language
mode; an Extension Development Host is not required.

To package and install in separate steps, run:

```sh
npm run package
code --install-extension ludii-syntax-highlighting.vsix --force
```

The generated VSIX is a local build artifact and is ignored by Git.

#### Update the local installation

Changes to the manifest, language configuration, or TextMate grammar are not
applied to the installed extension automatically. Repackage and reinstall it,
then reload VS Code:

```sh
cd tools/vscode-ludii
npm run install-local
```

#### Develop and verify the extension

The Extension Development Host remains available for testing changes without
installing them first:

1. Open the repository root in VS Code.
2. Open **Run and Debug**.
3. Select **Run Ludii Syntax Highlighting** and press **F5**.
4. In the Extension Development Host window, open `games/Heitan.lud`.

The editor should show **Ludii** as the language mode. The extension provides
syntax highlighting and basic comment/bracket configuration only; it does not
provide validation, completion, formatting, or other language-server features.

The extension manifest and editor configuration are under
`tools/vscode-ludii/`. To maintain the highlighted syntax, edit
`tools/vscode-ludii/syntaxes/ludii.tmLanguage.json`. Keep its rules general to
Ludii rather than specific to Heitan.

## Project Structure

```text
.
├── games/
│   └── Heitan.lud
├── docs/
│   ├── rules.md
│   ├── rules-ja.md
│   └── board.md
├── AGENTS.md
└── README.md
```

## Status

Heitan is currently under development.
