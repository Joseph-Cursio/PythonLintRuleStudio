import queue
import copy
from unittest.mock import MagicMock
import customtkinter as ctk
from tkinter import filedialog, messagebox
from . import ruff_adapter, config_manager, ci_integration, profile_manager
from .controller import StudioController
from .ui.proposal_window import ProposalWindow
from .ui.sidebar import Sidebar
from .ui.rules_view import RulesView
from .ui.analytics_window import AnalyticsView
from .ui.dashboard_window import ProposalsView
from .ui.comparison_window import ProfileComparisonWindow


class App(ctk.CTk):
    def __init__(self, headless=False):
        self.controller = StudioController()
        self.headless = headless
        if not headless:
            super().__init__()
            self.title("Ruff Studio")
            self.geometry("1400x850")
            self._init_ui()
        else:
            self.tk = MagicMock()

        self.rule_widgets = {}
        self.selected_rule_frame = None
        self.selected_category_frame = None

        if not headless:
            self.controller.run_in_thread(
                self.controller.discover_rules_worker, "discover_rules"
            )
            self.process_queue()

    # --- Properties for backward compatibility and convenience ---
    @property
    def rules_panel(self):
        return self.rules_view.rules_panel

    @property
    def info_panel(self):
        return self.rules_view.info_panel

    @property
    def results_panel(self):
        return self.rules_view.results_panel

    @property
    def toolbar(self):
        return self.rules_view.toolbar

    # (Keep existing properties that proxy to controller/toolbar)
    @property
    def analyzer(self):
        return self.controller.analyzer

    @property
    def current_directory(self):
        return self.controller.current_directory

    @property
    def pyproject_path(self):
        return self.controller.pyproject_path

    @property
    def pyproject_data(self):
        return self.controller.pyproject_data

    @property
    def staged_changes(self):
        return self.controller.staged_changes

    @property
    def select_button(self):
        return self.toolbar.select_button

    @property
    def apply_button(self):
        return self.toolbar.apply_button

    @property
    def simulate_button(self):
        return self.toolbar.simulate_button

    @property
    def profile_menu(self):
        return self.toolbar.profile_menu

    @property
    def generate_pre_commit_button(self):
        return self.sidebar.generate_pre_commit_button

    @property
    def status_label(self):
        return self.toolbar.status_label

    @property
    def results_label(self):
        return self.results_panel.results_label

    @property
    def rules_frame(self):
        return self.rules_panel.scroll_frame

    @property
    def top_frame(self):
        return self.toolbar

    @property
    def action_frame(self):
        return self.toolbar.action_frame

    def run_in_thread(self, worker, command_name, *args):
        self.toolbar.select_button.configure(state="disabled")
        self.toolbar.set_status("Running...")
        self.controller.run_in_thread(worker, command_name, *args)

    def _init_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Main Content Area ---
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        # Initialize Views
        self.rules_view = RulesView(self.container, self.controller)
        self.analytics_view = AnalyticsView(self.container, self.controller)
        self.proposals_view = ProposalsView(self.container, self.controller)

        self.views = {
            "rules": self.rules_view,
            "analytics": self.analytics_view,
            "proposals": self.proposals_view,
        }

        # --- Sidebar ---
        self.sidebar = Sidebar(
            self,
            on_switch_view=self.switch_view,
            on_compare_profiles=self.open_comparison_window,
            on_generate_pre_commit=self.generate_pre_commit_config_file,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # Sashes logic (moved to RulesView but needs methods here)
        self.resize_start_x = 0
        self.resize_start_col = 0

        self.bind("<Up>", self.navigate_items)
        self.bind("<Down>", self.navigate_items)

        self.switch_view("rules")

    def switch_view(self, view_name):
        for name, view in self.views.items():
            if name == view_name:
                view.grid(row=0, column=0, sticky="nsew")
                if hasattr(view, "refresh"):
                    view.refresh()
            else:
                view.grid_forget()

    def start_resize(self, event, col):
        self.resize_start_x = event.x_root
        self.resize_start_col = col

    def do_resize(self, event):
        delta = event.x_root - self.resize_start_x
        # We need to configure the grid of the RulesView, not self
        rv = self.rules_view
        weight0 = rv.grid_columnconfigure(0)["weight"]
        weight2 = rv.grid_columnconfigure(2)["weight"]
        weight4 = rv.grid_columnconfigure(4)["weight"]

        if self.resize_start_col == 0:
            new_weight0 = max(1, weight0 + delta)
            new_weight2 = max(1, weight2 - delta)
            rv.grid_columnconfigure(0, weight=new_weight0)
            rv.grid_columnconfigure(2, weight=new_weight2)
        else:  # col == 2
            new_weight2 = max(1, weight2 + delta)
            new_weight4 = max(1, weight4 - delta)
            rv.grid_columnconfigure(2, weight=new_weight2)
            rv.grid_columnconfigure(4, weight=new_weight4)
        self.resize_start_x = event.x_root

    def process_queue(self):
        try:
            while True:
                command, data = self.controller.queue.get_nowait()
                if command == "error":
                    messagebox.showerror("Error", f"Error: {data}")
                elif command == "discover_rules":
                    self.controller.all_rules = data
                    self.rules_panel.populate(data.items())
                    self.rule_widgets = self.rules_panel.rule_widgets
                elif command == "run_full_scan":
                    self.controller.base_scan_results = data
                    self.results_panel.set_results(data)
                elif command == "run_simulation":
                    self.results_panel.set_simulation_results(data)
                elif command == "fetch_docs":
                    rule, docs = data
                    rule["documentation"] = docs
                    self.info_panel.set_rule(rule)

                self.toolbar.select_button.configure(state="normal")
                self.toolbar.set_status("")
                self.controller.queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    def select_directory(self, directory=None):
        if not directory:
            directory = filedialog.askdirectory()
        if directory:
            self.controller.set_directory(directory)
            self.toolbar.set_directory(directory)
            self.results_panel.set_scanning()
            self.controller.run_in_thread(
                self.controller.run_full_scan_worker, "run_full_scan", directory
            )
            self.update_rules_panel()
            self.toolbar.profile_menu.configure(state="normal")
            self.sidebar.generate_pre_commit_button.configure(state="normal")

    def update_rules_panel(self):
        self.rules_panel.update_panel()

    def update_results_panel(self, violations):
        self.results_panel.set_results(violations)

    def populate_rules_initial(self):
        self.rules_panel.populate(self.controller.all_rules.items())
        self.rule_widgets = self.rules_panel.rule_widgets

    def stage_rule_change(self, rule_code, state):
        self.controller.staged_changes[rule_code] = state
        self.toolbar.simulate_button.configure(state="normal")
        self.toolbar.apply_button.configure(state="normal")
        self.update_rules_panel()

    def stage_category_change(self, prefix, state):
        self.controller.staged_changes[prefix] = state
        self.toolbar.simulate_button.configure(state="normal")
        self.toolbar.apply_button.configure(state="normal")
        for category_data in self.controller.all_rules.values():
            if category_data["prefix"] == prefix:
                for rule in category_data["rules"]:
                    rc = rule["code"]
                    if rc in self.controller.staged_changes:
                        del self.controller.staged_changes[rc]
                break
        self.update_rules_panel()

    def toggle_category_rules(self, category_name):
        self.rules_panel.toggle_category_rules(category_name)

    def simulate_changes(self):
        ruff_config, _ = self.controller.get_effective_configs()
        self.toolbar.set_status("Simulating...")
        self.controller.run_in_thread(
            self._run_simulation_worker, "run_simulation", ruff_config
        )

    def _run_simulation_worker(self, command, ruff_config):
        try:
            results = ruff_adapter.run_scan_with_config(
                self.controller.current_directory, ruff_config
            )
            self.controller.queue.put((command, results))
        except Exception as e:
            self.controller.queue.put(("error", str(e)))

    def apply_profile(self, profile_name):
        if profile_name == "Apply a Profile...":
            return
        try:
            profile_data = profile_manager.load_profile(profile_name)
            rules_all = profile_data.get("profile", {}).get("rules", {})
            profile_ruff_config = rules_all.get("ruff", {})
            self.controller.staged_changes = {}
            if profile_ruff_config:
                dummy_ruff_config = {
                    "select": profile_ruff_config.get("select", []),
                    "ignore": profile_ruff_config.get("ignore", []),
                }
                profile_ruff_rules = self.controller._get_ruff_rules_from_config(
                    dummy_ruff_config
                )
                for cat_name, cat_widgets in self.rules_panel.rule_widgets.items():
                    if cat_name.startswith("Pylint:"):
                        continue
                    for rule_code in cat_widgets["rules"].keys():
                        if rule_code in profile_ruff_rules:
                            self.controller.staged_changes[rule_code] = "select"
                        else:
                            self.controller.staged_changes[rule_code] = "ignore"
            self.update_rules_panel()
            self.toolbar.simulate_button.configure(state="normal")
            self.toolbar.apply_button.configure(state="normal")
            messagebox.showinfo("Profile Applied", f"Profile '{profile_name}' staged.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply profile: {e}")
        finally:
            self.toolbar.profile_menu.set("Apply a Profile...")

    def apply_changes(self, show_proposal_window=True):
        if not self.controller.pyproject_data or not self.controller.pyproject_path:
            return
        ruff_cfg, pylint_cfg = self.controller.get_effective_configs()
        config_before = config_manager.read_pyproject_text(
            self.controller.pyproject_path
        )
        after_data = copy.deepcopy(self.controller.pyproject_data)
        config_manager.update_ruff_config(after_data, ruff_cfg)
        config_manager.update_pylint_config(after_data, pylint_cfg)
        config_after = config_manager.get_pyproject_text(after_data)
        if show_proposal_window:
            impact = ruff_adapter.run_scan_with_config(
                self.controller.current_directory, ruff_cfg
            )
            ProposalWindow(self, config_before, config_after, impact)
            return
        config_manager.update_ruff_config(self.controller.pyproject_data, ruff_cfg)
        config_manager.update_pylint_config(self.controller.pyproject_data, pylint_cfg)
        config_manager.write_pyproject(
            self.controller.pyproject_path, self.controller.pyproject_data
        )
        self.controller.staged_changes = {}
        self.toolbar.simulate_button.configure(state="disabled")
        self.toolbar.apply_button.configure(state="disabled")
        self.update_rules_panel()
        self.controller.run_in_thread(
            self.controller.run_full_scan_worker,
            "run_full_scan",
            self.controller.current_directory,
        )

    def open_comparison_window(self):
        ProfileComparisonWindow(self)

    def open_proposals_dashboard(self):
        self.switch_view("proposals")

    def open_analytics(self):
        self.switch_view("analytics")

    def generate_pre_commit_config_file(self):
        try:
            ruff_version = ruff_adapter.get_ruff_version()
            config_content = ci_integration.generate_pre_commit_config(ruff_version)
            filepath = filedialog.asksaveasfilename(
                initialdir=self.controller.current_directory,
                initialfile=".pre-commit-config.yaml",
                defaultextension=".yaml",
                filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
            )
            if filepath:
                with open(filepath, "w") as f:
                    f.write(config_content)
                messagebox.showinfo("Success", f"Saved to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")

    def navigate_items(self, event):
        if not self.controller.navigable_items:
            return
        if event.keysym == "Up":
            self.controller.navigable_index = max(
                0, self.controller.navigable_index - 1
            )
        elif event.keysym == "Down":
            self.controller.navigable_index = min(
                len(self.controller.navigable_items) - 1,
                self.controller.navigable_index + 1,
            )
        item = self.controller.navigable_items[self.controller.navigable_index]
        if item["type"] == "rule":
            self.show_rule_info(item["data"], item["category_name"])
        else:
            self.select_category(item["name"])

    def select_category(self, category_name):
        for i, item in enumerate(self.controller.navigable_items):
            if item["type"] == "category" and item["name"] == category_name:
                self.controller.selected_item = item
                self.controller.navigable_index = i
                break
        if self.selected_rule_frame:
            self.selected_rule_frame.configure(fg_color="transparent")
        if self.selected_category_frame:
            self.selected_category_frame.configure(fg_color="transparent")
        if category_name in self.rules_panel.rule_widgets:
            self.selected_category_frame = self.rules_panel.rule_widgets[category_name][
                "category_frame"
            ]
            self.selected_category_frame.configure(fg_color="lightblue")
            self.rules_panel.see(self.selected_category_frame)
        self.info_panel.clear()

    def show_rule_info(self, rule, category_name=None):
        for i, item in enumerate(self.controller.navigable_items):
            if item["type"] == "rule" and item["data"] == rule:
                self.controller.selected_item = item
                self.controller.navigable_index = i
                break
        if self.selected_rule_frame:
            self.selected_rule_frame.configure(fg_color="transparent")
        if self.selected_category_frame:
            self.selected_category_frame.configure(fg_color="transparent")
        rule_code = rule["code"]
        cat_name = category_name or self.controller.selected_item.get("category_name")
        if (
            cat_name in self.rules_panel.rule_widgets
            and rule_code in self.rules_panel.rule_widgets[cat_name]["rules"]
        ):
            self.selected_rule_frame = self.rules_panel.rule_widgets[cat_name]["rules"][
                rule_code
            ]["frame"]
            self.selected_rule_frame.configure(fg_color="lightblue")
            self.rules_panel.see(self.selected_rule_frame)
        self.info_panel.set_rule(rule)

    def fetch_rule_docs(self, rule):
        self.toolbar.set_status("Fetching Docs...")
        self.controller.run_in_thread(self._fetch_docs_worker, "fetch_docs", rule)

    def _fetch_docs_worker(self, command, rule):
        try:
            docs = ruff_adapter.scrape_rule_documentation(rule["code"])
            self.controller.queue.put((command, (rule, docs)))
        except Exception as e:
            self.controller.queue.put(("error", str(e)))


if __name__ == "__main__":
    import sys

    app = App()
    if len(sys.argv) > 1:
        if sys.argv[1] != "--headless":
            app.select_directory(sys.argv[1])
    app.mainloop()
