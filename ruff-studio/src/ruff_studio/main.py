import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import tomlkit
import threading
import queue
import copy
from . import ruff_adapter, config_manager

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
    def __init__(self):
        super().__init__()

        self.title("Ruff Studio")
        self.geometry("1280x800")

        self.current_directory = None
        self.pyproject_path = None
        self.pyproject_data = None
        self.all_rules = []
        self.rule_widgets = {}
        self.staged_changes = {}
        self.base_scan_results = []
        self.selected_rule_frame = None

        self.queue = queue.Queue()

        # Create main layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=3)

        # --- Top Bar ---
        self.top_frame = ctk.CTkFrame(self, height=50)
        self.top_frame.grid(
            row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=10
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
        self.info_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=0)
        self.info_label = ctk.CTkLabel(self.info_frame, text="Rule Info")
        self.info_label.pack(pady=10)

        self.results_frame = ctk.CTkScrollableFrame(self)
        self.results_frame.grid(row=1, column=2, sticky="nsew", padx=0, pady=0)
        self.results_label = ctk.CTkLabel(self.results_frame, text="Scan Results")
        self.results_label.pack(pady=10)

        self.run_in_thread(self._discover_rules_worker, "discover_rules")
        self.process_queue()

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

    def _run_scan_worker(self, command_name, directory, config=None):
        try:
            if config:
                results = ruff_adapter.run_scan_with_config(directory, config)
            else:
                results = ruff_adapter.run_scan(directory)
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
                self.managed_prefixes = {
                    cat['prefix'] for cat in self.all_rules.values()
                }
                self.managed_rules = {
                    rule['code']
                    for cat in self.all_rules.values()
                    for rule in cat['rules']
                }
            elif command == "run_scan":
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

    def select_directory(self):
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
            else:
                self.pyproject_data = tomlkit.document()

            for widget in self.results_frame.winfo_children():
                if widget != self.results_label:
                    widget.destroy()
            self.results_label.configure(text="Scanning...")

            self.run_in_thread(self._run_scan_worker, "run_scan", directory)
            self.update_rules_panel()

    def update_results_panel(self, results):
        self.results_label.configure(text="Scan Results")
        for widget in self.results_frame.winfo_children():
            if widget != self.results_label:
                widget.destroy()

        if not results:
            ctk.CTkLabel(self.results_frame, text="No issues found.").pack(pady=5)
            return

        for result in results:
            result_text = (
                f"{result['filename']}:{result['location']['row']}:"
                f"{result['location']['column']} {result['code']} {result['message']}"
            )
            ctk.CTkLabel(
                self.results_frame, text=result_text,
                wraplength=self.results_frame.winfo_width()-50, justify="left"
            ).pack(pady=2, anchor="w")

    def _make_hashable(self, data):
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

        for category_name, category_data in sorted_categories:
            category_frame = ctk.CTkFrame(self.rules_frame)
            category_frame.pack(fill="x", pady=(5, 1), padx=5)

            category_var = ctk.StringVar()
            category_cb = ctk.CTkCheckBox(
                category_frame,
                text=f"{category_name} ({category_data['prefix']})",
                variable=category_var,
                onvalue=category_data['prefix'],
                offvalue="",
                command=(
                    lambda p=category_data['prefix'], cn=category_name:
                    self.toggle_category(p, cn)
                )
            )
            category_cb.pack(side="left")
            category_cb.configure(state="disabled")

            self.rule_widgets[category_name] = {
                'category_frame': category_frame,
                'category_checkbox': category_cb,
                'category_variable': category_var,
                'original_border_color': category_cb.cget("border_color"),
                'prefix': category_data['prefix'],
                'rules': {}
            }

            # Add a toggle button for expanding/collapsing rules
            toggle_button = ctk.CTkButton(
                category_frame, text="▼", width=20,
                command=lambda cn=category_name: self.toggle_category_rules(cn)
            )
            toggle_button.pack(side="right", padx=5)

            rules_container = ctk.CTkFrame(self.rules_frame, fg_color="transparent")
            rules_container.pack(fill="x", padx=(25, 5))

            self.rule_widgets[category_name]['rules_container'] = rules_container
            self.rule_widgets[category_name]['toggle_button'] = toggle_button

            for rule in sorted(category_data['rules'], key=lambda r: r['code']):
                frame = ctk.CTkFrame(rules_container)
                frame.pack(fill="x", pady=1)
                var = ctk.StringVar()

                rule_text = f"{rule['code']}"
                if rule['status'] != 'stable':
                    rule_text += f" (⚠️ {rule['status']})"

                cb = ctk.CTkCheckBox(
                    frame, text=rule_text, variable=var, onvalue=rule['code'],
                    offvalue="", command=lambda rc=rule['code'], cn=category_name:
                    self.stage_rule_change(rc, cn)
                )
                cb.pack(side="left")

                label = ctk.CTkLabel(frame, text=f"{rule['name']}", anchor="w")
                label.pack(side="left", fill="x", expand=True, padx=5)

                if rule['status'] != 'stable':
                    Tooltip(cb, f"This rule is {rule['status']}.")

                cb.configure(state="disabled")
                rule_widget_data = {
                    'checkbox': cb, 'variable': var,
                    'rule_info': rule, 'frame': frame
                }
                self.rule_widgets[category_name]['rules'][rule['code']] = (
                    rule_widget_data
                )
                label.bind("<Button-1>", lambda event, r=rule: self.show_rule_info(r))

    def is_rule_enabled(self, rule_code, ruff_config):
        selected_codes = ruff_config.get("select", [])
        ignored_codes = ruff_config.get("ignore", [])

        is_selected = False
        for selected in selected_codes:
            if rule_code.startswith(selected):
                is_selected = True
                break
        if not is_selected:
            return False

        is_ignored = False
        for ignored in ignored_codes:
            if rule_code.startswith(ignored):
                is_ignored = True
                break
        return not is_ignored

    def get_effective_rule_state(self, rule_code, ruff_config):
        if rule_code in self.staged_changes:
            return self.staged_changes[rule_code]
        return self.is_rule_enabled(rule_code, ruff_config)

    def update_rules_panel(self):
        if not self.current_directory:
            for category_name, category_widgets in self.rule_widgets.items():
                category_widgets['category_checkbox'].configure(state="disabled")
                category_widgets['category_variable'].set("")
                for rule_code, rule_widget in category_widgets['rules'].items():
                    rule_widget['checkbox'].configure(state="disabled")
                    rule_widget['variable'].set("")
            return

        ruff_config = (
            self.pyproject_data.get("tool", {})
            .get("ruff", {})
            .get("lint", {})
        )
        for category_name, category_widgets in self.rule_widgets.items():
            category_widgets['category_checkbox'].configure(state="normal")

            all_rules_in_category_enabled = True
            any_rule_in_category_enabled = False

            for rule_code, rule_widget in category_widgets['rules'].items():
                rule_widget['checkbox'].configure(state="normal")
                is_enabled = self.get_effective_rule_state(rule_code, ruff_config)

                if is_enabled:
                    rule_widget['variable'].set(rule_code)
                    any_rule_in_category_enabled = True
                else:
                    rule_widget['variable'].set("")
                    all_rules_in_category_enabled = False

            if all_rules_in_category_enabled:
                category_widgets['category_variable'].set(category_widgets['prefix'])
                category_widgets['category_checkbox'].configure(border_color=category_widgets['original_border_color'])
            elif any_rule_in_category_enabled:
                category_widgets['category_variable'].set(category_widgets['prefix'])
                category_widgets['category_checkbox'].configure(border_color="yellow")
            else:
                category_widgets['category_variable'].set("")
                category_widgets['category_checkbox'].configure(border_color=category_widgets['original_border_color'])

    def stage_rule_change(self, rule_code, category_name):
        rule_widget = self.rule_widgets[category_name]['rules'][rule_code]
        is_checkbox_on = rule_widget['variable'].get() == rule_code
        self.staged_changes[rule_code] = is_checkbox_on
        self.simulate_button.configure(state="normal")
        self.apply_button.configure(state="normal")
        self.update_category_checkbox_state(category_name)

    def toggle_category(self, prefix, category_name):
        category_widget = self.rule_widgets[category_name]
        is_enabled = category_widget['category_variable'].get() == prefix

        for rule_code in category_widget['rules'].keys():
            self.staged_changes[rule_code] = is_enabled
            rule_widget = self.rule_widgets[category_name]['rules'][rule_code]
            if is_enabled:
                rule_widget['variable'].set(rule_code)
            else:
                rule_widget['variable'].set("")

        self.simulate_button.configure(state="normal")
        self.apply_button.configure(state="normal")
        self.update_category_checkbox_state(category_name)

    def toggle_category_rules(self, category_name):
        widget_info = self.rule_widgets[category_name]
        container = widget_info['rules_container']
        toggle_button = widget_info['toggle_button']
        category_frame = widget_info['category_frame']

        if container.winfo_viewable():
            container.pack_forget()
            toggle_button.configure(text="►")
        else:
            container.pack(fill="x", padx=(25, 5), after=category_frame)
            toggle_button.configure(text="▼")

    def update_category_checkbox_state(self, category_name):
        category_widgets = self.rule_widgets[category_name]
        ruff_config = (
            self.pyproject_data.get("tool", {})
            .get("ruff", {})
            .get("lint", {})
        )

        all_rules_on = True
        any_rule_on = False

        for rule_code, rule_widget in category_widgets['rules'].items():
            if self.get_effective_rule_state(rule_code, ruff_config):
                any_rule_on = True
            else:
                all_rules_on = False

        if all_rules_on:
            category_widgets['category_variable'].set(category_widgets['prefix'])
            category_widgets['category_checkbox'].configure(border_color=category_widgets['original_border_color'])
        elif any_rule_on:
            category_widgets['category_variable'].set(category_widgets['prefix'])
            category_widgets['category_checkbox'].configure(border_color="yellow")
        else:
            category_widgets['category_variable'].set("")
            category_widgets['category_checkbox'].configure(border_color=category_widgets['original_border_color'])

    def simulate_changes(self):
        if not self.pyproject_data:
            return
        sim_config_data = self.get_effective_config()
        self.results_label.configure(text="Simulating...")
        self.run_in_thread(
            self._run_scan_worker, "run_simulation",
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
        self.run_in_thread(self._run_scan_worker, "run_scan", self.current_directory)

    def get_effective_config(self):
        effective_data = copy.deepcopy(self.pyproject_data)
        ruff_config = (
            effective_data.setdefault("tool", {})
            .setdefault("ruff", {})
            .setdefault("lint", {})
        )

        current_select = set(ruff_config.get("select", []))
        current_ignore = set(ruff_config.get("ignore", []))

        # Preserve unmanaged rules
        final_select = {
            s for s in current_select
            if s not in self.managed_prefixes and s not in self.managed_rules
        }
        final_ignore = {
            i for i in current_ignore
            if i not in self.managed_prefixes and i not in self.managed_rules
        }

        for category_name, category_widgets in self.rule_widgets.items():
            prefix = category_widgets['prefix']

            category_rules = set(category_widgets['rules'].keys())

            enabled_rules = {
                rc for rc in category_rules
                if self.get_effective_rule_state(rc, ruff_config)
            }

            if len(enabled_rules) == len(category_rules):
                final_select.add(prefix)
            elif enabled_rules:
                final_select.add(prefix)
                final_ignore.update(category_rules - enabled_rules)

        ruff_config["select"] = sorted(list(final_select))
        ruff_config["ignore"] = sorted(list(final_ignore))
        return ruff_config

    def show_rule_info(self, rule):
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

        if rule.get('documentation'):
            ctk.CTkLabel(self.info_frame, text="─" * 40).pack(pady=5)
            ctk.CTkLabel(
                self.info_frame, text="Documentation:", justify="left"
            ).pack(pady=5, anchor="w")
            ctk.CTkLabel(
                self.info_frame, text=rule['documentation'],
                wraplength=250, justify="left"
            ).pack(pady=5, anchor="w")

        if rule.get('documentation'):
            ctk.CTkLabel(self.info_frame, text="─" * 40).pack(pady=5)
            ctk.CTkLabel(self.info_frame, text=f"Documentation:", justify="left").pack(pady=5, anchor="w")
            ctk.CTkLabel(self.info_frame, text=rule['documentation'], wraplength=250, justify="left").pack(pady=5, anchor="w")

if __name__ == "__main__":
    app = App()
    app.mainloop()
