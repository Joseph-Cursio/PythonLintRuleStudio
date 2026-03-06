import customtkinter as ctk


class InfoPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.controller = controller

        self.info_label = ctk.CTkLabel(self, text="Rule Info", font=("", 16, "bold"))
        self.info_label.pack(pady=10)
        self._dynamic_labels = []
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        new_wrap = max(100, event.width - 30)
        for lbl in self._dynamic_labels:
            try:
                lbl.configure(wraplength=new_wrap)
            except Exception:
                pass

    def _wrap(self):
        """Current wraplength based on panel width, with a safe fallback."""
        w = self.winfo_width()
        return max(100, w - 30) if w > 1 else 250

    def clear(self):
        self._dynamic_labels = []
        for widget in self.winfo_children():
            if widget != self.info_label:
                widget.destroy()

    def set_rule(self, rule):
        self.clear()
        self._parent_canvas.yview_moveto(0)
        self.info_label.configure(text=f"Rule: {rule['code']}")

        wrap = self._wrap()

        name_lbl = ctk.CTkLabel(self, text=f"Name: {rule['name']}", wraplength=wrap, anchor="w")
        name_lbl.pack(pady=5, anchor="w")
        self._dynamic_labels.append(name_lbl)

        source = "Pylint" if self.controller.is_pylint_rule(rule["code"]) else "Ruff"
        source_lbl = ctk.CTkLabel(
            self,
            text=f"Source: {source} Linter",
            wraplength=wrap,
            font=("", 12, "italic"),
        )
        source_lbl.pack(pady=5, anchor="w")
        self._dynamic_labels.append(source_lbl)

        summary_lbl = ctk.CTkLabel(
            self, text=f"Summary: {rule['summary']}", wraplength=wrap, justify="left"
        )
        summary_lbl.pack(pady=5, anchor="w")
        self._dynamic_labels.append(summary_lbl)

        self._init_doc_viewer(rule)

    def _init_doc_viewer(self, rule):
        if rule.get("documentation"):
            self.docs_textbox = ctk.CTkTextbox(self, wrap="word", height=400)
            self.docs_textbox.pack(pady=(10, 5), fill="both", expand=True)
            self.docs_textbox.insert("1.0", rule["documentation"])
            self._apply_syntax_highlighting()
            self.docs_textbox.configure(state="disabled")
        elif not self.controller.is_pylint_rule(rule["code"]):
            self.scrape_button = ctk.CTkButton(
                self,
                text="Fetch Documentation Online",
                command=lambda: self.master.fetch_rule_docs(rule),
            )
            self.scrape_button.pack(pady=10)

    def _apply_syntax_highlighting(self):
        """Applies basic color tagging to the documentation text."""
        import re

        txt = self.docs_textbox

        # Configure tags
        txt.tag_config("header", foreground="#2196f3")
        txt.tag_config("keyword", foreground="#ff7b72")  # Reddish
        txt.tag_config("builtin", foreground="#79c0ff")  # Blue
        txt.tag_config("string", foreground="#a5d6ff")  # Light Blue

        content = txt.get("1.0", "end")

        # 1. Highlight Headers (--- WHAT IT DOES ---)
        for match in re.finditer(r"--- [A-Z ]+ ---", content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            txt.tag_add("header", start, end)

        # 2. Keywords
        kw_list = [
            "def",
            "class",
            "if",
            "else",
            "elif",
            "return",
            "import",
            "from",
            "for",
            "while",
            "try",
            "except",
            "with",
            "as",
            "in",
            "is",
            "not",
            "pass",
            "None",
            "True",
            "False",
        ]
        keywords = r"\b(" + "|".join(kw_list) + r")\b"
        for match in re.finditer(keywords, content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            txt.tag_add("keyword", start, end)

        # 3. Strings
        for match in re.finditer(r"(['\"])(?:(?=(\\?))\2.)*?\1", content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            txt.tag_add("string", start, end)

    def update_docs(self, docs):
        # Called after a scrape
        self.clear()
        # Re-initialize with the updated rule (caller should have updated rule object)
        # This is a bit recursive, simplified for now
        pass
