import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import tomlkit
import threading
import queue
import copy
from unittest.mock import MagicMock
from . import ruff_adapter, config_manager, workspace_analyzer, profile_manager, ci_integration, pylint_adapter

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

class ProfileComparisonWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Compare Profiles")
        self.geometry("600x400")

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Top Frame for selections ---
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        self.profiles = profile_manager.get_built_in_profiles()

        self.profile1_var = ctk.StringVar(value=self.profiles[0] if self.profiles else "")
        self.profile2_var = ctk.StringVar(value=self.profiles[1] if len(self.profiles) > 1 else "")

        self.profile1_menu = ctk.CTkOptionMenu(top_frame, variable=self.profile1_var, values=self.profiles)
        self.profile1_menu.pack(side="left", padx=5)

        ctk.CTkLabel(top_frame, text="vs.").pack(side="left", padx=5)

        self.profile2_menu = ctk.CTkOptionMenu(top_frame, variable=self.profile2_var, values=self.profiles)
        self.profile2_menu.pack(side="left", padx=5)

        self.compare_button = ctk.CTkButton(top_frame, text="Compare", command=self.do_comparison)
        self.compare_button.pack(side="left", padx=10)

        # --- Results Textbox ---
        self.results_textbox = ctk.CTkTextbox(self, wrap="word")
        self.results_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.results_textbox.insert("1.0", "Select two profiles and click 'Compare' to see the differences.")
        self.results_textbox.configure(state="disabled")

    def do_comparison(self):
        p1 = self.profile1_var.get()
        p2 = self.profile2_var.get()

        if not p1 or not p2 or p1 == p2:
            self.results_textbox.configure(state="normal")
            self.results_textbox.delete("1.0", "end")
            self.results_textbox.insert("1.0", "Please select two different profiles to compare.")
            self.results_textbox.configure(state="disabled")
            return

        diff = profile_manager.compare_profiles(p1, p2)

        report = f"Comparing '{p1}' vs '{p2}':\n\n"
        report += "--- RULES SELECTED --- \n"
        if diff["select_only_in_1"]:
            report += f"\nOnly in '{p1}':\n" + "\n".join(f"  - {r}" for r in diff["select_only_in_1"]) + "\n"
        if diff["select_only_in_2"]:
            report += f"\nOnly in '{p2}':\n" + "\n".join(f"  - {r}" for r in diff["select_only_in_2"]) + "\n"

        report += "\n--- RULES IGNORED ---\n"
        if diff["ignore_only_in_1"]:
            report += f"\nOnly in '{p1}':\n" + "\n".join(f"  - {r}" for r in diff["ignore_only_in_1"]) + "\n"
        if diff["ignore_only_in_2"]:
            report += f"\nOnly in '{p2}':\n" + "\n".join(f"  - {r}" for r in diff["ignore_only_in_2"]) + "\n"

        report += f"\n--- COMMON RULES ---\n"
        if diff["common_select"]:
            report += "\nCommonly Selected:\n" + "\n".join(f"  - {r}" for r in diff["common_select"]) + "\n"
        if diff["common_ignore"]:
            report += "\nCommonly Ignored:\n" + "\n".join(f"  - {r}" for r in diff["common_ignore"]) + "\n"

        self.results_textbox.configure(state="normal")
        self.results_textbox.delete("1.0", "end")
        self.results_textbox.insert("1.0", report)
        self.results_textbox.configure(state="disabled")


