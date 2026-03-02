# Tutorial: Safely Enabling a New Linting Rule

## Scenario
You want to improve your code quality by enabling a new rule (e.g., `F401 - Unused Import`), but you want to see exactly how many files it will affect before you commit to the change.

## Step 1: Open Your Project
1.  Launch Ruff Studio.
2.  Click **Select Directory** in the toolbar.
3.  Choose your project's root folder (the one containing `pyproject.toml`).
4.  Ruff Studio will automatically scan your project and display existing violations in the **Results** panel.

## Step 2: Find the New Rule
1.  Locate the **Pyflakes (F)** category in the **Rules** panel.
2.  Click the arrow (▼) to expand the category.
3.  Scroll down to find rule **F401**.
4.  Click on the rule name. Notice the **Info** panel updates with the rule's documentation, including why it's important and examples of what it catches.

## Step 3: Stage the Change
1.  Currently, the rule might be in its **Default** state.
2.  In the **Rules** panel, for rule **F401**, click the **Sel (Select)** radio button.
3.  Notice that the **Simulate Changes** button in the toolbar is now enabled. Your change is **staged** locally but not yet saved to your project files.

## Step 4: Run a Simulation
1.  Click **Simulate Changes** in the toolbar.
2.  Ruff Studio will perform a dry-run scan using your new staged configuration.
3.  Watch the **Results** panel. It will switch to **Simulation Results**.
4.  Review the list. It shows exactly which lines in which files currently violate the `F401` rule.
5.  Check the status bar for a summary (e.g., "Simulation complete: 12 new violations would be introduced").

## Step 5: Apply the Changes
1.  If you are comfortable with the number of violations and want to proceed, click **Apply Changes** in the toolbar.
2.  A **Proposal** window will appear, showing you the exact diff of the changes that will be made to your `pyproject.toml` file.
3.  Click **Save Changes** in the Proposal window.
4.  Ruff Studio will write the updated configuration to your `pyproject.toml` file.

## Conclusion
You have now safely enabled a new rule! By simulating the change first, you avoided a surprise "CI breakage" and were able to see the exact remediation work required.
