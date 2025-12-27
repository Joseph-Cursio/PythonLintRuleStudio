import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
from . import ruff_adapter, config_manager

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Ruff Studio")
        self.geometry("1280x800")

        self.current_directory = None
        self.pyproject_path = None
        self.pyproject_data = None

        try:
            self.all_rules = ruff_adapter.discover_rules()
        except RuntimeError as e:
            messagebox.showerror("Initialization Error", f"Failed to discover ruff rules. Is ruff installed and in your PATH?\n\n{e}")
            self.all_rules = []

        self.rule_widgets = {}

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

        # --- Left Panel (Rules) ---
        self.rules_frame = ctk.CTkScrollableFrame(self)
        self.rules_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=0)
        self.rules_label = ctk.CTkLabel(self.rules_frame, text="Rules")
        self.rules_label.pack(pady=10)

        # --- Middle Panel (Results) ---
        self.results_frame = ctk.CTkScrollableFrame(self)
        self.results_frame.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self.results_label = ctk.CTkLabel(self.results_frame, text="Scan Results")
        self.results_label.pack(pady=10)

        # --- Right Panel (Info) ---
        self.info_frame = ctk.CTkScrollableFrame(self)
        self.info_frame.grid(row=1, column=2, sticky="nsew", padx=10, pady=0)
        self.info_label = ctk.CTkLabel(self.info_frame, text="Rule Info")
        self.info_label.pack(pady=10)

        self.populate_rules_initial()

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
            self.run_scan(directory)
            self.update_rules_panel()

    def run_scan(self, directory):
        for widget in self.results_frame.winfo_children():
            if widget != self.results_label:
                widget.destroy()
        try:
            results = ruff_adapter.run_scan(directory)
            if not results:
                ctk.CTkLabel(self.results_frame, text="No issues found.").pack(pady=5)
                return

            for result in results:
                result_text = f"{result['filename']}:{result['location']['row']}:{result['location']['column']} {result['code']} {result['message']}"
                ctk.CTkLabel(self.results_frame, text=result_text).pack(pady=5, anchor="w")
        except RuntimeError as e:
            messagebox.showerror("Scan Error", f"An error occurred during the ruff scan:\n\n{e}")
            ctk.CTkLabel(self.results_frame, text=f"Scan failed: {e}", wraplength=400).pack(pady=5, anchor="w")


    def populate_rules_initial(self):
        for rule in self.all_rules:
            frame = ctk.CTkFrame(self.rules_frame)
            frame.pack(fill="x", pady=2)

            var = ctk.StringVar()
            cb = ctk.CTkCheckBox(frame, text=f"{rule['code']}: {rule['name']}", variable=var, onvalue=rule['code'], offvalue="")
            cb.pack(side="left", anchor="w")
            cb.configure(state="disabled")

            self.rule_widgets[rule['code']] = {'checkbox': cb, 'variable': var, 'rule_info': rule}

            cb.bind("<Button-1>", lambda event, r=rule: self.show_rule_info(r))


    def update_rules_panel(self):
        if not self.pyproject_data:
            for rule_code in self.rule_widgets:
                self.rule_widgets[rule_code]['checkbox'].configure(state="disabled")
                self.rule_widgets[rule_code]['variable'].set("")
            return

        selected_rules = self.pyproject_data.get("tool", {}).get("ruff", {}).get("lint", {}).get("select", [])

        for rule_code, widgets in self.rule_widgets.items():
            widgets['checkbox'].configure(state="normal", command=lambda rc=rule_code: self.toggle_rule(rc))
            if rule_code in selected_rules:
                widgets['variable'].set(rule_code)
            else:
                widgets['variable'].set("")

    def toggle_rule(self, rule_code):
        if not self.pyproject_data or not self.pyproject_path:
            return

        ruff_config = self.pyproject_data.setdefault("tool", {}).setdefault("ruff", {}).setdefault("lint", {})
        selected_rules = ruff_config.setdefault("select", [])

        var = self.rule_widgets[rule_code]['variable']
        if var.get() == rule_code:
            if rule_code not in selected_rules:
                selected_rules.append(rule_code)
        else:
            if rule_code in selected_rules:
                selected_rules.remove(rule_code)

        config_manager.write_pyproject(self.pyproject_path, self.pyproject_data)

    def show_rule_info(self, rule):
        for widget in self.info_frame.winfo_children():
            if widget != self.info_label:
                widget.destroy()

        ctk.CTkLabel(self.info_frame, text=f"Code: {rule['code']}", wraplength=250).pack(pady=5, anchor="w")
        ctk.CTkLabel(self.info_frame, text=f"Name: {rule['name']}", wraplength=250).pack(pady=5, anchor="w")
        ctk.CTkLabel(self.info_frame, text=f"Fixable: {'Yes' if rule['fix'] else 'No'}", wraplength=250).pack(pady=5, anchor="w")
        ctk.CTkLabel(self.info_frame, text=f"Summary: {rule['summary']}", wraplength=250, justify="left").pack(pady=5, anchor="w")


if __name__ == "__main__":
    app = App()
    app.mainloop()
