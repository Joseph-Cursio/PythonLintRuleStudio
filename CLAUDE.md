# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Python Linter Rule Studio (Ruff Studio)** is a desktop GUI application for managing, simulating, and governing Python linting configurations. It acts as a unified control plane for Ruff and Pylint across repos.

All application code lives under `ruff-studio/`. Commands below assume you are in that directory.

## Setup

```bash
cd ruff-studio
poetry install
```

## Common Commands

```bash
# Run the application
poetry run python -m src.ruff_studio.main

# Run all tests
poetry run pytest

# Run a single test file
poetry run pytest tests/test_ruff_adapter.py

# Run a single test by name
poetry run pytest tests/test_ruff_adapter.py::TestClassName::test_method_name

# Lint the codebase
poetry run ruff check src/
```

## Architecture

The application follows a controller/view pattern:

- **`controller.py` (`StudioController`)** — Central state manager. Holds `current_directory`, `all_rules`, `staged_changes`, `base_scan_results`. Runs background workers via `run_in_thread()` and communicates results back to the UI via a `queue.Queue`. UI callbacks `on_state_changed` and `on_scan_finished` are set by the `App`.

- **`main.py` (`App`)** — The `customtkinter` root window. Initializes `StudioController`, wires up UI panels, polls the queue with `process_queue()`, and dispatches actions to the controller. Supports `headless=True` mode for testing (mocks `self.tk`).

- **`ui/`** — Individual UI components, each as a class:
  - `Sidebar` — Navigation rail and workspace/profile selection
  - `RulesView` — Hosts `RulesPanel`, `InfoPanel`, `ResultsPanel`, `Toolbar`
  - `AnalyticsView`, `ProposalsView`, `ProfileComparisonWindow`, `ProposalWindow` — Secondary views

- **`ruff_adapter.py`** — Wraps the Ruff CLI via `subprocess`. Provides rule discovery (combining `ruff rule --all` JSON with web-scraped docs), scanning, and simulation (diffing scan results using a temp `pyproject.toml`).

- **`pylint_adapter.py`** — Same interface pattern as `ruff_adapter` but for Pylint.

- **`config_manager.py`** — Reads/writes `pyproject.toml` using `tomlkit` to preserve formatting.

- **`workspace_analyzer.py` (`WorkspaceAnalyzer`)** — Runs full scans, normalizes results into `UnifiedViolationModel` dataclasses, and stores them in SQLite via `database_manager.py`. Enriches violations with git blame data via `git_adapter.py`.

- **`database_manager.py`** — SQLite helpers for `scan_runs` and `violations` tables.

- **`proposal_manager.py`** — Manages proposed rule changes as saveable/loadable objects.

- **`profile_manager.py`** — Loads YAML-defined linting profiles from `src/ruff_studio/profiles/`.

- **`cache_manager.py`** — Caches rule metadata (docs, descriptions) to avoid repeated network/CLI calls.

- **`ci_integration.py`** — Generates CI config snippets (GitHub Actions, etc.) from the current rule configuration.

## Testing

Tests are in `ruff-studio/tests/` and mirror the module structure (`test_<module>.py`). All adapter and filesystem calls are mocked using `unittest.mock`. The `App` can be instantiated in `headless=True` mode for UI tests without a display.

Coverage is configured to run automatically with `pytest` (outputs to terminal and `htmlcov/`).
