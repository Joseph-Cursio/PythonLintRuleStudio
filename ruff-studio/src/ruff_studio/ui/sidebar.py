import customtkinter as ctk

_ACCENT = ("#3a86ff", "#79c0ff")


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_switch_view, on_compare_profiles=None, on_generate_pre_commit=None, **kwargs):
        super().__init__(master, width=200, corner_radius=0, **kwargs)
        self.on_switch_view = on_switch_view
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)  # Spacing between nav and actions

        self.logo_label = ctk.CTkLabel(
            self, text="Ruff Studio", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=20)

        self.rules_btn, self._rules_accent = self._make_nav_btn(1, "⚙  Rules Manager", "rules")
        self.analytics_btn, self._analytics_accent = self._make_nav_btn(2, "📊  Analytics", "analytics")
        self.proposals_btn, self._proposals_accent = self._make_nav_btn(3, "📋  Governance", "proposals")

        # --- Separator ---
        separator = ctk.CTkFrame(self, height=1, fg_color=("gray70", "gray40"))
        separator.grid(row=4, column=0, sticky="ew", padx=10, pady=(15, 5))

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

    def _make_nav_btn(self, row, text, view_name):
        """Build a nav row: 3px accent bar + button, both inside a wrapper frame."""
        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.grid(row=row, column=0, sticky="ew", pady=2)
        wrapper.grid_columnconfigure(1, weight=1)

        accent = ctk.CTkFrame(wrapper, width=3, corner_radius=0, fg_color="transparent")
        accent.grid(row=0, column=0, sticky="ns", padx=(4, 0))

        btn = ctk.CTkButton(
            wrapper,
            text=text,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            command=lambda: self._select_view(view_name),
        )
        btn.grid(row=0, column=1, sticky="ew", padx=(4, 10), pady=3)
        return btn, accent

    def _select_view(self, view_name):
        nav = [
            (self.rules_btn, self._rules_accent, "rules"),
            (self.analytics_btn, self._analytics_accent, "analytics"),
            (self.proposals_btn, self._proposals_accent, "proposals"),
        ]
        for btn, accent, name in nav:
            if name == view_name:
                btn.configure(fg_color=("gray75", "gray25"))
                accent.configure(fg_color=_ACCENT)
            else:
                btn.configure(fg_color="transparent")
                accent.configure(fg_color="transparent")

        self.on_switch_view(view_name)
