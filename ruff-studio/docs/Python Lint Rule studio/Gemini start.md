To help Jules start the Python Linter Rule Studio project, you can provide him with the following scoped-out details derived from the Product Requirements Document (PRD) and the initial technical roadmap.

1. Project Vision & Core Problem
The goal is to move from a fragmented, reactive linting process to a strategic "LintOps" governance system. Jules is building a unified control plane for Python code quality, specifically addressing:
 * Configuration Chaos: Inconsistent linting rules across multiple repositories.
 * Change Paralysis: Fear of breaking CI when enabling new rules.
 * Lack of Analytics: No easy way to track if code quality is actually improving over time.

1. Week 1: Phase 0 MVP Technical Scope
Jules should focus on establishing the "Safe Exploration" prototype this week.

Core Architecture (Day 1)
 * Abstract LinterAdapter: Create a base class that defines common behaviors for any linter (e.g., fetching rules, running scans, parsing output).
 * Ruff Adapter: Implement the first concrete version of this adapter specifically for Ruff to leverage its speed and extensive rule set.
 * Technology Stack: Use poetry or uv for dependency management to ensure a reproducible environment.

Safe-Guard Configuration (Day 2)
 * Requirement: Any programmatic changes to a user's pyproject.toml must preserve comments and formatting.
 * Implementation: Use tomlkit, a style-preserving TOML library, for all read/write operations.

Workspace & Data Layer (Day 3)
 * Storage: Use SQLite to store rule metadata and scan results. This allows for historical tracking and fast querying without needing a heavy database server.
 * Schema: Jules needs to design a schema that maps rules to specific violations and file paths.

Impact Simulation (Day 4)
 * The "Aha!" Moment: Jules needs to build a "Hypothetical Run" logic.
 * Delta Reporting: Instead of just showing total violations, the tool should calculate the net change: "If you enable rule X, you will have 12 new violations in 3 files".

Internal CLI (Day 5)
 * Developer Interface: Build a CLI using click or typer.
 * Example Commands:
   * studio analyze: Scans the current repo and saves results to SQLite.
   * studio simulate --enable S101: Runs a simulated check without modifying the actual config file.

3. Critical Technical Warning
The PRD targets a high performance standard: scanning 10,000 files in under 30 seconds.
 * Strategy: Jules must avoid hitting a bottleneck by using multiprocessing or concurrent.futures to call linter subprocesses in parallel.
 * Recommendation: Use a ProcessPoolExecutor to distribute the linting workload across CPU cores.

3. Immediate Next Steps
 * Initialize the Repo: Set up the structure using poetry.
 * Boilerplate Support: Ask for help writing the LinterAdapter interface or the SQLite initialization script if needed.
 * Validation: Ensure the tomlkit round-trip parsing doesn't destroy manual formatting in a test pyproject.toml.
