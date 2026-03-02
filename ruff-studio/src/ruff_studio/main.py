import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import tomlkit
import threading
import queue
import copy
import uuid
import json
from unittest.mock import MagicMock
from . import (
    ruff_adapter, config_manager, workspace_analyzer, profile_manager, 
    ci_integration, pylint_adapter, git_adapter, proposal_manager
)
from .controller import StudioController
from .ui.proposal_window import ProposalWindow
from .ui.dashboard_window import ProposalsDashboard
from .ui.comparison_window import ProfileComparisonWindow

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        if self.tooltip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip_window = ctk.CTkToplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        label = ctk.CTkLabel(self.tooltip_window, text=self.text, corner_radius=5,
                             bg_color="white", text_color="black")
        label.pack(ipadx=5)

    def hide_tooltip(self, event):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None


class App(ctk.CTk):
    def __init__(self, headless=False):
        if not headless:
            super().__init__()
            self.title("Ruff Studio")
            self.geometry("1280x800")
            self._init_ui()
        else:
            self.tk = MagicMock()

        self.controller = StudioController()
        self.rule_widgets = {}
        self.selected_rule_frame = None
        self.selected_category_frame = None

        if not headless:
            self.controller.run_in_thread(
                self.controller.discover_rules_worker, "discover_rules"
            )
            self.process_queue()

    @property
    def analyzer(self):
        return self.controller.analyzer

    @property
    def current_directory(self):
        return self.controller.current_directory

    @property
    def pyproject_path(self):
        return self.controller.pyproject_path

    @property
    def pyproject_data(self):
        return self.controller.pyproject_data

    @property
    def staged_changes(self):
        return self.controller.staged_changes

    def _init_ui(self):
        # Create main layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=0) # Sash
        self.grid_columnconfigure(2, weight=2)
        self.grid_columnconfigure(3, weight=0) # Sash
        self.grid_columnconfigure(4, weight=3)

        # --- Top Bar ---
        self.top_frame = ctk.CTkFrame(self, height=50)
        self.top_frame.grid(
            row=0, column=0, columnspan=5, sticky="ew", padx=10, pady=10
        )

        self.select_button = ctk.CTkButton(
            self.top_frame, text="Select Directory", command=self.select_directory
        )
        self.select_button.pack(side="left", padx=10)
        self.directory_label = ctk.CTkLabel(
            self.top_frame, text="No directory selected"
        )
        self.directory_label.pack(side="left", padx=10)

        self.action_frame = ctk.CTkFrame(self.top_frame)
        self.action_frame.pack(side="right", padx=10)
        self.simulate_button = ctk.CTkButton(
            self.action_frame, text="Simulate Changes", state="disabled",
            command=self.simulate_changes
        )
        self.simulate_button.pack(side="left", padx=5)
        self.apply_button = ctk.CTkButton(
            self.action_frame, text="Apply Changes", state="disabled",
            command=self.apply_changes
        )
        self.apply_button.pack(side="left", padx=5)

        self.profile_menu = ctk.CTkOptionMenu(
            self.action_frame,
            values=["Apply a Profile..."] + profile_manager.get_built_in_profiles(),
            command=self.apply_profile
        )
        self.profile_menu.pack(side="left", padx=5)
        self.profile_menu.set("Apply a Profile...")
        self.profile_menu.configure(state="disabled")

        self.compare_profiles_button = ctk.CTkButton(
            self.action_frame, text="Compare Profiles", 
            command=self.open_comparison_window
        )
        self.compare_profiles_button.pack(side="left", padx=5)

        self.view_proposals_button = ctk.CTkButton(
            self.action_frame, text="View Proposals", 
            command=self.open_proposals_dashboard
        )
        self.view_proposals_button.pack(side="left", padx=5)

        self.generate_pre_commit_button = ctk.CTkButton(
            self.action_frame, text="Generate Pre-commit Config", 
            command=self.generate_pre_commit_config_file,
            state="disabled"
        )
        self.generate_pre_commit_button.pack(side="left", padx=5)

        self.status_label = ctk.CTkLabel(self.top_frame, text="")
        self.status_label.pack(side="right", padx=10)

        # --- Panels ---
        # Create a container for the rules panel and its header
        self.rules_panel_container = ctk.CTkFrame(self, fg_color="transparent")
        self.rules_panel_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=0)
        self.rules_panel_container.grid_rowconfigure(1, weight=1)
        self.rules_panel_container.grid_columnconfigure(0, weight=1)

        # --- Rules Panel Header ---
        self.rules_header_frame = ctk.CTkFrame(
            self.rules_panel_container, height=30, fg_color="transparent"
        )
        self.rules_header_frame.grid(row=0, column=0, sticky="ew", padx=5)
        # Make the label column expand
        self.rules_header_frame.grid_columnconfigure(3, weight=1)

        # Spacer for toggle button column
        ctk.CTkLabel(
            self.rules_header_frame, text="", width=20
        ).grid(row=0, column=0, padx=5)
        # "Enabled" label for checkbox column
        ctk.CTkLabel(
            self.rules_header_frame, text="Enabled", anchor="w"
        ).grid(row=0, column=1, padx=(0, 5))

        # Configure grid for radio button labels
        radio_header_frame = ctk.CTkFrame(
            self.rules_header_frame, fg_color="transparent"
        )
        radio_header_frame.grid(row=0, column=2)
        radio_header_frame.grid_columnconfigure(0, minsize=35)
        radio_header_frame.grid_columnconfigure(1, minsize=35)
        radio_header_frame.grid_columnconfigure(2, minsize=35)

        sel_label = ctk.CTkLabel(
            radio_header_frame, text="Sel", anchor="center", width=35
        )
        sel_label.grid(row=0, column=0)
        Tooltip(sel_label, "Select")

        ign_label = ctk.CTkLabel(
            radio_header_frame, text="Ign", anchor="center", width=35
        )
        ign_label.grid(row=0, column=1)
        Tooltip(ign_label, "Ignore")

        def_label = ctk.CTkLabel(
            radio_header_frame, text="Def", anchor="center", width=35
        )
        def_label.grid(row=0, column=2)
        Tooltip(def_label, "Default")


        self.rules_frame = ctk.CTkScrollableFrame(self.rules_panel_container)
        self.rules_frame.grid(row=1, column=0, sticky="nsew")
        self.rules_label = ctk.CTkLabel(self.rules_frame, text="Rules (Loading...)")
        self.rules_label.pack(pady=10)

        self.info_frame = ctk.CTkScrollableFrame(self)
        self.info_frame.grid(row=1, column=2, sticky="nsew", padx=10, pady=0)
        self.info_label = ctk.CTkLabel(self.info_frame, text="Rule Info")
        self.info_label.pack(pady=10)

        self.results_frame = ctk.CTkScrollableFrame(self)
        self.results_frame.grid(row=1, column=4, sticky="nsew", padx=0, pady=0)
        self.results_label = ctk.CTkLabel(self.results_frame, text="Scan Results")
        self.results_label.pack(pady=10)

        # --- Sashes for resizing ---
        self.sash1 = ctk.CTkFrame(self, width=4, cursor="sb_h_double_arrow")
        self.sash1.grid(row=1, column=1, sticky="ns")
        self.sash1.bind("<Button-1>", lambda e: self.start_resize(e, 0))
        self.sash1.bind("<B1-Motion>", self.do_resize)

        self.sash2 = ctk.CTkFrame(self, width=4, cursor="sb_h_double_arrow")
        self.sash2.grid(row=1, column=3, sticky="ns")
        self.sash2.bind("<Button-1>", lambda e: self.start_resize(e, 2))
        self.sash2.bind("<B1-Motion>", self.do_resize)

        self.resize_start_x = 0
        self.resize_start_col = 0

        self.bind("<Up>", self.navigate_items)
        self.bind("<Down>", self.navigate_items)

    def start_resize(self, event, col):
        self.resize_start_x = event.x_root
        self.resize_start_col = col

    def do_resize(self, event):
        delta = event.x_root - self.resize_start_x

        # Adjust column weights
        weight0 = self.grid_columnconfigure(0)['weight']
        weight2 = self.grid_columnconfigure(2)['weight']
        weight4 = self.grid_columnconfigure(4)['weight']

        if self.resize_start_col == 0:
            new_weight0 = max(1, weight0 + delta)
            new_weight2 = max(1, weight2 - delta)
            self.grid_columnconfigure(0, weight=new_weight0)
            self.grid_columnconfigure(2, weight=new_weight2)
        else: # col == 2
            new_weight2 = max(1, weight2 + delta)
            new_weight4 = max(1, weight4 - delta)
            self.grid_columnconfigure(2, weight=new_weight2)
            self.grid_columnconfigure(4, weight=new_weight4)

        self.resize_start_x = event.x_root


    def run_in_thread(self, worker, command_name, *args):
        self.select_button.configure(state="disabled")
        self.status_label.configure(text="Running...")
        self.controller.run_in_thread(worker, command_name, *args)

    def process_queue(self):
        try:
            while True:
                command, data = self.controller.queue.get_nowait()

                if command == "error":
                    error_message = f"An unexpected error occurred:\n\n{data}"
                    messagebox.showerror("Error", error_message)
                elif command == "discover_rules":
                    self.controller.all_rules = data
                    self.rules_label.configure(text="Rules")
                    self.populate_rules_initial()
                elif command == "run_full_scan":
                    self.controller.base_scan_results = data
                    self.update_results_panel(data)
                elif command == "run_simulation":
                    self.update_simulation_results_panel(data)

                self.select_button.configure(state="normal")
                self.status_label.configure(text="")
                self.controller.queue.task_done()

        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    def select_directory(self, directory=None):
        if not directory:
            directory = filedialog.askdirectory()

        if directory:
            self.controller.set_directory(directory)
            self.directory_label.configure(text=directory)
            
            # Clear UI results
            for widget in self.results_frame.winfo_children():
                if widget != self.results_label:
                    widget.destroy()
            self.results_label.configure(text="Scanning...")

            self.controller.run_in_thread(
                self.controller.run_full_scan_worker, "run_full_scan", directory
            )
            self.update_rules_panel()
            self.profile_menu.configure(state="normal")
            self.generate_pre_commit_button.configure(state="normal")

    def update_results_panel(self, results):
        self.results_label.configure(text=f"Scan Results ({len(results)} violations)")
        for widget in self.results_frame.winfo_children():
            if widget != self.results_label:
                widget.destroy()

        if not results:
            ctk.CTkLabel(self.results_frame, text="No issues found.").pack(pady=5)
            return

        for result in results:
            author_info = f" (Author: {result.author})" if result.author else ""
            result_text = (
                f"{result.file_path}:{result.line_number}:"
                f"{result.column} {result.rule_id}{author_info}\n"
                f"  {result.message}"
            )
            ctk.CTkLabel(
                self.results_frame, text=result_text,
                wraplength=self.results_frame.winfo_width()-50, justify="left",
                anchor="w"
            ).pack(pady=2, fill="x", padx=5)

    def _make_hashable(self, data):
        if hasattr(data, '__dict__'):
            data = data.__dict__
        if isinstance(data, dict):
            return tuple(sorted((k, self._make_hashable(v)) for k, v in data.items()))
        if isinstance(data, list):
            return tuple(self._make_hashable(v) for v in data)
        return data

    def update_simulation_results_panel(self, sim_results):
        self.results_label.configure(text="Simulation Results")
        for widget in self.results_frame.winfo_children():
            if widget != self.results_label:
                widget.destroy()

        base_set = {self._make_hashable(d) for d in self.base_scan_results}
        sim_set = {self._make_hashable(d) for d in sim_results}

        new_violations = [dict(s) for s in sim_set - base_set]
        fixed_violations = [dict(s) for s in base_set - sim_set]

        summary = (
            f"Simulation complete: {len(new_violations)} new violations, "
            f"{len(fixed_violations)} fixed violations."
        )
        ctk.CTkLabel(
            self.results_frame, text=summary, font=("", 14, "bold")
        ).pack(pady=10)

        if new_violations:
            ctk.CTkLabel(
                self.results_frame, text="New Violations:", font=("", 12, "underline")
            ).pack(pady=5)
            for result in new_violations:
                result_text = (
                    f"+ {result['filename']}:{result['location']['row']}:"
                    f"{result['location']['column']} {result['code']}\n"
                    f"  {result['message']}"
                )
                ctk.CTkLabel(
                    self.results_frame, text=result_text,
                    wraplength=self.results_frame.winfo_width()-50, justify="left"
                ).pack(pady=2, anchor="w")

        if fixed_violations:
            ctk.CTkLabel(
                self.results_frame, text="Fixed Violations:", font=("", 12, "underline")
            ).pack(pady=5)
            for result in fixed_violations:
                result_text = (
                    f"- {result['filename']}:{result['location']['row']}:"
                    f"{result['location']['column']} {result['code']}\n"
                    f"  {result['message']}"
                )
                ctk.CTkLabel(
                    self.results_frame, text=result_text,
                    wraplength=self.results_frame.winfo_width()-50, justify="left"
                ).pack(pady=2, anchor="w")

    def populate_rules_initial(self):
        # Use the natural insertion order of categories from the dictionary
        categories = self.controller.all_rules.items()

        # Create a list of navigable items (categories and rules) in display order
        self.controller.navigable_items = []
        for category_name, category_data in categories:
            category_item = {
                'type': 'category', 'name': category_name, 'data': category_data
            }
            self.controller.navigable_items.append(category_item)
            sorted_rules = sorted(
                category_data['rules'], key=lambda r: r['code']
            )
            for rule in sorted_rules:
                rule_item = {
                    'type': 'rule', 'data': rule, 'category_name': category_name
                }
                self.controller.navigable_items.append(rule_item)


        for category_name, category_data in categories:
            # --- Category Header ---
            category_frame = ctk.CTkFrame(self.rules_frame)
            category_frame.pack(fill="x", pady=(5, 1), padx=5)
            # Label column
            category_frame.grid_columnconfigure(3, weight=1)

            # Allow the category header itself to be selected
            category_frame.bind(
                "<Button-1>", 
                lambda event, cn=category_name: self.select_category(cn)
            )

            effective_state_var = ctk.StringVar()
            toggle_button = ctk.CTkButton(
                category_frame, text="▼", width=20,
                command=lambda cn=category_name: self.toggle_category_rules(cn)
            )
            toggle_button.grid(row=0, column=0, padx=5, pady=2)

            effective_state_indicator = ctk.CTkCheckBox(
                category_frame, text="", variable=effective_state_var,
                onvalue="on", offvalue="off", state="disabled"
            )
            effective_state_indicator.grid(row=0, column=1, padx=(0, 5))

            # Radio buttons for category
            radio_frame = ctk.CTkFrame(category_frame, fg_color="transparent")
            radio_frame.grid(row=0, column=2)
            radio_frame.grid_columnconfigure(0, minsize=35)
            radio_frame.grid_columnconfigure(1, minsize=35)
            radio_frame.grid_columnconfigure(2, minsize=35)

            radio_var = ctk.StringVar(value="default")
            select_rb = ctk.CTkRadioButton(
                radio_frame, text="", variable=radio_var, value="select", 
                width=35, radiobutton_width=18, radiobutton_height=18, 
                command=lambda p=category_data['prefix']: (
                    self.stage_category_change(p, "select")
                )
            )
            ignore_rb = ctk.CTkRadioButton(
                radio_frame, text="", variable=radio_var, value="ignore", 
                width=35, radiobutton_width=18, radiobutton_height=18, 
                command=lambda p=category_data['prefix']: (
                    self.stage_category_change(p, "ignore")
                )
            )
            default_rb = ctk.CTkRadioButton(
                radio_frame, text="", variable=radio_var, value="default", 
                width=35, radiobutton_width=18, radiobutton_height=18, 
                command=lambda p=category_data['prefix']: (
                    self.stage_category_change(p, "default")
                )
            )

            select_rb.grid(row=0, column=0)
            ignore_rb.grid(row=0, column=1)
            default_rb.grid(row=0, column=2)

            category_label = ctk.CTkLabel(
                category_frame, 
                text=f"{category_name} ({category_data['prefix']})", anchor="w"
            )
            category_label.grid(row=0, column=3, sticky="w", padx=10)

            # --- Rules Container ---
            rules_container = ctk.CTkFrame(self.rules_frame, fg_color="transparent")
            rules_container.pack(fill="x", padx=(25, 5))

            self.rule_widgets[category_name] = {
                'category_frame': category_frame,
                'effective_state_indicator': effective_state_indicator,
                'effective_state_variable': effective_state_var,
                'radio_variable': radio_var,
                'prefix': category_data['prefix'],
                'rules_container': rules_container,
                'toggle_button': toggle_button,
                'rules': {}
            }

            for rule in sorted(category_data['rules'], key=lambda r: r['code']):
                frame = ctk.CTkFrame(rules_container)
                frame.pack(fill="x", pady=1)
                # Label column
                frame.grid_columnconfigure(3, weight=1)

                # Spacer to align with category toggle button
                ctk.CTkLabel(frame, text="", width=20).grid(row=0, column=0, padx=5)

                # Effective state indicator for the rule
                rule_effective_state_var = ctk.StringVar()
                rule_effective_indicator = ctk.CTkCheckBox(
                    frame, text="", variable=rule_effective_state_var,
                    onvalue="on", offvalue="off", state="disabled"
                )
                rule_effective_indicator.grid(row=0, column=1, padx=(0, 5))

                rule_text = f"{rule['code']}"
                if rule['status'] != 'stable':
                    rule_text += f" (⚠️ {rule['status']})"

                # Radio buttons for the rule
                rule_radio_frame = ctk.CTkFrame(frame, fg_color="transparent")
                rule_radio_frame.grid(row=0, column=2)
                rule_radio_frame.grid_columnconfigure(0, minsize=35)
                rule_radio_frame.grid_columnconfigure(1, minsize=35)
                rule_radio_frame.grid_columnconfigure(2, minsize=35)

                rule_radio_var = ctk.StringVar(value="default")
                rule_select_rb = ctk.CTkRadioButton(
                    rule_radio_frame, text="", variable=rule_radio_var, 
                    value="select", width=35, radiobutton_width=18, 
                    radiobutton_height=18, 
                    command=lambda rc=rule['code']: (
                        self.stage_rule_change(rc, "select")
                    )
                )
                rule_ignore_rb = ctk.CTkRadioButton(
                    rule_radio_frame, text="", variable=rule_radio_var, 
                    value="ignore", width=35, radiobutton_width=18, 
                    radiobutton_height=18, 
                    command=lambda rc=rule['code']: (
                        self.stage_rule_change(rc, "ignore")
                    )
                )
                rule_default_rb = ctk.CTkRadioButton(
                    rule_radio_frame, text="", variable=rule_radio_var, 
                    value="default", width=35, radiobutton_width=18, 
                    radiobutton_height=18, 
                    command=lambda rc=rule['code']: (
                        self.stage_rule_change(rc, "default")
                    )
                )

                rule_select_rb.grid(row=0, column=0)
                rule_ignore_rb.grid(row=0, column=1)
                rule_default_rb.grid(row=0, column=2)

                label = ctk.CTkLabel(
                    frame, text=f"{rule_text}: {rule['name']}", anchor="w"
                )
                label.grid(row=0, column=3, sticky="w", padx=10)

                if rule['status'] != 'stable':
                    Tooltip(label, f"This rule is {rule['status']}.")

                label.bind(
                    "<Button-1>", 
                    lambda event, r=rule, cn=category_name: (
                        self.show_rule_info(r, cn)
                    )
                )

                rule_widget_data = {
                    'effective_state_indicator': rule_effective_indicator,
                    'effective_state_variable': rule_effective_state_var,
                    'radio_variable': rule_radio_var,
                    'rule_info': rule,
                    'frame': frame
                }
                self.rule_widgets[category_name]['rules'][rule['code']] = (
                    rule_widget_data
                )

    def _get_ruff_rules_from_config(self, ruff_config):
        """
        Get the set of enabled ruff rule codes from a ruff config dict.
        """
        selected_codes = ruff_config.get("select", [])
        ignored_codes = ruff_config.get("ignore", [])

        # This is a simplified version. A more robust solution would
        # need to handle prefix expansion. For now, we assume codes are explicit.

        enabled = set()
        if not isinstance(self.all_rules, dict):
            return enabled

        all_managed_codes = {
            rule["code"] for cat in self.all_rules.values() for rule in cat["rules"]
        }

        for code in all_managed_codes:
            is_selected = False
            for selected in selected_codes:
                if code.startswith(selected):
                    is_selected = True
                    break

            if is_selected:
                is_ignored = False
                for ignored in ignored_codes:
                    if code.startswith(ignored):
                        is_ignored = True
                        break
                if not is_ignored:
                    enabled.add(code)
        return enabled

    def is_rule_enabled(self, rule_code):
        return rule_code in self.enabled_rules

    def is_pylint_rule(self, code):
        """Checks if a rule code belongs to a Pylint category."""
        for cat_name, cat_data in self.all_rules.items():
            if cat_name.startswith("Pylint:"):
                for rule in cat_data['rules']:
                    if rule['code'] == code:
                        return True
        return False

    def _get_effective_rule_state(self, rule_code, category_prefix):
        """
        Calculates the final on/off state of a rule based on the hierarchy.
        """
        if rule_code in self.staged_changes:
            state = self.staged_changes[rule_code]
            if state == "select":
                return True
            if state == "ignore":
                return False

        if category_prefix in self.staged_changes:
            state = self.staged_changes[category_prefix]
            if state == "select":
                return True
            if state == "ignore":
                return False

        return self.is_rule_enabled(rule_code)

    def _get_pylint_rules_from_config(self, pylint_config):
        """
        Get the set of enabled pylint rule codes from a pylint config dict.
        Pylint rules are on by default and explicitly disabled.
        """
        disabled_codes = pylint_config.get("disable", [])

        all_pylint_codes = {
            rule["code"]
            for cat_name, cat in self.all_rules.items()
            if cat_name.startswith("Pylint:")
            for rule in cat["rules"]
        }

        enabled = set()
        for code in all_pylint_codes:
            is_disabled = False
            for disabled in disabled_codes:
                if code.startswith(disabled):
                    is_disabled = True
                    break
            if not is_disabled:
                enabled.add(code)
        return enabled

    def _get_explicit_rule_state(self, code, ruff_config, pylint_config=None):
        """
        Determines if a rule or category is explicitly selected, 
        ignored, or default for a given linter.
        """
        if self.is_pylint_rule(code):
            if pylint_config is not None:
                if code in pylint_config.get("disable", []):
                    return "ignore"
                if code in pylint_config.get("enable", []):
                    return "select"
            return "default"
        else:  # Assume ruff
            if code in ruff_config.get("select", []):
                return "select"
            if code in ruff_config.get("ignore", []):
                return "ignore"
            return "default"
    def update_rules_panel(self):
        if not self.controller.current_directory:
            return

        ruff_config, pylint_config = self.controller.get_effective_configs()

        for category_name, category_widgets in self.rule_widgets.items():
            prefix = category_widgets['prefix']

            # Update category radio buttons
            cat_state = self.controller.staged_changes.get(
                prefix, 
                self.controller.get_explicit_rule_state(prefix, ruff_config, pylint_config)
            )
            category_widgets['radio_variable'].set(cat_state)

            any_rule_on = False
            all_rules_on = True

            for rule_code, rule_widget in category_widgets['rules'].items():
                # Update rule radio buttons
                rule_state = self.controller.staged_changes.get(
                    rule_code, 
                    self.controller.get_explicit_rule_state(
                        rule_code, ruff_config, pylint_config
                    )
                )
                rule_widget['radio_variable'].set(rule_state)

                # Update effective state indicator
                is_on = self.controller.get_effective_rule_state(rule_code, prefix)
                rule_widget['effective_state_variable'].set("on" if is_on else "off")

                if is_on:
                    any_rule_on = True
                else:
                    all_rules_on = False

            # Update category effective state indicator
            if all_rules_on:
                category_widgets['effective_state_variable'].set("on")
            elif any_rule_on:
                # Indeterminate state could be better
                category_widgets['effective_state_variable'].set("on")
            else:
                category_widgets['effective_state_variable'].set("off")

    def stage_rule_change(self, rule_code, state):
        self.controller.staged_changes[rule_code] = state
        self.simulate_button.configure(state="normal")
        self.apply_button.configure(state="normal")
        self.update_rules_panel()

    def stage_category_change(self, prefix, state):
        self.controller.staged_changes[prefix] = state
        self.simulate_button.configure(state="normal")
        self.apply_button.configure(state="normal")
        
        # Clear individual rule stagings for this category
        for category_data in self.controller.all_rules.values():
            if category_data['prefix'] == prefix:
                for rule in category_data['rules']:
                    rule_code = rule['code']
                    if rule_code in self.controller.staged_changes:
                        del self.controller.staged_changes[rule_code]
                break
        self.update_rules_panel()

    def toggle_category_rules(self, category_name):
        container = self.rule_widgets[category_name]['rules_container']
        toggle_button = self.rule_widgets[category_name]['toggle_button']
        if container.winfo_viewable():
            container.pack_forget()
            toggle_button.configure(text="▶")
        else:
            container.pack(fill="x", padx=(25, 5))
            toggle_button.configure(text="▼")

    def simulate_changes(self):
        ruff_config, _ = self.controller.get_effective_configs()
        self.status_label.configure(text="Simulating...")
        self.controller.run_in_thread(
            self._run_simulation_worker, "run_simulation", ruff_config
        )

    def _run_simulation_worker(self, command, ruff_config):
        try:
            results = ruff_adapter.run_scan_with_config(
                self.controller.current_directory, ruff_config
            )
            self.controller.queue.put((command, results))
        except Exception as e:
            self.controller.queue.put(("error", str(e)))

    def apply_profile(self, profile_name):
        if profile_name == "Apply a Profile...":
            return

        try:
            profile_data = profile_manager.load_profile(profile_name)
            rules_all = profile_data.get("profile", {}).get("rules", {})
            profile_ruff_config = rules_all.get("ruff", {})

            self.controller.staged_changes = {}

            # --- Ruff Profile ---
            if profile_ruff_config:
                dummy_ruff_config = {
                    "select": profile_ruff_config.get("select", []), 
                    "ignore": profile_ruff_config.get("ignore", [])
                }
                profile_ruff_rules = self.controller._get_ruff_rules_from_config(
                    dummy_ruff_config
                )
                for cat_name, cat_widgets in self.rule_widgets.items():
                    if cat_name.startswith("Pylint:"):
                        continue
                    for rule_code in cat_widgets['rules'].keys():
                        if rule_code in profile_ruff_rules:
                            self.controller.staged_changes[rule_code] = "select"
                        else:
                            self.controller.staged_changes[rule_code] = "ignore"

            # --- Pylint Profile ---
            profile_pylint_config = rules_all.get("pylint", {})
            if profile_pylint_config:
                disabled = profile_pylint_config.get("disable", [])
                for cat_name, cat_widgets in self.rule_widgets.items():
                    if not cat_name.startswith("Pylint:"):
                        continue
                    for rule_code in cat_widgets['rules'].keys():
                        if rule_code in disabled:
                            self.controller.staged_changes[rule_code] = "ignore"
                        else:
                            self.controller.staged_changes[rule_code] = "default"

            self.update_rules_panel()
            self.simulate_button.configure(state="normal")
            self.apply_button.configure(state="normal")
            messagebox.showinfo("Profile Applied", f"Profile '{profile_name}' staged.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply profile: {e}")
        finally:
            self.profile_menu.set("Apply a Profile...")

    def apply_changes(self, show_proposal_window=True):
        if not self.controller.pyproject_data or not self.controller.pyproject_path:
            return

        ruff_config, pylint_config = self.controller.get_effective_configs()
        config_before = config_manager.read_pyproject_text(self.controller.pyproject_path)
        
        after_data = copy.deepcopy(self.controller.pyproject_data)
        config_manager.update_ruff_config(after_data, ruff_config)
        config_manager.update_pylint_config(after_data, pylint_config)
        config_after = config_manager.get_pyproject_text(after_data)

        if show_proposal_window:
            impact = ruff_adapter.run_scan_with_config(
                self.controller.current_directory, ruff_config
            )
            ProposalWindow(self, config_before, config_after, impact)
            return

        config_manager.update_ruff_config(self.controller.pyproject_data, ruff_config)
        config_manager.update_pylint_config(self.controller.pyproject_data, pylint_config)
        config_manager.write_pyproject(self.controller.pyproject_path, self.controller.pyproject_data)

        self.controller.staged_changes = {}
        self.simulate_button.configure(state="disabled")
        self.apply_button.configure(state="disabled")
        self.update_rules_panel()
        self.controller.run_in_thread(
            self.controller.run_full_scan_worker, "run_full_scan", 
            self.controller.current_directory
        )

    def open_comparison_window(self):
        ProfileComparisonWindow(self)

    def open_proposals_dashboard(self):
        ProposalsDashboard(self)

    def generate_pre_commit_config_file(self):
        try:
            ruff_version = ruff_adapter.get_ruff_version()
            config_content = ci_integration.generate_pre_commit_config(ruff_version)
            filepath = filedialog.asksaveasfilename(
                initialdir=self.controller.current_directory,
                initialfile=".pre-commit-config.yaml",
                defaultextension=".yaml",
                filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
            )
            if filepath:
                with open(filepath, "w") as f:
                    f.write(config_content)
                messagebox.showinfo("Success", f"Saved to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")

    def navigate_items(self, event):
        if not self.controller.navigable_items:
            return
        if event.keysym == "Up":
            self.controller.navigable_index = max(0, self.controller.navigable_index - 1)
        elif event.keysym == "Down":
            self.controller.navigable_index = min(
                len(self.controller.navigable_items) - 1, self.controller.navigable_index + 1
            )
        item = self.controller.navigable_items[self.controller.navigable_index]
        if item['type'] == 'rule':
            self.show_rule_info(item['data'], item['category_name'])
        else:
            self.select_category(item['name'])

    def select_category(self, category_name):
        for i, item in enumerate(self.controller.navigable_items):
            if item['type'] == 'category' and item['name'] == category_name:
                self.controller.selected_item = item
                self.controller.navigable_index = i
                break
        if self.selected_rule_frame:
            self.selected_rule_frame.configure(fg_color="transparent")
        if self.selected_category_frame:
            self.selected_category_frame.configure(fg_color="transparent")
        if category_name in self.rule_widgets:
            self.selected_category_frame = self.rule_widgets[category_name]['category_frame']
            self.selected_category_frame.configure(fg_color="lightblue")
        for widget in self.info_frame.winfo_children():
            if widget != self.info_label: widget.destroy()
        self.info_label.configure(text="Rule Info")

    def show_rule_info(self, rule, category_name=None):
        for i, item in enumerate(self.controller.navigable_items):
            if item['type'] == 'rule' and item['data'] == rule:
                self.controller.selected_item = item
                self.controller.navigable_index = i
                break
        if self.selected_rule_frame:
            self.selected_rule_frame.configure(fg_color="transparent")
        if self.selected_category_frame:
            self.selected_category_frame.configure(fg_color="transparent")
        
        rule_code = rule['code']
        cat_name = category_name or self.controller.selected_item.get('category_name')
        if cat_name in self.rule_widgets and rule_code in self.rule_widgets[cat_name]['rules']:
            self.selected_rule_frame = self.rule_widgets[cat_name]['rules'][rule_code]['frame']
            self.selected_rule_frame.configure(fg_color="lightblue")

        for widget in self.info_frame.winfo_children():
            if widget != self.info_label: widget.destroy()
        self.info_label.configure(text=f"Rule: {rule['code']}")
        ctk.CTkLabel(self.info_frame, text=f"Name: {rule['name']}", wraplength=250).pack(pady=5, anchor="w")
        ctk.CTkLabel(self.info_frame, text=f"Summary: {rule['summary']}", wraplength=250, justify="left").pack(pady=5, anchor="w")
        self._init_doc_viewer(rule)

    def _init_doc_viewer(self, rule):
        if rule.get("documentation"):
            txt = ctk.CTkTextbox(self.info_frame, wrap="word", height=400)
            txt.pack(pady=(10, 5), fill="both", expand=True)
            txt.insert("1.0", rule["documentation"])
            txt.configure(state="disabled")
        elif not self.controller.is_pylint_rule(rule['code']):
            self.scrape_button = ctk.CTkButton(
                self.info_frame, text="Fetch Documentation Online",
                command=lambda: self.fetch_rule_docs(rule)
            )
            self.scrape_button.pack(pady=10)

    def fetch_rule_docs(self, rule):
        self.scrape_button.configure(state="disabled", text="Fetching...")
        self.status_label.configure(text="Scraping documentation...")
        self.controller.run_in_thread(self._fetch_docs_worker, "fetch_docs", rule)

    def _fetch_docs_worker(self, command, rule):
        try:
            docs = ruff_adapter.scrape_rule_documentation(rule['code'])
            self.controller.queue.put((command, (rule, docs)))
        except Exception as e:
            self.controller.queue.put(("error", str(e)))


if __name__ == "__main__":
    import sys
    app = App()
    if len(sys.argv) > 1:
        # In a real app, you might add a --headless flag
        if sys.argv[1] != '--headless':
            app.select_directory(sys.argv[1])
    app.mainloop()
