import customtkinter as ctk


class AnalyticsView(ctk.CTkFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Header ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)

        ctk.CTkLabel(
            header_frame, text="Code Quality Insights", font=("", 24, "bold")
        ).pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            header_frame, text="Refresh Data", command=self.refresh, width=120
        )
        self.refresh_btn.pack(side="right", padx=10)

        # --- Main Content (Scrollable) ---
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.scroll_frame.grid_columnconfigure((0, 1), weight=1)

        if self.controller.analyzer:
            self.refresh()

    def refresh(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self._populate_analytics()

    def _populate_analytics(self):
        # 1. Summary Card
        history = self.controller.get_scan_history()
        latest_count = history[0][3] if history else 0
        prev_count = history[1][3] if len(history) > 1 else latest_count
        delta = latest_count - prev_count
        delta_color = "red" if delta > 0 else "green"
        delta_text = f"{'+' if delta > 0 else ''}{delta}" if delta != 0 else "No change"

        summary_frame = ctk.CTkFrame(self.scroll_frame)
        summary_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=10, padx=5)

        ctk.CTkLabel(
            summary_frame,
            text=f"Latest Scan: {latest_count} Violations",
            font=("", 18, "bold"),
        ).pack(pady=(10, 0))

        ctk.CTkLabel(
            summary_frame, text=f"Trend: {delta_text}", text_color=delta_color
        ).pack(pady=(0, 10))

        # 2. Author Attribution
        author_frame = ctk.CTkFrame(self.scroll_frame)
        author_frame.grid(row=1, column=0, sticky="nsew", pady=10, padx=5)
        ctk.CTkLabel(
            author_frame, text="Violations by Author", font=("", 14, "bold")
        ).pack(pady=10)

        authors = self.controller.get_author_stats()
        if not authors:
            ctk.CTkLabel(author_frame, text="No data available").pack(pady=5)
        else:
            max_a = max(authors.values(), default=1)
            for author, count in authors.items():
                name = author if author else "Unknown"
                self._make_bar_row(author_frame, name, count, max_a)

        # 3. Rule Hotspots
        hotspot_frame = ctk.CTkFrame(self.scroll_frame)
        hotspot_frame.grid(row=1, column=1, sticky="nsew", pady=10, padx=5)
        ctk.CTkLabel(
            hotspot_frame, text="Top Rule Hotspots", font=("", 14, "bold")
        ).pack(pady=10)

        rules = self.controller.get_rule_hotspots()
        if not rules:
            ctk.CTkLabel(hotspot_frame, text="No data available").pack(pady=5)
        else:
            max_r = max(rules.values(), default=1)
            for rule_id, count in rules.items():
                color = self.controller.get_color_for_prefix(rule_id)
                self._make_bar_row(hotspot_frame, rule_id, count, max_r,
                                   bar_color=color)

        # 4. History Log
        history_frame = ctk.CTkFrame(self.scroll_frame)
        history_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=10, padx=5)
        ctk.CTkLabel(
            history_frame, text="Recent Scan History", font=("", 14, "bold")
        ).pack(pady=10)

        for run in history:
            ts = run[1][:19]
            branch = run[2] if run[2] else "N/A"
            self._make_history_row(history_frame, ts, branch, run[3])

    def _make_bar_row(self, parent, label, count, max_count, bar_color=None):
        """Render a name + proportional progress bar + count label."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(2, 5))
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row, text=label, anchor="w", width=100, font=("", 12),
        ).grid(row=0, column=0, sticky="w")

        bar = ctk.CTkProgressBar(row, height=10, corner_radius=5,
                                  progress_color=bar_color or "#3a86ff")
        bar.set(count / max_count if max_count > 0 else 0)
        bar.grid(row=0, column=1, sticky="ew", padx=(8, 8))

        ctk.CTkLabel(
            row, text=str(count), anchor="e", width=36, font=("", 12),
            text_color=("gray40", "gray60"),
        ).grid(row=0, column=2, sticky="e")

    def _make_history_row(self, parent, ts, branch, count):
        """Render a single scan history entry as a styled row."""
        row = ctk.CTkFrame(parent, fg_color=("gray92", "gray20"), corner_radius=6)
        row.pack(fill="x", padx=12, pady=2)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row, text=ts, font=("", 11), text_color=("gray35", "gray65"),
        ).grid(row=0, column=0, padx=(10, 8), pady=6, sticky="w")

        ctk.CTkLabel(
            row, text=f"branch: {branch}", font=("", 11),
            text_color=("gray50", "gray55"), anchor="w",
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            row, text=str(count), font=("", 12, "bold"),
            text_color=("#3a86ff", "#79c0ff"),
        ).grid(row=0, column=2, padx=(8, 10), pady=6, sticky="e")
