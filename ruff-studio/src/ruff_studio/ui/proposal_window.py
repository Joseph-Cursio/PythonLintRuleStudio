import uuid
import customtkinter as ctk
from tkinter import messagebox
from .. import git_adapter, proposal_manager

class ProposalWindow(ctk.CTkToplevel):
    def __init__(self, master, config_before, config_after, impact_simulation):
        super().__init__(master)
        self.master = master
        self.title("Create Proposal")
        self.geometry("600x500")
        self.config_before = config_before
        self.config_after = config_after
        self.impact_simulation = impact_simulation

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            self, text="Proposal Title:", anchor="w"
        ).grid(row=0, column=0, padx=20, pady=(20, 5), sticky="ew")
        self.title_entry = ctk.CTkEntry(
            self, placeholder_text="e.g., Enable Security Rules"
        )
        self.title_entry.grid(row=1, column=0, padx=20, pady=5, sticky="ew")

        ctk.CTkLabel(
            self, text="Rationale (Why are we making this change?):", anchor="w"
        ).grid(row=2, column=0, padx=20, pady=(10, 5), sticky="ew")
        self.rationale_text = ctk.CTkTextbox(self)
        self.rationale_text.grid(row=3, column=0, padx=20, pady=5, sticky="nsew")

        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=4, column=0, padx=20, pady=20, sticky="ew")

        self.create_btn = ctk.CTkButton(
            self.button_frame, text="Create Proposal Only", command=self.create_only
        )
        self.create_btn.pack(side="left", padx=5)

        self.commit_btn = ctk.CTkButton(
            self.button_frame, text="Apply & Create Git Branch", 
            command=self.create_and_commit
        )
        self.commit_btn.pack(side="left", padx=5)

        self.cancel_btn = ctk.CTkButton(
            self.button_frame, text="Cancel", fg_color="gray", command=self.destroy
        )
        self.cancel_btn.pack(side="right", padx=5)

    def _get_data(self):
        title = self.title_entry.get().strip()
        rationale = self.rationale_text.get("1.0", "end").strip()
        if not title:
            messagebox.showwarning(
                "Warning", "Please provide a title for the proposal."
            )
            return None, None
        return title, rationale

    def create_only(self):
        title, rationale = self._get_data()
        if not title:
            return
        
        proposal_id = proposal_manager.create_proposal(
            self.master.analyzer.conn, title, rationale,
            self.config_before, self.config_after, self.impact_simulation
        )
        if proposal_id:
            messagebox.showinfo(
                "Success", f"Proposal '{title}' created successfully."
            )
            self.destroy()

    def create_and_commit(self):
        title, rationale = self._get_data()
        if not title:
            return

        repo_path = self.master.current_directory
        if not git_adapter.is_repo_clean(repo_path):
            if not messagebox.askyesno(
                "Git Dirty", 
                "Repository has uncommitted changes. Continue anyway?"
            ):
                return

        branch_name = f"ruff-studio/proposal-{uuid.uuid4().hex[:8]}"
        if git_adapter.create_branch(repo_path, branch_name):
            # Apply changes to file
            self.master.apply_changes(show_proposal_window=False)
            
            # Commit
            commit_msg = f"feat: {title}\n\n{rationale}"
            git_adapter.commit_changes(repo_path, commit_msg)
            
            # Save proposal to DB
            proposal_manager.create_proposal(
                self.master.analyzer.conn, title, rationale,
                self.config_before, self.config_after, self.impact_simulation
            )
            
            messagebox.showinfo(
                "Success", 
                f"Changes applied and committed to branch: {branch_name}"
            )
            self.destroy()
        else:
            messagebox.showerror("Error", "Failed to create git branch.")
