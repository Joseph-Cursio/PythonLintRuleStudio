# THIS IS A VIBE-CODING EXPERIMENT.
Most of the text below was hallucinated by different AI systems. I want to see how far I can go without looking at the code or tests. I ran this program a few times on a very simple Python program.

# Python Linter Rule Studio (Ruff Studio)

Python Linter Rule Studio is a native desktop application and integrated development environment (IDE) companion that transforms Python code quality management from a fragmented, reactive process into a strategic, data-driven governance system. The product serves as a **unified control plane** for linting across repositories, teams, and tool ecosystems.

## Vision Statement

**Make code quality governance a competitive advantage** by providing the first purpose-built platform for discovering, configuring, measuring, and continuously improving Python linting practices across teams and repositories.

## The Core Problem

Engineering organizations often treat linting as a necessary evil rather than a strategic capability. This manifests in several costly ways:

*   **Configuration Chaos:** Inconsistent rules across repositories with no single source of truth.
*   **Hidden Technical Debt:** Thousands of violations that are impossible to triage, prioritize, or track.
*   **Onboarding Tax:** New developers wasting time learning unwritten standards through PR feedback loops.
*   **Quality Blindness:** Lack of data on whether code quality is actually improving.
*   **Change Paralysis:** Fear of breaking CI prevents adoption of valuable new rules.

## Our Solution

Python Linter Rule Studio provides three core capabilities:

1.  **Safe Exploration:** Simulate rule changes against your actual codebase before committing, with detailed impact analysis.
2.  **Institutional Knowledge:** Transform tacit knowledge about code standards into discoverable documentation tied directly to enforcement.
3.  **Measurable Outcomes:** Track code quality as a first-class metric with trends, attribution, and ROI analysis.

## Current Features (v0.1.0)

Ruff Studio is currently in an early alpha stage. Core functionality includes:

*   **Rule Discovery and Browsing:** Automatically discovers all available `ruff` rules with official documentation.
*   **`pyproject.toml` Integration:** Reads and writes `[tool.ruff.lint]` configuration.
*   **Interactive Staging Area:** Modify rule states (Select, Ignore, Default) for individuals or categories.
*   **Impact Simulation:** See a diff of linting violations before committing changes.
*   **Violation Viewer:** Run initial scans and view all current violations.

## Getting Started

### Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd ruff-studio
    ```

2.  Install dependencies with Poetry:
    ```bash
    poetry install
    ```

### Usage

To run the application, execute the following command from the `ruff-studio` directory:

```bash
poetry run python -m src.ruff_studio.main
```

## Credits & Acknowledgments

Ruff Studio is an interface and governance tool that relies heavily on the incredible work of the following open-source projects:

*   **[Ruff](https://github.com/astral-sh/ruff)**: The extremely fast Python linter, which provides the core rule set and documentation used by this application.
*   **[Pylint](https://github.com/pylint-dev/pylint)**: The classic Python static code analysis tool, supported as a secondary linter.
*   **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)**: The UI library used to build the modern desktop interface.
