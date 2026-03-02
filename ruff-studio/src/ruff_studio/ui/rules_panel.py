import customtkinter as ctk
from .tooltip import Tooltip

class RulesPanel(ctk.CTkFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.controller = controller
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Header ---
        self.header_frame = ctk.CTkFrame(self, height=30, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=5)
        self.header_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(self.header_frame, text="", width=20).grid(row=0, column=0, padx=5)
        ctk.CTkLabel(
            self.header_frame, text="Enabled", anchor="w"
        ).grid(row=0, column=1, padx=(0, 5))

        radio_header_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        radio_header_frame.grid(row=0, column=2)
        for i in range(3):
            radio_header_frame.grid_columnconfigure(i, minsize=35)

        for i, (text, tip) in enumerate(
            [("Sel", "Select"), ("Ign", "Ignore"), ("Def", "Default")]
        ):
            lbl = ctk.CTkLabel(
                radio_header_frame, text=text, anchor="center", width=35
            )
            lbl.grid(row=0, column=i)
            Tooltip(lbl, tip)

        # --- Content ---
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.loading_label = ctk.CTkLabel(self.scroll_frame, text="Rules (Loading...)")
        self.loading_label.pack(pady=10)
        
        self.rule_widgets = {}

    def populate(self, categories):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        self.rule_widgets = {}
        for category_name, category_data in categories:
            # --- Category Header ---
            cat_frame = ctk.CTkFrame(self.scroll_frame)
            cat_frame.pack(fill="x", pady=(5, 1), padx=5)
            cat_frame.grid_columnconfigure(3, weight=1)

            cat_frame.bind(
                "<Button-1>",
                lambda e, cn=category_name: self.master.select_category(cn)
            )

            eff_var = ctk.StringVar()
            toggle_btn = ctk.CTkButton(
                cat_frame, text="▼", width=20,
                command=lambda cn=category_name:
                self.master.toggle_category_rules(cn)
            )
            toggle_btn.grid(row=0, column=0, padx=5, pady=2)

            eff_ind = ctk.CTkCheckBox(
                cat_frame, text="", variable=eff_var,
                onvalue="on", offvalue="off", state="disabled"
            )
            eff_ind.grid(row=0, column=1, padx=(0, 5))

            radio_frame = ctk.CTkFrame(cat_frame, fg_color="transparent")
            radio_frame.grid(row=0, column=2)
            radio_var = ctk.StringVar(value="default")
            
            for i, val in enumerate(["select", "ignore", "default"]):
                ctk.CTkRadioButton(
                    radio_frame, text="", variable=radio_var, value=val,
                    width=35, radiobutton_width=18, radiobutton_height=18,
                    command=lambda v=val, p=category_data['prefix']:
                    self.master.stage_category_change(p, v)
                ).grid(row=0, column=i)

            cat_title = f"{category_name} ({category_data['prefix']})"
            ctk.CTkLabel(
                cat_frame, text=cat_title, anchor="w"
            ).grid(row=0, column=3, sticky="w", padx=10)

            # --- Rules Container ---
            rules_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            rules_container.pack(fill="x", padx=(25, 5))

            self.rule_widgets[category_name] = {
                'prefix': category_data['prefix'],
                'radio_variable': radio_var,
                'effective_state_variable': eff_var,
                'rules_container': rules_container,
                'toggle_button': toggle_btn,
                'category_frame': cat_frame,
                'rules': {},
                'raw_data': category_data, # Keep for rebuilding navigation
                'is_expanded': True # Default state
            }

            for rule in sorted(category_data['rules'], key=lambda r: r['code']):
                r_frame = ctk.CTkFrame(rules_container)
                r_frame.pack(fill="x", pady=1)
                r_frame.grid_columnconfigure(3, weight=1)
                ctk.CTkLabel(r_frame, text="", width=20).grid(row=0, column=0, padx=5)

                r_eff_var = ctk.StringVar()
                ctk.CTkCheckBox(
                    r_frame, text="", variable=r_eff_var,
                    onvalue="on", offvalue="off", state="disabled"
                ).grid(row=0, column=1, padx=(0, 5))

                r_radio_frame = ctk.CTkFrame(r_frame, fg_color="transparent")
                r_radio_frame.grid(row=0, column=2)
                r_radio_var = ctk.StringVar(value="default")
                for i, val in enumerate(["select", "ignore", "default"]):
                    ctk.CTkRadioButton(
                        r_radio_frame, text="", variable=r_radio_var,
                        value=val, width=35,
                        radiobutton_width=18, radiobutton_height=18,
                        command=lambda v=val, rc=rule['code']:
                        self.master.stage_rule_change(rc, v)
                    ).grid(row=0, column=i)

                status_tag = f" (⚠️ {rule['status']})" \
                    if rule['status'] != 'stable' else ""
                r_text = f"{rule['code']}{status_tag}"
                lbl = ctk.CTkLabel(
                    r_frame, text=f"{r_text}: {rule['name']}", anchor="w"
                )
                lbl.grid(row=0, column=3, sticky="w", padx=10)
                if rule['status'] != 'stable':
                    Tooltip(lbl, f"This rule is {rule['status']}.")
                lbl.bind(
                    "<Button-1>",
                    lambda e, r=rule, cn=category_name:
                    self.master.show_rule_info(r, cn)
                )

                self.rule_widgets[category_name]['rules'][rule['code']] = {
                    'effective_state_variable': r_eff_var,
                    'radio_variable': r_radio_var,
                    'frame': r_frame
                }
        self.rebuild_navigable_items()

    def rebuild_navigable_items(self):
        """Builds the list of items reachable via keyboard navigation."""
        self.controller.navigable_items = []
        # Categories are processed in the order they were added to rule_widgets
        for cat_name, cat_widgets in self.rule_widgets.items():
            category_item = {
                'type': 'category', 'name': cat_name, 'data': cat_widgets['raw_data']
            }
            self.controller.navigable_items.append(category_item)
            
            # Only add rules if the category is expanded
            if cat_widgets['is_expanded']:
                sorted_rules = sorted(
                    cat_widgets['raw_data']['rules'], key=lambda r: r['code']
                )
                for rule in sorted_rules:
                    rule_item = {
                        'type': 'rule', 'data': rule, 'category_name': cat_name
                    }
                    self.controller.navigable_items.append(rule_item)
        
        # Re-sync navigable_index to point to the current selected item
        # if it's still there
        if self.controller.selected_item:
            for i, item in enumerate(self.controller.navigable_items):
                if item == self.controller.selected_item:
                    self.controller.navigable_index = i
                    break
            else:
                # If selected item is now hidden, fallback to its category
                # if it's a rule
                if self.controller.selected_item['type'] == 'rule':
                    cat_name = self.controller.selected_item['category_name']
                    for i, item in enumerate(self.controller.navigable_items):
                        if item['type'] == 'category' and item['name'] == cat_name:
                            self.controller.navigable_index = i
                            self.controller.selected_item = item
                            break

    def toggle_category_rules(self, category_name):
        cat_widgets = self.rule_widgets[category_name]
        container = cat_widgets['rules_container']
        toggle_button = cat_widgets['toggle_button']
        
        if cat_widgets['is_expanded']:
            container.pack_forget()
            toggle_button.configure(text="▶")
            cat_widgets['is_expanded'] = False
        else:
            container.pack(fill="x", padx=(25, 5))
            toggle_button.configure(text="▼")
            cat_widgets['is_expanded'] = True
        self.rebuild_navigable_items()

    def update_panel(self):
        if not self.controller.current_directory:
            return
        ruff_cfg, pylint_cfg = self.controller.get_effective_configs()

        for cat_name, cat_widgets in self.rule_widgets.items():
            prefix = cat_widgets['prefix']
            cat_widgets['radio_variable'].set(
                self.controller.staged_changes.get(
                    prefix,
                    self.controller.get_explicit_rule_state(
                        prefix, ruff_cfg, pylint_cfg
                    )
                )
            )

            any_on, all_on = False, True
            for rc, r_widget in cat_widgets['rules'].items():
                r_widget['radio_variable'].set(
                    self.controller.staged_changes.get(
                        rc,
                        self.controller.get_explicit_rule_state(
                            rc, ruff_cfg, pylint_cfg
                        )
                    )
                )
                is_on = self.controller.get_effective_rule_state(rc, prefix)
                r_widget['effective_state_variable'].set(
                    "on" if is_on else "off"
                )
                if is_on:
                    any_on = True
                else:
                    all_on = False

            cat_widgets['effective_state_variable'].set(
                "on" if all_on or any_on else "off"
            )

    def see(self, widget):
        """Scrolls the scroll_frame so that the given widget is visible."""
        if not widget:
            return
        self.scroll_frame._parent_canvas.update_idletasks()
        
        # Absolute Y relative to the scrollable content frame
        y = widget.winfo_rooty() - self.scroll_frame._parent_frame.winfo_rooty()
        h = widget.winfo_height()
        
        c_height = self.scroll_frame._parent_frame.winfo_height()
        v_height = self.scroll_frame._parent_canvas.winfo_height()
        
        if c_height <= v_height:
            return
        
        top, bottom = self.scroll_frame._parent_canvas.yview()
        t_top = y / c_height
        t_bottom = (y + h) / c_height
        
        if t_top < top:
            self.scroll_frame._parent_canvas.yview_moveto(t_top)
        elif t_bottom > bottom:
            self.scroll_frame._parent_canvas.yview_moveto(t_bottom - (bottom - top))
