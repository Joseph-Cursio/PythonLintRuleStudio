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
                self, text=result_text,
                wraplength=self.winfo_width()-50, justify="left",
                anchor="w"
            ).pack(pady=2, fill="x", padx=5)

    def set_simulation_results(self, sim_results):
        self.clear()
        self._parent_canvas.yview_moveto(0)
        self.results_label.configure(text="Simulation Results")
        
        if not sim_results:
            ctk.CTkLabel(self, text="Dry-run: No violations found!").pack(pady=20)
            return

        for result in sim_results:
            result_text = (
                f"{result['filename']}:{result['location']['row']}:"
                f"{result['location']['column']} {result['code']}\n"
                f"  {result['message']}"
            )
            ctk.CTkLabel(
                self, text=result_text,
                wraplength=self.winfo_width()-50, justify="left",
                anchor="w"
            ).pack(pady=2, fill="x", padx=5)
            
    def set_scanning(self):
        self.clear()
        self.results_label.configure(text="Scanning...")
