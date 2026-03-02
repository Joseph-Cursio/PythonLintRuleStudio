# GEMINI.md - Python Linter Rule Studio (Ruff Studio)

## Project Overview
**Python Linter Rule Studio** (also known as **Ruff Studio**) is a desktop application designed to manage, simulate, and govern Python linting configurations. It serves as a unified control plane for linting across repositories, primarily focusing on **Ruff**, with support for **Pylint**.

### Core Technologies
- **Language:** Python 3.12+
- **Dependency Management:** [Poetry](https://python-poetry.org/)
- **UI Framework:** [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- **Configuration Parsing:** [tomlkit](https://github.com/sdispater/tomlkit)
- **Linters:** [Ruff](https://github.com/astral-sh/ruff), [Pylint](https://github.com/pylint-dev/pylint)
- **Testing:** `unittest` (primary) and `pytest` (available in dev dependencies)

### Architecture
The project is structured as a modular Python application:
- `src/ruff_studio/main.py`: The entry point and primary UI logic using CustomTkinter.
- `src/ruff_studio/ruff_adapter.py`: Interface for interacting with the Ruff CLI, including rule discovery and scanning.
- `src/ruff_studio/pylint_adapter.py`: Interface for Pylint.
- `src/ruff_studio/config_manager.py`: Handles reading and writing `pyproject.toml` configurations.
- `src/ruff_studio/workspace_analyzer.py`: Analyzes local workspaces for linting violations.
- `src/ruff_studio/profile_manager.py`: Manages linting profiles (e.g., standard, strict).

---

## Building and Running
All commands should be executed from the `ruff-studio/` directory.

### Installation
```bash
cd ruff-studio
poetry install
```

### Running the Application
```bash
poetry run python -m src.ruff_studio.main
```

### Running Tests
The project uses `unittest` for its test suite.
```bash
poetry run python -m unittest discover tests
```
Alternatively, `pytest` is available:
```bash
poetry run pytest
```

---

## Development Conventions

### Coding Style
- **Formatting:** Follows Ruff's default formatting (line length 88).
- **Linting:** Configured in `pyproject.toml` under `[tool.ruff.lint]` (selects `E` and `F` rules by default).
- **UI:** Built using `CustomTkinter` widgets for a modern look.

### Testing Practices
- Tests are located in the `tests/` directory.
- Mocking is heavily used (via `unittest.mock`) to isolate adapters from actual CLI calls and filesystem side effects.
- New features should include corresponding tests in `tests/test_<module_name>.py`.

### UI Development
- The application uses a main window defined in `main.py`.
- Tooltips and secondary windows (like `ProfileComparisonWindow`) are implemented as helper classes within `main.py` or separate modules.

---

## Key Files
- `ruff-studio/pyproject.toml`: Project metadata, dependencies, and tool configurations.
- `ruff-studio/src/ruff_studio/main.py`: The "heart" of the application, managing the UI and orchestration.
- `ruff-studio/src/ruff_studio/ruff_adapter.py`: Core logic for Ruff integration.
- `ruff-studio/src/ruff_studio/profiles/`: Contains YAML definitions for linting profiles.
- `ruff-studio/docs/`: Additional analysis and vision documents.
