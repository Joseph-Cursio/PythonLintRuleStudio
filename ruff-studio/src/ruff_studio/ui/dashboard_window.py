import json
import customtkinter as ctk
from tkinter import messagebox
from .. import proposal_manager


class ProposalsView(ctk.CTkFrame):
    def __init__(self, master, controller=None, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.controller = controller or getattr(master, "controller", None)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Left Panel: List ---
        self.list_side = ctk.CTkFrame(self, width=300)
        self.list_side.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.list_side.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.list_side, text="Proposals", font=("", 16, "bold")).grid(
            row=0, column=0, pady=10
        )

        self.list_frame = ctk.CTkScrollableFrame(self.list_side)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # --- Right Panel: Detail ---
        self.detail_frame = ctk.CTkFrame(self)
        self.detail_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.detail_frame.grid_columnconfigure(0, weight=1)
        self.detail_frame.grid_rowconfigure(2, weight=1)

        self.detail_title = ctk.CTkLabel(
            self.detail_frame,
            text="Select a proposal to view details",
            font=("", 16, "bold"),
        )
        self.detail_title.grid(row=0, column=0, padx=20, pady=10, sticky="w")

        self.detail_info = ctk.CTkLabel(self.detail_frame, text="", justify="left")
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

        self.copy_report_btn = ctk.CTkButton(
            self.action_btns,
            text="Copy PR Report",
            fg_color="gray",
            command=self.copy_report,
        )
        self.copy_report_btn.pack(side="right", padx=5)

        self.current_proposal = None
        if self.controller and self.controller.analyzer:
            self.refresh()

    def refresh(self):
        self.load_proposals()

    def load_proposals(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        # Use controller's analyzer if available
        analyzer = self.controller.analyzer if self.controller else self.master.analyzer
        proposals = proposal_manager.get_proposals(analyzer.conn)
        for p in proposals:
            btn = ctk.CTkButton(
                self.list_frame,
                text=f"{p['title']}\n({p['status']})",
                command=lambda p=p: self.show_detail(p),
                anchor="w",
                fg_color="transparent" if p["status"] != "pending" else None,
            )
            btn.pack(fill="x", pady=2)

    def show_detail(self, proposal):
        self.current_proposal = proposal
        self.detail_title.configure(text=proposal["title"])
        branch_text = (
            f" | Branch: {proposal['branch_name']}"
            if proposal.get("branch_name")
            else ""
        )
        info_text = (
            f"Author: {proposal['author']} | "
            f"Status: {proposal['status']} | "
            f"Created: {proposal['created_at']}{branch_text}"
        )
        self.detail_info.configure(text=info_text)

        impact = json.loads(proposal["impact_simulation"])
        violation_count = len(impact) if isinstance(impact, list) else "N/A"
        report = f"RATIONALE:\n{proposal['rationale']}\n\n"
        report += f"IMPACT SIMULATION:\n- Violations found: {violation_count}\n\n"
        report += (
            f"CONFIG CHANGES:\n--- BEFORE ---\n{proposal['config_before']}\n\n"
            f"--- AFTER ---\n{proposal['config_after']}"
        )

        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", report)

        if proposal["status"] == "pending":
            self.approve_btn.pack(side="left", padx=5)
            self.reject_btn.pack(side="left", padx=5)
        else:
            self.approve_btn.pack_forget()
            self.reject_btn.pack_forget()

    def copy_report(self):
        if not self.current_proposal:
            return

        report = proposal_manager.generate_impact_report(
            self.current_proposal["config_before"],
            self.current_proposal["config_after"],
            json.loads(self.current_proposal["impact_simulation"]),
        )
        self.clipboard_clear()
        self.clipboard_append(report)
        messagebox.showinfo("Copied", "PR Impact Report copied to clipboard.")

    def approve(self):
        analyzer = self.controller.analyzer if self.controller else self.master.analyzer
        conn = analyzer.conn
        p_id = self.current_proposal["id"]
        if proposal_manager.update_proposal_status(conn, p_id, "approved"):
            messagebox.showinfo("Approved", "Proposal marked as approved.")
            self.load_proposals()
            updated_proposals = proposal_manager.get_proposals(conn, status="approved")
            if updated_proposals:
                self.show_detail(updated_proposals[0])

    def reject(self):
        analyzer = self.controller.analyzer if self.controller else self.master.analyzer
        conn = analyzer.conn
        p_id = self.current_proposal["id"]
        if proposal_manager.update_proposal_status(conn, p_id, "rejected"):
            messagebox.showinfo("Rejected", "Proposal marked as rejected.")
            self.load_proposals()
            updated_proposals = proposal_manager.get_proposals(conn, status="rejected")
            if updated_proposals:
                self.show_detail(updated_proposals[0])
