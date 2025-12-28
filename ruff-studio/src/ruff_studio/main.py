import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import tomlkit
import threading
import queue
import copy
from . import ruff_adapter, config_manager

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

        self.queue = queue.Queue()

        # Create main layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_columnconfigure(2, weight=1)

        # --- Top Bar ---
        self.top_frame = ctk.CTkFrame(self, height=50)
        self.top_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=10)

        self.select_button = ctk.CTkButton(self.top_frame, text="Select Directory", command=self.select_directory)
        self.select_button.pack(side="left", padx=10)
        self.directory_label = ctk.CTkLabel(self.top_frame, text="No directory selected")
        self.directory_label.pack(side="left", padx=10)

        self.action_frame = ctk.CTkFrame(self.top_frame)
        self.action_frame.pack(side="right", padx=10)
        self.simulate_button = ctk.CTkButton(self.action_frame, text="Simulate Changes", state="disabled", command=self.simulate_changes)
        self.simulate_button.pack(side="left", padx=5)
        self.apply_button = ctk.CTkButton(self.action_frame, text="Apply Changes", state="disabled", command=self.apply_changes)
        self.apply_button.pack(side="left", padx=5)

        self.status_label = ctk.CTkLabel(self.top_frame, text="")
        self.status_label.pack(side="right", padx=10)

        # --- Panels ---
        self.rules_frame = ctk.CTkScrollableFrame(self)
        self.rules_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=0)
        self.rules_label = ctk.CTkLabel(self.rules_frame, text="Rules (Loading...)")
        self.rules_label.pack(pady=10)

        self.results_frame = ctk.CTkScrollableFrame(self)
        self.results_frame.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self.results_label = ctk.CTkLabel(self.results_frame, text="Scan Results")
        self.results_label.pack(pady=10)

        self.info_frame = ctk.CTkScrollableFrame(self)
        self.info_frame.grid(row=1, column=2, sticky="nsew", padx=10, pady=0)
        self.info_label = ctk.CTkLabel(self.info_frame, text="Rule Info")
        self.info_label.pack(pady=10)

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
                    messagebox.showerror("Error", f"An unexpected error occurred:\n\n{data}")
            elif command == "discover_rules":
                self.all_rules = data
                self.rules_label.configure(text="Rules")
                self.populate_rules_initial()
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
                if widget != self.results_label: widget.destroy()
            self.results_label.configure(text="Scanning...")

            self.run_in_thread(self._run_scan_worker, "run_scan", directory)
            self.update_rules_panel()

    def update_results_panel(self, results):
        self.results_label.configure(text="Scan Results")
        for widget in self.results_frame.winfo_children():
            if widget != self.results_label: widget.destroy()

        if not results:
            ctk.CTkLabel(self.results_frame, text="No issues found.").pack(pady=5)
            return

        for result in results:
            result_text = f"{result['filename']}:{result['location']['row']}:{result['location']['column']} {result['code']} {result['message']}"
            ctk.CTkLabel(self.results_frame, text=result_text, wraplength=self.results_frame.winfo_width()-50, justify="left").pack(pady=2, anchor="w")

    def update_simulation_results_panel(self, sim_results):
        self.results_label.configure(text="Simulation Results")
        for widget in self.results_frame.winfo_children():
            if widget != self.results_label: widget.destroy()

        base_set = {tuple(sorted(d.items())) for d in self.base_scan_results}
        sim_set = {tuple(sorted(d.items())) for d in sim_results}

        new_violations = [dict(s) for s in sim_set - base_set]
        fixed_violations = [dict(s) for s in base_set - sim_set]

        summary = f"Simulation complete: {len(new_violations)} new violations, {len(fixed_violations)} fixed violations."
        ctk.CTkLabel(self.results_frame, text=summary, font=("", 14, "bold")).pack(pady=10)

        if new_violations:
            ctk.CTkLabel(self.results_frame, text="New Violations:", font=("", 12, "underline")).pack(pady=5)
            for result in new_violations:
                result_text = f"+ {result['filename']}:{result['location']['row']}:{result['location']['column']} {result['code']} {result['message']}"
                ctk.CTkLabel(self.results_frame, text=result_text, wraplength=self.results_frame.winfo_width()-50, justify="left").pack(pady=2, anchor="w")

        if fixed_violations:
            ctk.CTkLabel(self.results_frame, text="Fixed Violations:", font=("", 12, "underline")).pack(pady=5)
            for result in fixed_violations:
                result_text = f"- {result['filename']}:{result['location']['row']}:{result['location']['column']} {result['code']} {result['message']}"
                ctk.CTkLabel(self.results_frame, text=result_text, wraplength=self.results_frame.winfo_width()-50, justify="left").pack(pady=2, anchor="w")

    def populate_rules_initial(self):
        for rule in self.all_rules:
            frame = ctk.CTkFrame(self.rules_frame)
            frame.pack(fill="x", pady=1)
            var = ctk.StringVar()
            cb = ctk.CTkCheckBox(frame, text=f"{rule['code']}", variable=var, onvalue=rule['code'], offvalue="", command=lambda rc=rule['code']: self.stage_rule_change(rc))
            cb.pack(side="left")
            label = ctk.CTkLabel(frame, text=f"{rule['name']}", anchor="w")
            label.pack(side="left", fill="x", expand=True, padx=5)
            cb.configure(state="disabled")
            self.rule_widgets[rule['code']] = {'checkbox': cb, 'variable': var, 'rule_info': rule}
            label.bind("<Button-1>", lambda event, r=rule: self.show_rule_info(r))

    def is_rule_enabled(self, rule_code, ruff_config):
        selected_codes = ruff_config.get("select", [])
        ignored_codes = ruff_config.get("ignore", [])

        is_selected = False
        for selected in selected_codes:
            if rule_code.startswith(selected):
                is_selected = True
                break
        if not is_selected: return False

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
            for rule_code in self.rule_widgets:
                self.rule_widgets[rule_code]['checkbox'].configure(state="disabled")
                self.rule_widgets[rule_code]['variable'].set("")
            return

        ruff_config = self.pyproject_data.get("tool", {}).get("ruff", {}).get("lint", {})
        for rule_code, widgets in self.rule_widgets.items():
            widgets['checkbox'].configure(state="normal")
            if self.get_effective_rule_state(rule_code, ruff_config):
                widgets['variable'].set(rule_code)
            else:
                widgets['variable'].set("")

    def stage_rule_change(self, rule_code):
        is_checkbox_on = self.rule_widgets[rule_code]['variable'].get() == rule_code
        self.staged_changes[rule_code] = is_checkbox_on
        self.simulate_button.configure(state="normal")
        self.apply_button.configure(state="normal")

    def simulate_changes(self):
        if not self.pyproject_data: return
        sim_config_data = self.get_effective_config()
        self.results_label.configure(text="Simulating...")
        self.run_in_thread(self._run_scan_worker, "run_simulation", self.current_directory, sim_config_data)

    def apply_changes(self):
        if not self.pyproject_data or not self.pyproject_path: return

        ruff_config = self.pyproject_data.setdefault("tool", {}).setdefault("ruff", {}).setdefault("lint", {})
        select_list = ruff_config.setdefault("select", [])
        ignore_list = ruff_config.setdefault("ignore", [])

        for rule_code, is_enabled in self.staged_changes.items():
            if is_enabled:
                if rule_code in ignore_list:
                    ignore_list.remove(rule_code)
                is_selected = any(rule_code.startswith(s) for s in select_list)
                if not is_selected:
                    select_list.append(rule_code)
            else:
                is_ignored = any(rule_code.startswith(i) for i in ignore_list)
                if not is_ignored:
                    ignore_list.append(rule_code)

        ruff_config["select"] = sorted(list(set(select_list)))
        ruff_config["ignore"] = sorted(list(set(ignore_list)))

        config_manager.write_pyproject(self.pyproject_path, self.pyproject_data)

        self.staged_changes = {}
        self.simulate_button.configure(state="disabled")
        self.apply_button.configure(state="disabled")

        self.update_rules_panel()
        self.run_in_thread(self._run_scan_worker, "run_scan", self.current_directory)

    def get_effective_config(self):
        effective_data = copy.deepcopy(self.pyproject_data)
        ruff_config = effective_data.setdefault("tool", {}).setdefault("ruff", {}).setdefault("lint", {})

        select_list = ruff_config.setdefault("select", [])
        ignore_list = ruff_config.setdefault("ignore", [])

        for rule_code, is_enabled in self.staged_changes.items():
            if is_enabled:
                if rule_code in ignore_list: ignore_list.remove(rule_code)
                if not any(rule_code.startswith(s) for s in select_list):
                    select_list.append(rule_code)
            else:
                if not any(rule_code.startswith(i) for i in ignore_list):
                    ignore_list.append(rule_code)

        ruff_config["select"] = sorted(list(set(select_list)))
        ruff_config["ignore"] = sorted(list(set(ignore_list)))

        return ruff_config

    def show_rule_info(self, rule):
        for widget in self.info_frame.winfo_children():
            if widget != self.info_label: widget.destroy()
        ctk.CTkLabel(self.info_frame, text=f"Code: {rule['code']}", wraplength=250).pack(pady=5, anchor="w")
        ctk.CTkLabel(self.info_frame, text=f"Name: {rule['name']}", wraplength=250).pack(pady=5, anchor="w")
        ctk.CTkLabel(self.info_frame, text=f"Fixable: {'Yes' if rule['fix'] else 'No'}", wraplength=250).pack(pady=5, anchor="w")
        ctk.CTkLabel(self.info_frame, text=f"Summary: {rule['summary']}", wraplength=250, justify="left").pack(pady=5, anchor="w")

if __name__ == "__main__":
    app = App()
    app.mainloop()
