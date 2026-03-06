import customtkinter as ctk
from .toolbar import Toolbar
from .rules_panel import RulesPanel
from .info_panel import InfoPanel
from .results_panel import ResultsPanel


class RulesView(ctk.CTkFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, **kwargs)
        # master is self.container in App
        # self.master.master is the App instance
        self.app = master.master
        self.controller = controller

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=0)  # Sash
        self.grid_columnconfigure(2, weight=2)
        self.grid_columnconfigure(3, weight=0)  # Sash
        self.grid_columnconfigure(4, weight=3)

        # --- Toolbar ---
        self.toolbar = Toolbar(self.app, self.controller)
        self.toolbar.grid(row=0, column=0, columnspan=5, sticky="ew", padx=10, pady=10)

        # --- Toolbar / content separator ---
        separator = ctk.CTkFrame(self, height=1, fg_color=("gray70", "gray40"))
        separator.grid(row=1, column=0, columnspan=5, sticky="ew", padx=10)

        # --- Panels ---
        self.rules_panel = RulesPanel(self.app, self.controller)
        self.rules_panel.grid(row=2, column=0, sticky="nsew", padx=10, pady=(8, 8))

        self.info_panel = InfoPanel(self.app, self.controller)
        self.info_panel.grid(row=2, column=2, sticky="nsew", padx=10, pady=(8, 8))

        self.results_panel = ResultsPanel(self.app, self.controller)
        self.results_panel.grid(row=2, column=4, sticky="nsew", padx=(0, 10), pady=(8, 8))

        # --- Sashes for resizing ---
        self.sash1 = ctk.CTkFrame(self, width=4, cursor="sb_h_double_arrow")
        self.sash1.grid(row=2, column=1, sticky="ns")
        self.sash1.bind("<Button-1>", lambda e: self.app.start_resize(e, 0))
        self.sash1.bind("<B1-Motion>", self.app.do_resize)

        self.sash2 = ctk.CTkFrame(self, width=4, cursor="sb_h_double_arrow")
        self.sash2.grid(row=2, column=3, sticky="ns")
        self.sash2.bind("<Button-1>", lambda e: self.app.start_resize(e, 2))
        self.sash2.bind("<B1-Motion>", self.app.do_resize)

    def refresh(self):
        self.rules_panel.update_panel()