class App(ctk.CTk):
    def __init__(self, headless=False):
        if not headless:
            super().__init__()
            self.title("Ruff Studio")
            self.geometry("1280x800")
            self._init_ui()
        else:
            self.tk = MagicMock()

        self.current_directory = None
        self.pyproject_path = None
        self.pyproject_data = None
        self.enabled_rules = set()
        self.all_rules = []
        self.rule_widgets = {}
        self.staged_changes = {}
        self.base_scan_results = []
        self.selected_rule_frame = None
        self.selected_category_frame = None
        self.selected_item = None
        self.navigable_items = []

        self.analyzer = workspace_analyzer.WorkspaceAnalyzer("ruff_studio.db")
        self.queue = queue.Queue()

        if not headless:
            self.run_in_thread(self._discover_rules_worker, "discover_rules")
            self.process_queue()

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
            self.action_frame, text="Compare Profiles", command=self.open_comparison_window
        )
        self.compare_profiles_button.pack(side="left", padx=5)

        self.generate_pre_commit_button = ctk.CTkButton(
            self.action_frame, text="Generate Pre-commit Config", command=self.generate_pre_commit_config_file,
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
        self.rules_header_frame = ctk.CTkFrame(self.rules_panel_container, height=30, fg_color="transparent")
        self.rules_header_frame.grid(row=0, column=0, sticky="ew", padx=5)
        self.rules_header_frame.grid_columnconfigure(3, weight=1) # Make the label column expand

        # Spacer for toggle button column
        ctk.CTkLabel(self.rules_header_frame, text="", width=20).grid(row=0, column=0, padx=5)
        # "Enabled" label for checkbox column
        ctk.CTkLabel(self.rules_header_frame, text="Enabled", anchor="w").grid(row=0, column=1, padx=(0,5))

        # Configure grid for radio button labels
        radio_header_frame = ctk.CTkFrame(self.rules_header_frame, fg_color="transparent")
        radio_header_frame.grid(row=0, column=2)
        radio_header_frame.grid_columnconfigure(0, minsize=20)
        radio_header_frame.grid_columnconfigure(1, minsize=20)
        radio_header_frame.grid_columnconfigure(2, minsize=20)

        ctk.CTkLabel(radio_header_frame, text="Select", anchor="center").grid(row=0, column=0)
        ctk.CTkLabel(radio_header_frame, text="Ignore", anchor="center").grid(row=0, column=1)
        ctk.CTkLabel(radio_header_frame, text="Default", anchor="center").grid(row=0, column=2)


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

        total_weight = weight0 + weight2 + weight4

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
        thread = threading.Thread(target=worker, args=(command_name, *args))
        thread.daemon = True
        thread.start()

    def _discover_rules_worker(self, command_name):
        try:
            ruff_rules = ruff_adapter.discover_rules()
            pylint_rules = pylint_adapter.discover_rules()

            # Combine rules, prefixing pylint categories to avoid name clashes
            combined_rules = ruff_rules
            for category, data in pylint_rules.items():
                combined_rules[f"Pylint: {category}"] = data

            self.queue.put((command_name, combined_rules))
        except (RuntimeError, FileNotFoundError) as e:
            self.queue.put(("error", e))


    def _run_full_scan_worker(self, command_name, directory):
        try:
            results = self.analyzer.run_full_scan(directory)
            self.queue.put((command_name, results))
        except (RuntimeError, FileNotFoundError) as e:
            self.queue.put(("error", e))

    def process_queue(self):
        try:
            command, data = self.queue.get_nowait()

            if command == "error":
                if isinstance(data, FileNotFoundError):
                    messagebox.showerror("Error", "Ruff executable not found...")
                else:
                    error_message = f"An unexpected error occurred:\n\n{data}"
                    messagebox.showerror("Error", error_message)
            elif command == "discover_rules":
                self.all_rules = data
                self.rules_label.configure(text="Rules")
                self.populate_rules_initial()
                if not isinstance(self.all_rules, dict):
                    return
                self.managed_prefixes = {
                    cat['prefix'] for cat in self.all_rules.values()
                }
                self.managed_rules = {
                    rule['code']
                    for cat in self.all_rules.values()
                    for rule in cat['rules']
                }
            elif command == "run_full_scan":
                self.base_scan_results = data
                self.update_results_panel(data)
            elif command == "run_simulation":
                self.update_simulation_results_panel(data)

            self.select_button.configure(state="normal")
            self.status_label.configure(text="")

        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    def select_directory(self, directory=None):
        if not directory:
            directory = filedialog.askdirectory()

        if directory:
            self.current_directory = directory
            self.directory_label.configure(text=directory)
            self.pyproject_path = os.path.join(directory, "pyproject.toml")
            self.staged_changes = {}
            self.simulate_button.configure(state="disabled")
            self.apply_button.configure(state="disabled")

            if os.path.exists(self.pyproject_path):
                self.pyproject_data = config_manager.read_pyproject(self.pyproject_path)
                ruff_config = config_manager.get_ruff_config(self.pyproject_data)
                pylint_config = config_manager.get_pylint_config(self.pyproject_data)

                ruff_enabled = self._get_ruff_rules_from_config(ruff_config)
                pylint_enabled = self._get_pylint_rules_from_config(pylint_config)
                self.enabled_rules = ruff_enabled.union(pylint_enabled)
            else:
                self.pyproject_data = tomlkit.document()
                # Get default ruff rules, assume all pylint rules are enabled by default
                ruff_enabled = ruff_adapter.get_default_rules()
                pylint_enabled = self._get_pylint_rules_from_config({})
                self.enabled_rules = ruff_enabled.union(pylint_enabled)

            for widget in self.results_frame.winfo_children():
                if widget != self.results_label:
                    widget.destroy()
            self.results_label.configure(text="Scanning...")

            self.run_in_thread(self._run_full_scan_worker, "run_full_scan", directory)
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
            result_text = (
                f"{result.file_path}:{result.line_number}:"
                f"{result.column} {result.rule_id} {result.message}"
            )
            ctk.CTkLabel(
                self.results_frame, text=result_text,
                wraplength=self.results_frame.winfo_width()-50, justify="left"
            ).pack(pady=2, anchor="w")

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
        categories = self.all_rules.items()

        # Create a list of navigable items (categories and rules) in display order
        self.navigable_items = []
        for category_name, category_data in categories:
            category_item = {'type': 'category', 'name': category_name, 'data': category_data}
            self.navigable_items.append(category_item)
            sorted_rules = sorted(category_data['rules'], key=lambda r: r['code'])
            for rule in sorted_rules:
                rule_item = {'type': 'rule', 'data': rule, 'category_name': category_name}
                self.navigable_items.append(rule_item)


        for category_name, category_data in categories:
            # --- Category Header ---
            category_frame = ctk.CTkFrame(self.rules_frame)
            category_frame.pack(fill="x", pady=(5, 1), padx=5)
            category_frame.grid_columnconfigure(3, weight=1) # Label column

            # Allow the category header itself to be selected
            category_frame.bind("<Button-1>", lambda event, cn=category_name: self.select_category(cn))

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
            radio_frame.grid_columnconfigure(0, minsize=20)
            radio_frame.grid_columnconfigure(1, minsize=20)
            radio_frame.grid_columnconfigure(2, minsize=20)

            radio_var = ctk.StringVar(value="default")
            select_rb = ctk.CTkRadioButton(radio_frame, text="", variable=radio_var, value="select", command=lambda p=category_data['prefix']: self.stage_category_change(p, "select"))
            ignore_rb = ctk.CTkRadioButton(radio_frame, text="", variable=radio_var, value="ignore", command=lambda p=category_data['prefix']: self.stage_category_change(p, "ignore"))
            default_rb = ctk.CTkRadioButton(radio_frame, text="", variable=radio_var, value="default", command=lambda p=category_data['prefix']: self.stage_category_change(p, "default"))

            select_rb.grid(row=0, column=0)
            ignore_rb.grid(row=0, column=1)
            default_rb.grid(row=0, column=2)

            category_label = ctk.CTkLabel(category_frame, text=f"{category_name} ({category_data['prefix']})", anchor="w")
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
                frame.grid_columnconfigure(3, weight=1) # Label column

                # Spacer to align with category toggle button
                ctk.CTkLabel(frame, text="", width=20).grid(row=0, column=0, padx=5)

                # Effective state indicator for the rule
                rule_effective_state_var = ctk.StringVar()
                rule_effective_indicator = ctk.CTkCheckBox(
                    frame, text="", variable=rule_effective_state_var,
                    onvalue="on", offvalue="off", state="disabled"
                )
                rule_effective_indicator.grid(row=0, column=1, padx=(0,5))

                rule_text = f"{rule['code']}"
                if rule['status'] != 'stable':
                    rule_text += f" (⚠️ {rule['status']})"

                # Radio buttons for the rule
                rule_radio_frame = ctk.CTkFrame(frame, fg_color="transparent")
                rule_radio_frame.grid(row=0, column=2)
                rule_radio_frame.grid_columnconfigure(0, minsize=20)
                rule_radio_frame.grid_columnconfigure(1, minsize=20)
                rule_radio_frame.grid_columnconfigure(2, minsize=20)

                rule_radio_var = ctk.StringVar(value="default")
                rule_select_rb = ctk.CTkRadioButton(rule_radio_frame, text="", variable=rule_radio_var, value="select", command=lambda rc=rule['code']: self.stage_rule_change(rc, "select"))
                rule_ignore_rb = ctk.CTkRadioButton(rule_radio_frame, text="", variable=rule_radio_var, value="ignore", command=lambda rc=rule['code']: self.stage_rule_change(rc, "ignore"))
                rule_default_rb = ctk.CTkRadioButton(rule_radio_frame, text="", variable=rule_radio_var, value="default", command=lambda rc=rule['code']: self.stage_rule_change(rc, "default"))

                rule_select_rb.grid(row=0, column=0)
                rule_ignore_rb.grid(row=0, column=1)
                rule_default_rb.grid(row=0, column=2)

                label = ctk.CTkLabel(frame, text=f"{rule_text}: {rule['name']}", anchor="w")
                label.grid(row=0, column=3, sticky="w", padx=10)

                if rule['status'] != 'stable':
                    Tooltip(label, f"This rule is {rule['status']}.")

                label.bind("<Button-1>", lambda event, r=rule, cn=category_name: self.show_rule_info(r, cn))

                rule_widget_data = {
                    'effective_state_indicator': rule_effective_indicator,
                    'effective_state_variable': rule_effective_state_var,
                    'radio_variable': rule_radio_var,
                    'rule_info': rule,
                    'frame': frame
                }
                self.rule_widgets[category_name]['rules'][rule['code']] = rule_widget_data

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
            if state == "select": return True
            if state == "ignore": return False

        if category_prefix in self.staged_changes:
            state = self.staged_changes[category_prefix]
            if state == "select": return True
            if state == "ignore": return False

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
        Determines if a rule or category is explicitly selected, ignored, or default for a given linter.
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
        if not self.current_directory:
            # Disable all widgets if no directory is selected
            for category_widgets in self.rule_widgets.values():
                for rb in category_widgets['radio_variable'].values():
                    rb.configure(state="disabled")
                for rule_widget in category_widgets['rules'].values():
                    for rb in rule_widget['radio_variable'].values():
                        rb.configure(state="disabled")
            return

        ruff_config = config_manager.get_ruff_config(self.pyproject_data)
        pylint_config = config_manager.get_pylint_config(self.pyproject_data)

        for category_name, category_widgets in self.rule_widgets.items():
            prefix = category_widgets['prefix']
            is_pylint = category_name.startswith("Pylint:")

            # Update category radio buttons
            cat_state = self.staged_changes.get(prefix, self._get_explicit_rule_state(prefix, ruff_config, pylint_config))
            category_widgets['radio_variable'].set(cat_state)

            any_rule_on = False
            all_rules_on = True

            for rule_code, rule_widget in category_widgets['rules'].items():
                # Update rule radio buttons
                rule_state = self.staged_changes.get(rule_code, self._get_explicit_rule_state(rule_code, ruff_config, pylint_config))
                rule_widget['radio_variable'].set(rule_state)

                # Update effective state indicator
                is_on = self._get_effective_rule_state(rule_code, prefix)
                rule_widget['effective_state_variable'].set("on" if is_on else "off")

                if is_on:
                    any_rule_on = True
                else:
                    all_rules_on = False

            # Update category effective state indicator
            if all_rules_on:
                category_widgets['effective_state_variable'].set("on")
            elif any_rule_on:
                category_widgets['effective_state_variable'].set("on") # Indeterminate state could be better
            else:
                category_widgets['effective_state_variable'].set("off")

    def stage_rule_change(self, rule_code, state):
        self.staged_changes[rule_code] = state
        self.simulate_button.configure(state="normal")
        self.apply_button.configure(state="normal")
        self.update_rules_panel()

    def stage_category_change(self, prefix, state):
        self.staged_changes[prefix] = state
        self.simulate_button.configure(state="normal")
        self.apply_button.configure(state="normal")
        # Update all rules under this category to reflect the change
        for category_name, category_data in self.rule_widgets.items():
            if category_data['prefix'] == prefix:
                for rule_code in category_data['rules'].keys():
                    if rule_code in self.staged_changes:
                        del self.staged_changes[rule_code]
                break
        self.update_rules_panel()

    def toggle_category_rules(self, category_name):
        container = self.rule_widgets[category_name]['rules_container']
        toggle_button = self.rule_widgets[category_name]['toggle_button']
        category_frame = self.rule_widgets[category_name]['category_frame']
        if container.winfo_viewable():
            container.pack_forget()
            toggle_button.configure(text="►")
        else:
            container.pack(fill="x", padx=(25, 5), after=category_frame)
            toggle_button.configure(text="▼")


    def simulate_changes(self):
        if not self.pyproject_data:
            return
        sim_config_data = self.get_effective_config()
        self.results_label.configure(text="Simulating...")
        self.run_in_thread(
            ruff_adapter.run_scan_with_config, "run_simulation",
            self.current_directory, sim_config_data
        )

    def apply_profile(self, profile_name):
        if profile_name == "Apply a Profile...":
            return

        try:
            profile_data = profile_manager.load_profile(profile_name)

            # We don't need to apply to a config copy, as we'll just read the rules
            # and then stage changes through the existing UI logic.
            profile_ruff_config = profile_data.get("profile", {}).get("rules", {}).get("ruff", {})

            # Reset staged changes
            self.staged_changes = {}

            # --- Ruff Profile Application ---
            profile_ruff_config = profile_data.get("profile", {}).get("rules", {}).get("ruff", {})
            if profile_ruff_config:
                dummy_ruff_config = {"select": profile_ruff_config.get("select", []), "ignore": profile_ruff_config.get("ignore", [])}
                profile_ruff_rules = self._get_ruff_rules_from_config(dummy_ruff_config)
                for category_name, category_widgets in self.rule_widgets.items():
                    if category_name.startswith("Pylint:"):
                        continue  # Skip pylint categories for ruff logic
                    for rule_code in category_widgets['rules'].keys():
                        if rule_code in profile_ruff_rules:
                            self.staged_changes[rule_code] = "select"
                        else:
                            self.staged_changes[rule_code] = "ignore"

            # --- Pylint Profile Application ---
            profile_pylint_config = profile_data.get("profile", {}).get("rules", {}).get("pylint", {})
            if profile_pylint_config:
                # Pylint is default-on, so we only need to stage disabled rules
                pylint_disabled_rules = profile_pylint_config.get("disable", [])
                for category_name, category_widgets in self.rule_widgets.items():
                    if not category_name.startswith("Pylint:"):
                        continue
                    for rule_code in category_widgets['rules'].keys():
                        if rule_code in pylint_disabled_rules:
                            self.staged_changes[rule_code] = "ignore"
                        else:
                            # If not explicitly disabled, it should be on (default)
                            self.staged_changes[rule_code] = "default"

            # Ensure the UI reflects the newly staged changes
            self.update_rules_panel()
            self.simulate_button.configure(state="normal")
            self.apply_button.configure(state="normal")

            messagebox.showinfo(
                "Profile Applied",
                f"The '{profile_name}' profile has been staged. "
                "Review the changes and click 'Simulate' or 'Apply'."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply profile: {e}")
        finally:
            self.profile_menu.set("Apply a Profile...")


    def apply_changes(self):
        if not self.pyproject_data or not self.pyproject_path:
            return

        ruff_config, pylint_config = self.get_effective_configs()

        config_manager.update_ruff_config(self.pyproject_data, ruff_config)
        config_manager.update_pylint_config(self.pyproject_data, pylint_config)

        config_manager.write_pyproject(self.pyproject_path, self.pyproject_data)

        self.staged_changes = {}
        self.simulate_button.configure(state="disabled")
        self.apply_button.configure(state="disabled")

        self.update_rules_panel()
        self.run_in_thread(self._run_full_scan_worker, "run_full_scan", self.current_directory)

    def open_comparison_window(self):
        ProfileComparisonWindow(self)

    def generate_pre_commit_config_file(self):
        """Generates and saves a .pre-commit-config.yaml file."""
        try:
            ruff_version = ruff_adapter.get_ruff_version()
            config_content = ci_integration.generate_pre_commit_config(ruff_version)

            filepath = filedialog.asksaveasfilename(
                initialdir=self.current_directory,
                initialfile=".pre-commit-config.yaml",
                defaultextension=".yaml",
                filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
            )

            if filepath:
                with open(filepath, "w") as f:
                    f.write(config_content)
                messagebox.showinfo("Success", f"Successfully saved {filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate pre-commit config: {e}")

    def get_effective_configs(self):
        """
        Calculates the effective ruff and pylint configurations based on staged changes.
        Returns a tuple of (ruff_config, pylint_config).
        """
        # --- Ruff ---
        ruff_config = config_manager.get_ruff_config(self.pyproject_data).copy()
        ruff_select = set(ruff_config.get("select", []))
        ruff_ignore = set(ruff_config.get("ignore", []))

        # --- Pylint ---
        pylint_config = config_manager.get_pylint_config(self.pyproject_data).copy()
        pylint_enable = set(pylint_config.get("enable", []))
        pylint_disable = set(pylint_config.get("disable", []))

        for code, state in self.staged_changes.items():
            if self.is_pylint_rule(code):
                if state == "select":
                    pylint_enable.add(code)
                    pylint_disable.discard(code)
                elif state == "ignore":
                    pylint_disable.add(code)
                    pylint_enable.discard(code)
                elif state == "default":
                    pylint_enable.discard(code)
                    pylint_disable.discard(code)
            else:  # Assume ruff
                if state == "select":
                    ruff_select.add(code)
                    ruff_ignore.discard(code)
                elif state == "ignore":
                    ruff_ignore.add(code)
                elif state == "default":
                    ruff_select.discard(code)
                    ruff_ignore.discard(code)

        ruff_config["select"] = sorted(list(ruff_select))
        ruff_config["ignore"] = sorted(list(ruff_ignore))

        # Only add lists if they are not empty
        if pylint_enable:
            pylint_config["enable"] = sorted(list(pylint_enable))
        elif "enable" in pylint_config:
            del pylint_config["enable"]

        if pylint_disable:
            pylint_config["disable"] = sorted(list(pylint_disable))
        elif "disable" in pylint_config:
            del pylint_config["disable"]

        return ruff_config, pylint_config

    def navigate_items(self, event):
        if not self.selected_item or not self.navigable_items:
            return

        try:
            current_index = self.navigable_items.index(self.selected_item)
        except ValueError:
            return # Should not happen if selection is managed properly

        if event.keysym == "Up":
            next_index = max(0, current_index - 1)
        elif event.keysym == "Down":
            next_index = min(len(self.navigable_items) - 1, current_index + 1)
        else:
            return

        if next_index != current_index:
            next_item = self.navigable_items[next_index]
            if next_item['type'] == 'rule':
                self.show_rule_info(next_item['data'], next_item['category_name'])
            elif next_item['type'] == 'category':
                self.select_category(next_item['name'])

    def select_category(self, category_name):
        # Find the full item from the navigable list
        selected_nav_item = None
        for item in self.navigable_items:
            if item['type'] == 'category' and item['name'] == category_name:
                selected_nav_item = item
                break
        self.selected_item = selected_nav_item

        # Reset any previously selected frames
        if self.selected_rule_frame:
            self.selected_rule_frame.configure(fg_color="transparent")
        if self.selected_category_frame:
            self.selected_category_frame.configure(fg_color="transparent")

        # Highlight the new selected category
        if category_name in self.rule_widgets:
            self.selected_category_frame = self.rule_widgets[category_name]['category_frame']
            self.selected_category_frame.configure(fg_color="lightblue")

        # Clear the info panel
        for widget in self.info_frame.winfo_children():
            if widget != self.info_label:
                widget.destroy()
        self.info_label.configure(text="Rule Info")


    def show_rule_info(self, rule, category_name=None):
        # Find the full item from the navigable list
        selected_nav_item = None
        for item in self.navigable_items:
            if item['type'] == 'rule' and item['data'] == rule:
                selected_nav_item = item
                break
        self.selected_item = selected_nav_item

        # Reset any previously selected frames
        if self.selected_rule_frame:
            self.selected_rule_frame.configure(fg_color="transparent")
        if self.selected_category_frame:
            self.selected_category_frame.configure(fg_color="transparent")

        # Highlight the new selected rule
        rule_code = rule['code']
        category_name_for_widget = category_name or selected_nav_item.get('category_name')


        if (category_name_for_widget in self.rule_widgets and
                rule_code in self.rule_widgets[category_name_for_widget]['rules']):
            self.selected_rule_frame = (
                self.rule_widgets[category_name_for_widget]['rules'][rule_code]['frame']
            )
            self.selected_rule_frame.configure(fg_color="lightblue")

        for widget in self.info_frame.winfo_children():
            if widget != self.info_label:
                widget.destroy()

        ctk.CTkLabel(
            self.info_frame, text=f"Code: {rule['code']}", wraplength=250
        ).pack(pady=5, anchor="w")
        ctk.CTkLabel(
            self.info_frame, text=f"Name: {rule['name']}", wraplength=250
        ).pack(pady=5, anchor="w")
        ctk.CTkLabel(
            self.info_frame, text=f"Fixable: {'Yes' if rule['fix'] else 'No'}",
            wraplength=250
        ).pack(pady=5, anchor="w")
        ctk.CTkLabel(
            self.info_frame, text=f"Summary: {rule['summary']}",
            wraplength=250, justify="left"
        ).pack(pady=5, anchor="w")

        if rule.get("documentation") is None and not self.is_pylint_rule(rule['code']):
            # If documentation is missing, and it's a ruff rule, scrape it now.
            self.status_label.configure(text=f"Fetching docs for {rule['code']}...")
            self.update_idletasks()
            # This runs in the main thread, which can cause a brief UI freeze.
            # For a better user experience, this could be moved to a background thread.
            rule['documentation'] = ruff_adapter.scrape_rule_documentation(rule['name'])
            self.status_label.configure(text="")
            # No need to update the cache here, as the rule object is updated in-memory
            # and will be re-cached the next time the app starts if rules are re-discovered.

        if rule.get("documentation"):
            # Use a Textbox for better scrolling and text selection
            doc_textbox = ctk.CTkTextbox(self.info_frame, wrap="word", height=400)
            doc_textbox.pack(pady=(10, 5), fill="both", expand=True)
            doc_textbox.insert("1.0", rule["documentation"])
            doc_textbox.configure(state="disabled")


if __name__ == "__main__":
    import sys
    app = App()
    if len(sys.argv) > 1:
        # In a real app, you might add a --headless flag
        if sys.argv[1] != '--headless':
            app.select_directory(sys.argv[1])
    app.mainloop()
