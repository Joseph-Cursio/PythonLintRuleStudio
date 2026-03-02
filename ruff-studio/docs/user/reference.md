# Ruff Studio Reference Guide

## UI Components

### 1. Toolbar
The top bar contains project-level controls:
- **Select Directory:** Opens a file dialog to choose a project workspace.
- **Apply Profile:** Select a predefined linting profile (e.g., Standard, Strict).
- **Simulate Changes:** Runs a "dry-run" scan with staged changes.
- **Apply Changes:** Saves staged changes to `pyproject.toml`.
- **Pre-commit:** Generates a `.pre-commit-config.yaml` based on current settings.
- **Status Label:** Displays current activity (e.g., "Scanning...", "Fetching Docs...").

### 2. Rules Panel
A categorized list of all discovered linter rules.
- **Category Header:** Displays the category name (e.g., "Pyflakes (F)"). Use the arrow to expand/collapse.
- **Rule Item:** Shows the rule code (e.g., "F401") and its name.
- **Staging Controls:** Three radio buttons for each rule and category:
  - **Sel (Select):** Explicitly enable.
  - **Ign (Ignore):** Explicitly disable.
  - **Def (Default):** Use linter's default.
- **Effective State:** A checkbox indicating if the rule is *currently* enabled (even if via default).

### 3. Info Panel (Documentation)
Displays rich information for the currently selected rule:
- **Name and Code:** The canonical identifiers.
- **Source:** Whether the rule comes from Ruff or Pylint.
- **Summary:** A brief description of the rule's purpose.
- **Official Docs:** Fetched and cached documentation directly from the linter's repository.

### 4. Results Panel (Violations)
Lists linting violations found in the project.
- **Scan Results:** Shows current violations on disk.
- **Simulation Results:** Shows the *projected* violations if staged changes were applied.
- **Violation Item:** Includes the rule code, file path, line/column, and the violation message.

## Configuration Files
Ruff Studio primarily manages `pyproject.toml`. It specifically targets:
- `[tool.ruff.lint.select]`
- `[tool.ruff.lint.ignore]`
- `[tool.pylint.messages_control.disable]` (for Pylint rules)

## Profiles
Profiles are predefined sets of linting rules.
- **Built-in Profiles:**
  - **Standard:** A balanced rule set suitable for most projects.
  - **Strict:** Enables more aggressive rules for higher code quality.
- **Profile Comparison:** Use the comparison tool to see the differences between two profiles.
