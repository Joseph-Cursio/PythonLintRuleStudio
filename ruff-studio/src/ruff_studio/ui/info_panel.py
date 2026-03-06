import customtkinter as ctk


class InfoPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.controller = controller

        # Kept for backward compatibility (tests assert on this label's text).
        self.info_label = ctk.CTkLabel(self, text="Rule Info", font=("", 16, "bold"))
        self.info_label.pack(pady=(10, 4))
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

    def _section_divider(self, title):
        """Render a small-caps section label followed by a 1px divider."""
        ctk.CTkLabel(
            self,
            text=title,
            font=("", 10, "bold"),
            text_color=("gray45", "gray55"),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(10, 1))
        ctk.CTkFrame(self, height=1, fg_color=("gray72", "gray38")).pack(
            fill="x", padx=6, pady=(0, 4)
        )

    def clear(self):
        self._dynamic_labels = []
        for widget in self.winfo_children():
            if widget != self.info_label:
                widget.destroy()

    def set_rule(self, rule):
        self.clear()
        self._parent_canvas.yview_moveto(0)

        code = rule["code"]
        color = self.controller.get_color_for_prefix(code)
        source = "Pylint" if self.controller.is_pylint_rule(code) else "Ruff"
        wrap = self._wrap()

        # Update the persistent title label (tests check this).
        self.info_label.configure(text=f"Rule: {code}", text_color=color)

        # --- Header card: badge + name + source pill ---
        header = ctk.CTkFrame(self, fg_color=("gray88", "gray22"), corner_radius=8)
        header.pack(fill="x", padx=6, pady=(0, 4))
        header.grid_columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(header, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=(10, 4))

        # Rule code in prefix color
        ctk.CTkLabel(
            top_row,
            text=code,
            font=("", 20, "bold"),
            text_color=color,
            anchor="w",
        ).pack(side="left")

        # Source pill (right-aligned)
        pill_color = "#79c0ff" if source == "Ruff" else "#f0883e"
        ctk.CTkLabel(
            top_row,
            text=f"  {source}  ",
            font=("", 10, "bold"),
            text_color=pill_color,
            fg_color=("gray78", "gray30"),
            corner_radius=8,
        ).pack(side="right", padx=(4, 0))

        # Rule name below the badge row
        name_lbl = ctk.CTkLabel(
            header,
            text=rule["name"],
            font=("", 13),
            text_color=("gray20", "gray85"),
            anchor="w",
            justify="left",
            wraplength=wrap - 24,
        )
        name_lbl.pack(fill="x", padx=12, pady=(0, 10))
        self._dynamic_labels.append(name_lbl)

        # --- Summary section ---
        self._section_divider("SUMMARY")

        summary_card = ctk.CTkFrame(
            self, fg_color=("gray92", "gray18"), corner_radius=6
        )
        summary_card.pack(fill="x", padx=6, pady=(0, 4))

        summary_lbl = ctk.CTkLabel(
            summary_card,
            text=rule["summary"],
            wraplength=wrap - 24,
            justify="left",
            anchor="w",
        )
        summary_lbl.pack(padx=12, pady=10, anchor="w")
        self._dynamic_labels.append(summary_lbl)

        # --- Documentation section ---
        self._init_doc_viewer(rule)

    def _init_doc_viewer(self, rule):
        if rule.get("documentation"):
            self._section_divider("DOCUMENTATION")
            self.docs_textbox = ctk.CTkTextbox(self, wrap="word", height=400)
            self.docs_textbox.pack(pady=(0, 5), fill="both", expand=True, padx=6)
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

        txt.tag_config("header", foreground="#2196f3")
        txt.tag_config("keyword", foreground="#ff7b72")
        txt.tag_config("string", foreground="#a5d6ff")

        content = txt.get("1.0", "end")

        for match in re.finditer(r"--- [A-Z ]+ ---", content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            txt.tag_add("header", start, end)

        kw_list = [
            "def", "class", "if", "else", "elif", "return", "import", "from",
            "for", "while", "try", "except", "with", "as", "in", "is", "not",
            "pass", "None", "True", "False",
        ]
        keywords = r"\b(" + "|".join(kw_list) + r")\b"
        for match in re.finditer(keywords, content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            txt.tag_add("keyword", start, end)

        for match in re.finditer(r"(['\"])(?:(?=(\\?))\2.)*?\1", content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            txt.tag_add("string", start, end)

    def update_docs(self, docs):
        # Called after a scrape
        self.clear()
        pass
