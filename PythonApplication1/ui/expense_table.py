"""Custom expense table with row actions and design-system styling."""

import tkinter as tk
from tkinter import ttk

from ui.theme import THEME, STATUS_COLORS, create_link_button, format_status
from utils import format_money


class ExpenseDataTable(tk.Frame):
    """Scrollable expense table with readable rows and per-row actions."""

    COLUMNS = [
        ("id", "ID", 44, "center"),
        ("date", "Ngày", 90, "w"),
        ("project", "Dự án", 150, "w"),
        ("category", "Loại CP", 136, "w"),
        ("desc", "Mô tả", 320, "w"),
        ("amount", "Số tiền", 126, "e"),
        ("status", "Trạng thái", 100, "center"),
        ("docs", "CT", 34, "center"),
        ("files", "File", 34, "center"),
        ("actions", "Thao tác", 184, "e"),
    ]

    def __init__(self, parent, expenses, callbacks):
        super().__init__(parent, bg=THEME["panel"])
        self.callbacks = callbacks

        self.header_frame = tk.Frame(self, bg=THEME["panel"])
        self.header_frame.pack(fill="x")

        body_wrap = tk.Frame(self, bg=THEME["panel"])
        body_wrap.pack(fill="x", expand=False)

        self.canvas = tk.Canvas(body_wrap, bg=THEME["panel"], highlightthickness=0)
        visible_rows = max(1, min(len(expenses or []), 9))
        self.canvas.configure(height=visible_rows * 50 + (38 if not expenses else 0))
        v_scroll = ttk.Scrollbar(body_wrap, orient="vertical", command=self.canvas.yview)
        h_scroll = ttk.Scrollbar(body_wrap, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.inner = tk.Frame(self.canvas, bg=THEME["panel"])
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self.canvas_window, width=max(e.width, self.inner.winfo_reqwidth())),
        )

        self.canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        body_wrap.rowconfigure(0, weight=1)
        body_wrap.columnconfigure(0, weight=1)

        def _wheel(event):
            if self.canvas.winfo_containing(event.x_root, event.y_root):
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"
            return None

        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", _wheel))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

        self._build_header()
        if not expenses:
            tk.Label(
                self.inner,
                text="Chưa có chi phí.",
                font=("Segoe UI", 11),
                fg=THEME["muted"],
                bg=THEME["panel"],
                pady=32,
            ).grid(row=0, column=0, columnspan=len(self.COLUMNS), sticky="ew")
        else:
            for idx, exp in enumerate(expenses):
                self._build_row(idx, exp)
        self.after_idle(self._reset_scroll_position)

    def _reset_scroll_position(self):
        self.canvas.yview_moveto(0)
        self.canvas.xview_moveto(0)

    def _build_header(self):
        hdr = tk.Frame(self.header_frame, bg=THEME["panel"], height=38)
        hdr.pack(fill="x")
        for col, (_key, label, width, anchor) in enumerate(self.COLUMNS):
            tk.Label(
                hdr,
                text=label,
                width=int(width / 7),
                anchor=anchor,
                font=("Segoe UI", 10, "bold"),
                fg=THEME["muted"],
                bg=THEME["panel"],
                padx=8,
                pady=9,
            ).grid(row=0, column=col, sticky="nsew")
            hdr.grid_columnconfigure(col, minsize=width)
        tk.Frame(self.header_frame, bg=THEME["line"], height=1).pack(fill="x")

    def _build_row(self, row_idx, exp):
        expense_id = exp[0]
        status_key = exp[6] if len(exp) > 6 else "pending"
        bg = THEME["panel"]
        row = tk.Frame(self.inner, bg=bg)
        row.grid(row=row_idx * 2, column=0, columnspan=len(self.COLUMNS), sticky="ew")
        tk.Frame(self.inner, bg=THEME["line"], height=1).grid(
            row=row_idx * 2 + 1, column=0, columnspan=len(self.COLUMNS), sticky="ew"
        )

        def open_detail(_event=None):
            callback = self.callbacks.get("open")
            if callback:
                callback(expense_id)
            return "break"

        values = [
            str(expense_id),
            str(exp[1] or ""),
            exp[2] or "",
            exp[3] or "",
            exp[4] or "",
            f"{format_money(exp[5])} đ" if isinstance(exp[5], (int, float)) else str(exp[5]),
            None,
            str(exp[7] if len(exp) > 7 else 0),
            str(exp[8] if len(exp) > 8 else 0),
            None,
        ]

        for col, (key, _label, width, anchor) in enumerate(self.COLUMNS):
            row.grid_columnconfigure(col, minsize=width)
            if key == "status":
                st_bg, st_fg = STATUS_COLORS.get(status_key, (THEME["line"], THEME["text"]))
                cell = tk.Frame(row, bg=bg)
                cell.grid(row=0, column=col, sticky="nsew", padx=4, pady=8)
                badge = tk.Label(
                    cell,
                    text=format_status(status_key),
                    font=("Segoe UI", 9),
                    fg=st_fg,
                    bg=st_bg,
                    padx=10,
                    pady=5,
                )
                badge.pack()
                cell.bind("<Double-Button-1>", open_detail)
                badge.bind("<Double-Button-1>", open_detail)
            elif key == "actions":
                actions = tk.Frame(row, bg=bg)
                actions.grid(row=0, column=col, sticky="e", padx=8, pady=8)
                cb = self.callbacks
                links = [
                    ("Sửa", lambda: cb["edit"](expense_id)),
                    ("Ghi", lambda: cb["post"](expense_id)),
                    ("Bỏ", lambda: cb["unpost"](expense_id)),
                    ("CT", lambda: cb["view_docs"](expense_id)),
                    ("Xóa", lambda: cb["delete"](expense_id)),
                ]
                for i, (label, cmd) in enumerate(links):
                    if i:
                        tk.Label(actions, text="·", fg=THEME["muted"], bg=bg).pack(side="left")
                    create_link_button(actions, label, cmd, bg=bg).pack(side="left", padx=3)
            else:
                font = ("Segoe UI", 10, "bold") if key == "amount" else ("Segoe UI", 10)
                fg = THEME["primary"] if key == "amount" else THEME["text"]
                if key in {"docs", "files", "id"}:
                    fg = THEME["muted"]
                cell = tk.Label(
                    row,
                    text=values[col],
                    anchor=anchor,
                    font=font,
                    fg=fg,
                    bg=bg,
                    padx=8,
                    pady=12,
                    cursor="hand2",
                    wraplength=max(width - 14, 40),
                )
                cell.grid(row=0, column=col, sticky="nsew")
                cell.bind("<Double-Button-1>", open_detail)

        row.bind("<Enter>", lambda _e, r=row: self._set_row_bg(r, THEME["row_hover"]))
        row.bind("<Leave>", lambda _e, r=row, b=bg: self._set_row_bg(r, b))
        row.bind("<Double-Button-1>", open_detail)

    def _set_row_bg(self, row, bg):
        row.configure(bg=bg)
        for child in row.winfo_children():
            try:
                child.configure(bg=bg)
            except tk.TclError:
                pass
