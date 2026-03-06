import customtkinter as ctk


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_switch_view, on_compare_profiles=None, on_generate_pre_commit=None, **kwargs):
        super().__init__(master, width=200, corner_radius=0, **kwargs)
        self.on_switch_view = on_switch_view

        self.grid_rowconfigure(5, weight=1)  # Spacing between nav and actions

        self.logo_label = ctk.CTkLabel(
            self, text="Ruff Studio", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=20)

        self.rules_btn = ctk.CTkButton(
            self,
            text="⚙  Rules Manager",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            command=lambda: self._select_view("rules"),
        )
        self.rules_btn.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        self.analytics_btn = ctk.CTkButton(
            self,
            text="📊  Analytics",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            command=lambda: self._select_view("analytics"),
        )
        self.analytics_btn.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

        self.proposals_btn = ctk.CTkButton(
            self,
            text="📋  Governance",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            command=lambda: self._select_view("proposals"),
        )
        self.proposals_btn.grid(row=3, column=0, sticky="ew", padx=10, pady=5)

        # --- Separator ---
        separator = ctk.CTkFrame(self, height=1, fg_color=("gray70", "gray40"))
        separator.grid(row=4, column=0, sticky="ew", padx=15, pady=(15, 5))

        # --- Action buttons ---
        self.compare_profiles_btn = ctk.CTkButton(
            self,
            text="⚖  Compare Profiles",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            command=on_compare_profiles,
        )
        self.compare_profiles_btn.grid(row=6, column=0, sticky="ew", padx=10, pady=5)

        self.generate_pre_commit_button = ctk.CTkButton(
            self,
            text="🔧  Generate Pre-commit",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            state="disabled",
            command=on_generate_pre_commit,
        )
        self.generate_pre_commit_button.grid(row=7, column=0, sticky="ew", padx=10, pady=5)

        # Initial selection
        self._select_view("rules")

    def _select_view(self, view_name):
        # Update button styles
        for btn, name in [
            (self.rules_btn, "rules"),
            (self.analytics_btn, "analytics"),
            (self.proposals_btn, "proposals"),
        ]:
            if name == view_name:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")

        self.on_switch_view(view_name)
