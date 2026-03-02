import customtkinter as ctk
from .. import profile_manager

class Toolbar(ctk.CTkFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, **kwargs)
        self.controller = controller
        
        self.select_button = ctk.CTkButton(
            self, text="Select Directory", command=master.select_directory
        )
        self.select_button.pack(side="left", padx=10)
        
        self.directory_label = ctk.CTkLabel(
            self, text="No directory selected"
        )
        self.directory_label.pack(side="left", padx=10)

        self.action_frame = ctk.CTkFrame(self)
        self.action_frame.pack(side="right", padx=10)
        
        self.simulate_button = ctk.CTkButton(
            self.action_frame, text="Simulate Changes", state="disabled",
            command=master.simulate_changes
        )
        self.simulate_button.pack(side="left", padx=5)
        
        self.apply_button = ctk.CTkButton(
            self.action_frame, text="Apply Changes", state="disabled",
            command=master.apply_changes
        )
        self.apply_button.pack(side="left", padx=5)

        self.profile_menu = ctk.CTkOptionMenu(
            self.action_frame,
            values=["Apply a Profile..."] + profile_manager.get_built_in_profiles(),
            command=master.apply_profile
        )
        self.profile_menu.pack(side="left", padx=5)
        self.profile_menu.set("Apply a Profile...")
        self.profile_menu.configure(state="disabled")

        self.compare_profiles_button = ctk.CTkButton(
            self.action_frame, text="Compare Profiles", 
            command=master.open_comparison_window
        )
        self.compare_profiles_button.pack(side="left", padx=5)

        self.view_proposals_button = ctk.CTkButton(
            self.action_frame, text="View Proposals", 
            command=master.open_proposals_dashboard
        )
        self.view_proposals_button.pack(side="left", padx=5)

        self.generate_pre_commit_button = ctk.CTkButton(
            self.action_frame, text="Generate Pre-commit Config", 
            command=master.generate_pre_commit_config_file,
            state="disabled"
        )
        self.generate_pre_commit_button.pack(side="left", padx=5)

        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.pack(side="right", padx=10)

    def set_status(self, text):
        self.status_label.configure(text=text)

    def set_directory(self, text):
        self.directory_label.configure(text=text)
