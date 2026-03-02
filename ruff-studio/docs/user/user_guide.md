# Ruff Studio User Guide

## Overview
Python Linter Rule Studio (Ruff Studio) is a unified control plane for managing Python linting across your projects. It allows you to discover rules, safely simulate configuration changes, and manage linting as a strategic governance system rather than a fragmented set of configuration files.

## Core Concepts

### 1. Rule Discovery and Browsing
Ruff Studio automatically discovers all available rules from your installed version of **Ruff** (and supported **Pylint** rules). Rules are organized into collapsible categories (e.g., Pyflakes, Pycodestyle) making it easy to browse the vast rule set.

### 2. Interactive Staging Area
When you modify a rule's state (Select, Ignore, or Default), those changes are **staged**. They are kept in a local state and do not modify your `pyproject.toml` file until you explicitly choose to apply them.

- **Select:** Explicitly enable the rule.
- **Ignore:** Explicitly disable the rule.
- **Default:** Rely on the linter's default behavior for this rule.

### 3. Impact Simulation
Before applying any changes, use the **Simulate Changes** feature. Ruff Studio will run a "dry-run" scan using your staged configuration and show you exactly what would happen:
- Which violations would be fixed.
- Which new violations would be introduced.
- The net change in code quality.

### 4. Applying Changes
Once you are satisfied with your staged changes, click **Apply Changes**. This will:
- Update your `pyproject.toml` file with the new configuration.
- Preserve existing formatting in the file.
- Optionally trigger a full workspace scan to update the violation results.

## Getting Started
1. **Select a Project:** Use the "Select Directory" button to open a Python project containing a `pyproject.toml` file.
2. **Review Violations:** The "Results" panel will display current linting violations in your codebase.
3. **Explore Rules:** Browse the "Rules" panel. Select a rule to see its official documentation in the "Info" panel.
4. **Stage Changes:** Toggle rule states and watch the "Simulate" button become active.
5. **Simulate:** Click "Simulate" to see the impact of your changes in the results panel.
6. **Apply:** Click "Apply Changes" to save your configuration.
