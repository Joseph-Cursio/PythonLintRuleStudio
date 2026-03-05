import customtkinter as ctk


class ResultsPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.controller = controller

        self.results_label = ctk.CTkLabel(
            self, text="Scan Results", font=("", 16, "bold")
        )
        self.results_label.pack(pady=10)

    def clear(self):
        for widget in self.winfo_children():
            if widget != self.results_label:
                widget.destroy()

    def set_results(self, results):
        self.clear()
        self._parent_canvas.yview_moveto(0)
        count = len(results)
        self.results_label.configure(text=f"Scan Results ({count})")

        if not results:
            ctk.CTkLabel(self, text="No violations found!").pack(pady=20)
            return

        for result in results:
            author_info = f" (Author: {result.author})" if result.author else ""
            result_text = (
                f"{result.file_path}:{result.line_number}:"
                f"{result.column} {result.rule_id}{author_info}\n"
                f"  {result.message}"
            )
            ctk.CTkLabel(
                self,
                text=result_text,
                wraplength=self.winfo_width() - 50,
                justify="left",
                anchor="w",
            ).pack(pady=2, fill="x", padx=5)

    def set_simulation_results(self, sim_results):
        self.clear()
        self._parent_canvas.yview_moveto(0)

        base_results = self.controller.base_scan_results

        # Helper to create a unique key for comparison
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

        # Show Removed (Fixed) first
        if removed_keys:
            ctk.CTkLabel(
                self,
                text="--- FIXED/IGNORED ---",
                text_color="#f44336",
                font=("", 12, "bold"),
            ).pack(pady=5)
            for k in sorted(removed_keys):
                r = base_keys[k]
                txt = (
                    f"- {r.file_path}:{r.line_number}:{r.column} {r.rule_id}\n"
                    f"  {r.message}"
                )
                ctk.CTkLabel(
                    self, text=txt, text_color="#ef5350", anchor="w", justify="left"
                ).pack(fill="x", padx=10)

        # Show Added
        if added_keys:
            ctk.CTkLabel(
                self,
                text="--- NEW VIOLATIONS ---",
                text_color="#4caf50",
                font=("", 12, "bold"),
            ).pack(pady=5)
            for k in sorted(added_keys):
                r = sim_keys[k]
                loc = r["location"]
                txt = (
                    f"+ {r['filename']}:{loc['row']}:{loc['column']} {r['code']}\n"
                    f"  {r['message']}"
                )
                ctk.CTkLabel(
                    self, text=txt, text_color="#81c784", anchor="w", justify="left"
                ).pack(fill="x", padx=10)

        # Summarize kept
        if kept_keys:
            ctk.CTkLabel(
                self,
                text=f"... and {len(kept_keys)} existing violations remain unchanged.",
                text_color="gray",
            ).pack(pady=10)

    def set_scanning(self):
        self.clear()
        self.results_label.configure(text="Scanning...")
