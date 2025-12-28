import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import threading
import queue
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

    def _run_scan_worker(self, command_name, directory):
        try:
            results = ruff_adapter.run_scan(directory)
            self.queue.put((command_name, results))
        except (RuntimeError, FileNotFoundError) as e:
            self.queue.put(("error", e))

    def process_queue(self):
        try:
            command, data = self.queue.get_nowait()

            if command == "error":
                if isinstance(data, FileNotFoundError):
                    messagebox.showerror("Error", "Ruff executable not found. Please ensure ruff is installed and in your system's PATH.")
                else:
                    messagebox.showerror("Error", f"An unexpected error occurred:\n\n{data}")
            elif command == "discover_rules":
                self.all_rules = data
                self.rules_label.configure(text="Rules")
                self.populate_rules_initial()
            elif command == "run_scan":
                self.update_results_panel(data)

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
            if os.path.exists(self.pyproject_path):
                self.pyproject_data = config_manager.read_pyproject(self.pyproject_path)
            else:
                self.pyproject_data = None

            for widget in self.results_frame.winfo_children():
                if widget != self.results_label: widget.destroy()
            self.results_label.configure(text="Scanning...")

            self.run_in_thread(self._run_scan_worker, "run_scan", directory)
            self.update_rules_panel()

    def update_results_panel(self, results):
        self.results_label.configure(text="Scan Results")
        if not results:
            ctk.CTkLabel(self.results_frame, text="No issues found.").pack(pady=5)
            return

        for result in results:
            result_text = f"{result['filename']}:{result['location']['row']}:{result['location']['column']} {result['code']} {result['message']}"
            ctk.CTkLabel(self.results_frame, text=result_text, wraplength=self.results_frame.winfo_width()-50, justify="left").pack(pady=2, anchor="w")

    def populate_rules_initial(self):
        for rule in self.all_rules:
            frame = ctk.CTkFrame(self.rules_frame)
            frame.pack(fill="x", pady=1)
            var = ctk.StringVar()
            cb = ctk.CTkCheckBox(frame, text=f"{rule['code']}", variable=var, onvalue=rule['code'], offvalue="")
            cb.pack(side="left")
            label = ctk.CTkLabel(frame, text=f"{rule['name']}", anchor="w")
            label.pack(side="left", fill="x", expand=True, padx=5)
            cb.configure(state="disabled")
            self.rule_widgets[rule['code']] = {'checkbox': cb, 'variable': var, 'rule_info': rule}
            label.bind("<Button-1>", lambda event, r=rule: self.show_rule_info(r))

    def is_rule_enabled(self, rule_code, selected_codes):
        for selected in selected_codes:
            if rule_code.startswith(selected):
                return True
        return False

    def update_rules_panel(self):
        if not self.pyproject_data:
            for rule_code in self.rule_widgets:
                self.rule_widgets[rule_code]['checkbox'].configure(state="disabled")
                self.rule_widgets[rule_code]['variable'].set("")
            return

        selected_codes = self.pyproject_data.get("tool", {}).get("ruff", {}).get("lint", {}).get("select", [])

        for rule_code, widgets in self.rule_widgets.items():
            widgets['checkbox'].configure(state="normal", command=lambda rc=rule_code: self.toggle_rule(rc))
            if self.is_rule_enabled(rule_code, selected_codes):
                widgets['variable'].set(rule_code)
            else:
                widgets['variable'].set("")

    def toggle_rule(self, rule_code):
        if not self.pyproject_data or not self.pyproject_path: return

        ruff_config = self.pyproject_data.setdefault("tool", {}).setdefault("ruff", {}).setdefault("lint", {})
        selected_codes = ruff_config.setdefault("select", [])

        is_currently_enabled = self.is_rule_enabled(rule_code, selected_codes)
        is_checkbox_on = self.rule_widgets[rule_code]['variable'].get() == rule_code

        if is_checkbox_on and not is_currently_enabled:
            # Enable rule: just add the specific code
            selected_codes.append(rule_code)
        elif not is_checkbox_on and is_currently_enabled:
            # Disable rule: this is the complex case
            # Find the prefix that enables this rule
            enabling_prefix = None
            for selected in selected_codes:
                if rule_code.startswith(selected):
                    enabling_prefix = selected
                    break

            if enabling_prefix == rule_code: # It was enabled by its full code
                selected_codes.remove(rule_code)
            elif enabling_prefix: # It was enabled by a prefix
                # Expand the prefix
                selected_codes.remove(enabling_prefix)
                for rule in self.all_rules:
                    if rule['code'].startswith(enabling_prefix) and rule['code'] != rule_code:
                        if not self.is_rule_enabled(rule['code'], selected_codes):
                             selected_codes.append(rule['code'])

        # Clean up duplicates
        ruff_config["select"] = sorted(list(set(selected_codes)))

        config_manager.write_pyproject(self.pyproject_path, self.pyproject_data)
        # Refresh the panel to reflect the change
        self.update_rules_panel()

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
