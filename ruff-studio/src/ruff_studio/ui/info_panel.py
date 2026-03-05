import customtkinter as ctk


class InfoPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.controller = controller

        self.info_label = ctk.CTkLabel(self, text="Rule Info", font=("", 16, "bold"))
        self.info_label.pack(pady=10)

    def clear(self):
        for widget in self.winfo_children():
            if widget != self.info_label:
                widget.destroy()

    def set_rule(self, rule):
        self.clear()
        self._parent_canvas.yview_moveto(0)
        self.info_label.configure(text=f"Rule: {rule['code']}")

        ctk.CTkLabel(self, text=f"Name: {rule['name']}", wraplength=250).pack(
            pady=5, anchor="w"
        )

        source = "Pylint" if self.controller.is_pylint_rule(rule["code"]) else "Ruff"
        ctk.CTkLabel(
            self,
            text=f"Source: {source} Linter",
            wraplength=250,
            font=("", 12, "italic"),
        ).pack(pady=5, anchor="w")

        ctk.CTkLabel(
            self, text=f"Summary: {rule['summary']}", wraplength=250, justify="left"
        ).pack(pady=5, anchor="w")

        self._init_doc_viewer(rule)

    def _init_doc_viewer(self, rule):
        if rule.get("documentation"):
            self.docs_textbox = ctk.CTkTextbox(self, wrap="word", height=400)
            self.docs_textbox.pack(pady=(10, 5), fill="both", expand=True)
            self.docs_textbox.insert("1.0", rule["documentation"])
            self.docs_textbox.configure(state="disabled")
        elif not self.controller.is_pylint_rule(rule["code"]):
            self.scrape_button = ctk.CTkButton(
                self,
                text="Fetch Documentation Online",
                command=lambda: self.master.fetch_rule_docs(rule),
            )
            self.scrape_button.pack(pady=10)

    def update_docs(self, docs):
        # Called after a scrape
        self.clear()
        # Re-initialize with the updated rule (caller should have updated rule object)
        # This is a bit recursive, simplified for now
        pass
