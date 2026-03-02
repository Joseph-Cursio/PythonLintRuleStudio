import json
import customtkinter as ctk
from tkinter import messagebox
from .. import proposal_manager

class ProposalsDashboard(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.title("Proposals Dashboard")
        self.geometry("1000x600")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Left Panel: List ---
        self.list_frame = ctk.CTkScrollableFrame(self, width=300)
        self.list_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # --- Right Panel: Detail ---
        self.detail_frame = ctk.CTkFrame(self)
        self.detail_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.detail_frame.grid_columnconfigure(0, weight=1)
        self.detail_frame.grid_rowconfigure(2, weight=1)

        self.detail_title = ctk.CTkLabel(
            self.detail_frame, text="Select a proposal to view details", 
            font=("", 16, "bold")
        )
        self.detail_title.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        self.detail_info = ctk.CTkLabel(
            self.detail_frame, text="", justify="left"
        )
        self.detail_info.grid(row=1, column=0, padx=20, pady=5, sticky="w")

        self.detail_text = ctk.CTkTextbox(self.detail_frame)
        self.detail_text.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")

        self.action_btns = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
        self.action_btns.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        self.approve_btn = ctk.CTkButton(
            self.action_btns, text="Approve", command=self.approve
        )
        self.reject_btn = ctk.CTkButton(
            self.action_btns, text="Reject", fg_color="red", command=self.reject
        )
        
        self.load_proposals()

    def load_proposals(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        
        proposals = proposal_manager.get_proposals(self.master.analyzer.conn)
        for p in proposals:
            btn = ctk.CTkButton(
                self.list_frame, 
                text=f"{p['title']}\n({p['status']})",
                command=lambda p=p: self.show_detail(p),
                anchor="w",
                fg_color="transparent" if p['status'] != 'pending' else None
            )
            btn.pack(fill="x", pady=2)

    def show_detail(self, proposal):
        self.current_proposal = proposal
        self.detail_title.configure(text=proposal['title'])
        info_text = (
            f"Author: {proposal['author']} | "
            f"Status: {proposal['status']} | "
            f"Created: {proposal['created_at']}"
        )
        self.detail_info.configure(text=info_text)
        
        impact = json.loads(proposal['impact_simulation'])
        violation_count = len(impact) if isinstance(impact, list) else 'N/A'
        report = f"RATIONALE:\n{proposal['rationale']}\n\n"
        report += f"IMPACT SIMULATION:\n- Violations found: {violation_count}\n\n"
        report += (
            f"CONFIG CHANGES:\n--- BEFORE ---\n{proposal['config_before']}\n\n"
            f"--- AFTER ---\n{proposal['config_after']}"
        )
        
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", report)
        
        if proposal['status'] == 'pending':
            self.approve_btn.pack(side="left", padx=5)
            self.reject_btn.pack(side="left", padx=5)
        else:
            self.approve_btn.pack_forget()
            self.reject_btn.pack_forget()

    def approve(self):
        conn = self.master.analyzer.conn
        p_id = self.current_proposal['id']
        if proposal_manager.update_proposal_status(conn, p_id, "approved"):
            messagebox.showinfo("Approved", "Proposal marked as approved.")
            self.load_proposals()
            # Refresh detail view with updated data
            updated_proposals = proposal_manager.get_proposals(conn, status="approved")
            if updated_proposals:
                self.show_detail(updated_proposals[0])

    def reject(self):
        conn = self.master.analyzer.conn
        p_id = self.current_proposal['id']
        if proposal_manager.update_proposal_status(conn, p_id, "rejected"):
            messagebox.showinfo("Rejected", "Proposal marked as rejected.")
            self.load_proposals()
            updated_proposals = proposal_manager.get_proposals(conn, status="rejected")
            if updated_proposals:
                self.show_detail(updated_proposals[0])
