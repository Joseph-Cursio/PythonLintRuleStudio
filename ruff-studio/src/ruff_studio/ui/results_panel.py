import customtkinter as ctk


class ResultsPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.controller = controller
        self._message_labels = []

        self.results_label = ctk.CTkLabel(
            self, text="Scan Results", font=("", 16, "bold")
        )
        self.results_label.pack(pady=10)
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        wrap = max(100, event.width - 120)
        for lbl in self._message_labels:
            try:
                lbl.configure(wraplength=wrap)
            except Exception:
                pass

    def _wrap(self):
        w = self.winfo_width()
        return max(100, w - 120) if w > 1 else 300

    def clear(self):
        self._message_labels = []
        for widget in self.winfo_children():
            if widget != self.results_label:
                widget.destroy()

    def _make_row(self, rule_id, location, message, author=None,
                  badge_color=None, row_fg=None):
        """Build a single violation card row."""
        card = ctk.CTkFrame(
            self,
            fg_color=row_fg or ("gray88", "gray20"),
            corner_radius=6,
        )
        card.pack(fill="x", pady=2, padx=5)
        card.grid_columnconfigure(1, weight=1)

        # Colored rule-code badge
        color = badge_color or self.controller.get_color_for_prefix(rule_id)
        ctk.CTkLabel(
            card,
            text=rule_id,
            font=("", 11, "bold"),
            text_color=color,
            width=58,
            anchor="center",
        ).grid(row=0, column=0, rowspan=2, padx=(8, 6), pady=8, sticky="ns")

        # Vertical divider
        ctk.CTkFrame(card, width=1, fg_color=("gray70", "gray40")).grid(
            row=0, column=1, rowspan=2, sticky="ns", pady=4
        )

        # Location (muted)
        ctk.CTkLabel(
            card,
            text=location,
            font=("", 11),
            text_color=("gray45", "gray58"),
            anchor="w",
        ).grid(row=0, column=2, sticky="w", padx=(8, 8), pady=(7, 1))

        # Message
        msg_lbl = ctk.CTkLabel(
            card,
            text=message,
            font=("", 12),
            anchor="w",
            justify="left",
            wraplength=self._wrap(),
        )
        msg_lbl.grid(row=1, column=2, sticky="w", padx=(8, 8), pady=(0, 7))
        self._message_labels.append(msg_lbl)

        # Author badge (right-aligned, if present)
        if author:
            ctk.CTkLabel(
                card,
                text=f"  {author}",
                font=("", 10),
                text_color=("gray50", "gray55"),
                anchor="e",
            ).grid(row=0, column=3, padx=(0, 8), pady=(7, 1))

        card.grid_columnconfigure(2, weight=1)
        return card

    def set_results(self, results):
        self.clear()
        self._parent_canvas.yview_moveto(0)
        count = len(results)
        self.results_label.configure(text=f"Scan Results ({count})")

        if not results:
            ctk.CTkLabel(
                self, text="✓  No violations found!", text_color=("green", "#81c784")
            ).pack(pady=20)
            return

        for result in results:
            location = (
                f"{result.file_path}:{result.line_number}:{result.column}"
            )
            self._make_row(
                rule_id=result.rule_id,
                location=location,
                message=result.message,
                author=result.author or None,
            )

    def set_simulation_results(self, sim_results):
        self.clear()
        self._parent_canvas.yview_moveto(0)

        base_results = self.controller.base_scan_results

        def get_key(r):
            if hasattr(r, "file_path"):  # UnifiedViolationModel
                return f"{r.file_path}:{r.line_number}:{r.column}:{r.rule_id}"
            else:  # Raw ruff dict
                loc = r["location"]
                return f"{r['filename']}:{loc['row']}:{loc['column']}:{r['code']}"

        base_keys = {get_key(r): r for r in base_results}
        sim_keys = {get_key(r): r for r in sim_results}

        removed_keys = base_keys.keys() - sim_keys.keys()
        added_keys = sim_keys.keys() - base_keys.keys()
        kept_keys = base_keys.keys() & sim_keys.keys()

        count_delta = len(sim_results) - len(base_results)
        delta_str = f"({'+' if count_delta >= 0 else ''}{count_delta})"
        self.results_label.configure(text=f"Simulation Results {delta_str}")

        if not sim_results and not removed_keys:
            ctk.CTkLabel(self, text="Dry-run: No change in violations.").pack(pady=20)
            return

        # Fixed / removed violations
        if removed_keys:
            ctk.CTkLabel(
                self,
                text="FIXED / IGNORED",
                text_color="#ef5350",
                font=("", 12, "bold"),
            ).pack(pady=(10, 2), anchor="w", padx=10)
            for k in sorted(removed_keys):
                r = base_keys[k]
                self._make_row(
                    rule_id=r.rule_id,
                    location=f"{r.file_path}:{r.line_number}:{r.column}",
                    message=r.message,
                    badge_color="#ef5350",
                    row_fg=("#fce4e4", "#3b1a1a"),
                )

        # New violations
        if added_keys:
            ctk.CTkLabel(
                self,
                text="NEW VIOLATIONS",
                text_color="#81c784",
                font=("", 12, "bold"),
            ).pack(pady=(10, 2), anchor="w", padx=10)
            for k in sorted(added_keys):
                r = sim_keys[k]
                loc = r["location"]
                self._make_row(
                    rule_id=r["code"],
                    location=f"{r['filename']}:{loc['row']}:{loc['column']}",
                    message=r["message"],
                    badge_color="#81c784",
                    row_fg=("#e8f5e9", "#1a3b1a"),
                )

        # Unchanged summary
        if kept_keys:
            ctk.CTkLabel(
                self,
                text=f"  {len(kept_keys)} existing violations unchanged",
                text_color=("gray50", "gray55"),
                font=("", 11),
            ).pack(pady=10, anchor="w", padx=10)

    def set_scanning(self):
        self.clear()
        self.results_label.configure(text="Scanning...")
