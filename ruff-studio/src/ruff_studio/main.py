import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import tomlkit
import threading
import queue
import copy
from unittest.mock import MagicMock
from . import ruff_adapter, config_manager, workspace_analyzer

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

        self.current_directory = None
        self.pyproject_path = None
        self.pyproject_data = None
        self.enabled_rules = set()
        self.all_rules = []
        self.rule_widgets = {}
        self.staged_changes = {}
        self.base_scan_results = []
        self.selected_rule_frame = None
        self.selected_rule_info = None
        self.sorted_rules = []

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

        self.status_label = ctk.CTkLabel(self.top_frame, text="")
        self.status_label.pack(side="right", padx=10)

        # --- Panels ---
        self.rules_frame = ctk.CTkScrollableFrame(self)
        self.rules_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=0)
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

        self.bind("<Up>", self.navigate_rules)
        self.bind("<Down>", self.navigate_rules)

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
            rules = ruff_adapter.discover_rules()
            self.queue.put((command_name, rules))
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
                ruff_config = self.pyproject_data.get("tool", {}).get("ruff", {}).get("lint", {})
                self.enabled_rules = self._get_rules_from_config(ruff_config)
            else:
                self.pyproject_data = tomlkit.document()
                self.enabled_rules = ruff_adapter.get_default_rules()

            for widget in self.results_frame.winfo_children():
                if widget != self.results_label:
                    widget.destroy()
            self.results_label.configure(text="Scanning...")

            self.run_in_thread(self._run_full_scan_worker, "run_full_scan", directory)
            self.update_rules_panel()

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
        sorted_categories = sorted(self.all_rules.items())

        # Create a flat, sorted list of all rules for navigation
        all_rules_flat = []
        for _, category_data in sorted_categories:
            all_rules_flat.extend(category_data['rules'])
        self.sorted_rules = sorted(all_rules_flat, key=lambda r: r['code'])

        for category_name, category_data in sorted_categories:
            # --- Category Header ---
            category_frame = ctk.CTkFrame(self.rules_frame)
            category_frame.pack(fill="x", pady=(5, 1), padx=5)

            effective_state_var = ctk.StringVar()
            toggle_button = ctk.CTkButton(
                category_frame, text="▼", width=20,
                command=lambda cn=category_name: self.toggle_category_rules(cn)
            )
            toggle_button.pack(side="left", padx=5)

            effective_state_indicator = ctk.CTkCheckBox(category_frame, text="", variable=effective_state_var, onvalue="on", offvalue="off", state="disabled")
            effective_state_indicator.pack(side="left", padx=(0, 5))


            category_label = ctk.CTkLabel(category_frame, text=f"{category_name} ({category_data['prefix']})", anchor="w")
            category_label.pack(side="left", fill="x", expand=True)

            # Radio buttons for category
            radio_frame = ctk.CTkFrame(category_frame, fg_color="transparent")
            radio_frame.pack(side="right", padx=10)
            radio_var = ctk.StringVar(value="default")

            select_rb = ctk.CTkRadioButton(radio_frame, text="Select", variable=radio_var, value="select", command=lambda p=category_data['prefix']: self.stage_category_change(p, "select"))
            ignore_rb = ctk.CTkRadioButton(radio_frame, text="Ignore", variable=radio_var, value="ignore", command=lambda p=category_data['prefix']: self.stage_category_change(p, "ignore"))
            default_rb = ctk.CTkRadioButton(radio_frame, text="Default", variable=radio_var, value="default", command=lambda p=category_data['prefix']: self.stage_category_change(p, "default"))

            select_rb.pack(side="left", padx=5)
            ignore_rb.pack(side="left", padx=5)
            default_rb.pack(side="left", padx=5)

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

                # Effective state indicator for the rule
                rule_effective_state_var = ctk.StringVar()
                rule_effective_indicator = ctk.CTkCheckBox(frame, text="", variable=rule_effective_state_var, onvalue="on", offvalue="off", state="disabled")
                rule_effective_indicator.pack(side="left", padx=(0,5))

                rule_text = f"{rule['code']}"
                if rule['status'] != 'stable':
                    rule_text += f" (⚠️ {rule['status']})"


                label = ctk.CTkLabel(frame, text=f"{rule_text}: {rule['name']}", anchor="w")
                label.pack(side="left", fill="x", expand=True, padx=5)

                # Radio buttons for the rule
                rule_radio_frame = ctk.CTkFrame(frame, fg_color="transparent")
                rule_radio_frame.pack(side="left", padx=10)
                rule_radio_var = ctk.StringVar(value="default")

                rule_select_rb = ctk.CTkRadioButton(rule_radio_frame, text="Select", variable=rule_radio_var, value="select", command=lambda rc=rule['code']: self.stage_rule_change(rc, "select"))
                rule_ignore_rb = ctk.CTkRadioButton(rule_radio_frame, text="Ignore", variable=rule_radio_var, value="ignore", command=lambda rc=rule['code']: self.stage_rule_change(rc, "ignore"))
                rule_default_rb = ctk.CTkRadioButton(rule_radio_frame, text="Default", variable=rule_radio_var, value="default", command=lambda rc=rule['code']: self.stage_rule_change(rc, "default"))

                rule_select_rb.pack(side="left", padx=5)
                rule_ignore_rb.pack(side="left", padx=5)
                rule_default_rb.pack(side="left", padx=5)

                if rule['status'] != 'stable':
                    Tooltip(label, f"This rule is {rule['status']}.")

                label.bind("<Button-1>", lambda event, r=rule: self.show_rule_info(r))

                rule_widget_data = {
                    'effective_state_indicator': rule_effective_indicator,
                    'effective_state_variable': rule_effective_state_var,
                    'radio_variable': rule_radio_var,
                    'rule_info': rule,
                    'frame': frame
                }
                self.rule_widgets[category_name]['rules'][rule['code']] = rule_widget_data

    def _get_rules_from_config(self, ruff_config):
        """
        Get the set of enabled rule codes from a ruff config dict.
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

    def _get_explicit_rule_state(self, code, ruff_config):
        """
        Determines if a rule or category is explicitly selected, ignored, or default.
        """
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

        ruff_config = self.pyproject_data.get("tool", {}).get("ruff", {}).get("lint", {})

        for category_name, category_widgets in self.rule_widgets.items():
            prefix = category_widgets['prefix']

            # Update category radio buttons
            cat_state = self.staged_changes.get(prefix, self._get_explicit_rule_state(prefix, ruff_config))
            category_widgets['radio_variable'].set(cat_state)

            any_rule_on = False
            all_rules_on = True

            for rule_code, rule_widget in category_widgets['rules'].items():
                # Update rule radio buttons
                rule_state = self.staged_changes.get(rule_code, self._get_explicit_rule_state(rule_code, ruff_config))
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

    def apply_changes(self):
        if not self.pyproject_data or not self.pyproject_path:
            return

        effective_config = self.get_effective_config()
        (
            self.pyproject_data.setdefault("tool", {})
            .setdefault("ruff", {})["lint"]
        ) = effective_config

        config_manager.write_pyproject(self.pyproject_path, self.pyproject_data)

        self.staged_changes = {}
        self.simulate_button.configure(state="disabled")
        self.apply_button.configure(state="disabled")

        self.update_rules_panel()
        self.run_in_thread(self._run_full_scan_worker, "run_full_scan", self.current_directory)

    def get_effective_config(self):
        effective_data = copy.deepcopy(self.pyproject_data)
        ruff_config = (
            effective_data.setdefault("tool", {})
            .setdefault("ruff", {})
            .setdefault("lint", {})
        )

        final_select = set()
        final_ignore = set()

        # Process staged changes
        for code, state in self.staged_changes.items():
            if state == "select":
                final_select.add(code)
            elif state == "ignore":
                final_ignore.add(code)

        # Preserve unmanaged rules from the original config
        original_select = set(ruff_config.get("select", []))
        original_ignore = set(ruff_config.get("ignore", []))

        final_select.update(s for s in original_select if s not in self.managed_prefixes and s not in self.managed_rules)
        final_ignore.update(i for i in original_ignore if i not in self.managed_prefixes and i not in self.managed_rules)

        ruff_config["select"] = sorted(list(final_select))
        ruff_config["ignore"] = sorted(list(final_ignore))
        return ruff_config

    def navigate_rules(self, event):
        if not self.selected_rule_info or not self.sorted_rules:
            return

        try:
            current_index = self.sorted_rules.index(self.selected_rule_info)
        except ValueError:
            return # Current selection not in the navigable list

        if event.keysym == "Up":
            next_index = max(0, current_index - 1)
        elif event.keysym == "Down":
            next_index = min(len(self.sorted_rules) - 1, current_index + 1)
        else:
            return

        if next_index != current_index:
            next_rule = self.sorted_rules[next_index]
            self.show_rule_info(next_rule)

    def show_rule_info(self, rule):
        self.selected_rule_info = rule
        # Reset the previously selected rule's background color
        if self.selected_rule_frame:
            self.selected_rule_frame.configure(fg_color="transparent")

        # Highlight the new selected rule
        rule_code = rule['code']
        category_name = rule.get("linter", "Unknown")

        if (category_name in self.rule_widgets and
                rule_code in self.rule_widgets[category_name]['rules']):
            self.selected_rule_frame = (
                self.rule_widgets[category_name]['rules'][rule_code]['frame']
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


if __name__ == "__main__":
    import sys
    app = App()
    if len(sys.argv) > 1:
        # In a real app, you might add a --headless flag
        if sys.argv[1] != '--headless':
            app.select_directory(sys.argv[1])
    app.mainloop()
