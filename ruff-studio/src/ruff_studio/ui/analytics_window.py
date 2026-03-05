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
            for author, count in authors.items():
                name = author if author else "Unknown"
                ctk.CTkLabel(author_frame, text=f"{name}: {count}").pack(
                    anchor="w", padx=20
                )

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
            for rule_id, count in rules.items():
                ctk.CTkLabel(hotspot_frame, text=f"{rule_id}: {count}").pack(
                    anchor="w", padx=20
                )

        # 4. History Log
        history_frame = ctk.CTkFrame(self.scroll_frame)
        history_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=10, padx=5)
        ctk.CTkLabel(
            history_frame, text="Recent Scan History", font=("", 14, "bold")
        ).pack(pady=10)

        for run in history:
            ts = run[1][:19]
            branch = run[2] if run[2] else "N/A"
            ctk.CTkLabel(
                history_frame, text=f"{ts} | Branch: {branch} | Count: {run[3]}"
            ).pack(anchor="w", padx=20, pady=2)
