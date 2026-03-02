import customtkinter as ctk
from .. import profile_manager

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

        self.profile1_var = ctk.StringVar(
            value=self.profiles[0] if self.profiles else ""
        )
        self.profile2_var = ctk.StringVar(
            value=self.profiles[1] if len(self.profiles) > 1 else ""
        )

        self.profile1_menu = ctk.CTkOptionMenu(
            top_frame, variable=self.profile1_var, values=self.profiles
        )
        self.profile1_menu.pack(side="left", padx=5)

        ctk.CTkLabel(top_frame, text="vs.").pack(side="left", padx=5)

        self.profile2_menu = ctk.CTkOptionMenu(
            top_frame, variable=self.profile2_var, values=self.profiles
        )
        self.profile2_menu.pack(side="left", padx=5)

        self.compare_button = ctk.CTkButton(
            top_frame, text="Compare", command=self.do_comparison
        )
        self.compare_button.pack(side="left", padx=10)

        # --- Results Textbox ---
        self.results_textbox = ctk.CTkTextbox(self, wrap="word")
        self.results_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.results_textbox.insert(
            "1.0", 
            "Select two profiles and click 'Compare' to see the differences."
        )
        self.results_textbox.configure(state="disabled")

    def do_comparison(self):
        p1 = self.profile1_var.get()
        p2 = self.profile2_var.get()

        if not p1 or not p2 or p1 == p2:
            self.results_textbox.configure(state="normal")
            self.results_textbox.delete("1.0", "end")
            self.results_textbox.insert(
                "1.0", "Please select two different profiles to compare."
            )
            self.results_textbox.configure(state="disabled")
            return

        diff = profile_manager.compare_profiles(p1, p2)

        report = f"Comparing '{p1}' vs '{p2}':\n\n"
        report += "--- RULES SELECTED --- \n"
        if diff["select_only_in_1"]:
            lines = "\n".join(f"  - {r}" for r in diff["select_only_in_1"])
            report += f"\nOnly in '{p1}':\n{lines}\n"
        if diff["select_only_in_2"]:
            lines = "\n".join(f"  - {r}" for r in diff["select_only_in_2"])
            report += f"\nOnly in '{p2}':\n{lines}\n"

        report += "\n--- RULES IGNORED ---\n"
        if diff["ignore_only_in_1"]:
            lines = "\n".join(f"  - {r}" for r in diff["ignore_only_in_1"])
            report += f"\nOnly in '{p1}':\n{lines}\n"
        if diff["ignore_only_in_2"]:
            lines = "\n".join(f"  - {r}" for r in diff["ignore_only_in_2"])
            report += f"\nOnly in '{p2}':\n{lines}\n"

        report += "\n--- COMMON RULES ---\n"
        if diff["common_select"]:
            lines = "\n".join(f"  - {r}" for r in diff["common_select"])
            report += f"\nCommonly Selected:\n{lines}\n"
        if diff["common_ignore"]:
            lines = "\n".join(f"  - {r}" for r in diff["common_ignore"])
            report += f"\nCommonly Ignored:\n{lines}\n"

        self.results_textbox.configure(state="normal")
        self.results_textbox.delete("1.0", "end")
        self.results_textbox.insert("1.0", report)
        self.results_textbox.configure(state="disabled")
