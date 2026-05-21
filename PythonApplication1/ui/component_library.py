"""
COMPONENT LIBRARY - Tkinter components theo design system FasTrack ERP
"""

import tkinter as tk
from tkinter import ttk
from ui.theme import (
    SIDEBAR_BG, SIDEBAR_SECTION, SIDEBAR_ITEM, SIDEBAR_ACTIVE, SIDEBAR_ACTIVE_BG, SIDEBAR_HOVER_BG,
    PAGE_BG, PANEL_BG, PANEL_BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_BLUE, ACCENT_GREEN, ACCENT_AMBER, ACCENT_RED,
    PILL_PENDING_BG, PILL_PENDING_FG, PILL_DONE_BG, PILL_DONE_FG, PILL_PROC_BG, PILL_PROC_FG,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_SECTION,
    PADDING_LARGE, PADDING_MEDIUM, PADDING_SMALL, BORDER_RADIUS,
)


class Card(tk.Frame):
    """Card component: panel với border nhẹ"""
    def __init__(self, parent, **kwargs):
        bg = kwargs.pop('bg', PANEL_BG)
        super().__init__(
            parent,
            bg=bg,
            highlightbackground=PANEL_BORDER,
            highlightthickness=1,
            **kwargs
        )


class Button(tk.Label):
    """Button component: label with hover effect"""
    def __init__(self, parent, text="", command=None, variant="primary", **kwargs):
        # Định nghĩa style theo variant
        if variant == "primary":
            bg, fg, hover_bg = ACCENT_BLUE, "white", ACCENT_BLUE
            active_fg = "white"
        elif variant == "secondary":
            bg, fg, hover_bg = PANEL_BG, TEXT_SECONDARY, "#EEEFF2"
            active_fg = TEXT_PRIMARY
        elif variant == "danger":
            bg, fg, hover_bg = ACCENT_RED, "white", ACCENT_RED
            active_fg = "white"
        elif variant == "success":
            bg, fg, hover_bg = ACCENT_GREEN, "white", ACCENT_GREEN
            active_fg = "white"
        else:  # neutral
            bg, fg, hover_bg = PAGE_BG, TEXT_MUTED, "#E8ECEF"
            active_fg = TEXT_SECONDARY

        font = kwargs.pop('font', FONT_BODY)
        padx = kwargs.pop('padx', PADDING_MEDIUM)
        pady = kwargs.pop('pady', 6)

        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=font,
            cursor="hand2",
            padx=padx,
            pady=pady,
            relief="flat",
            **kwargs
        )

        self._command = command
        self._bg_normal = bg
        self._fg_normal = fg
        self._bg_hover = hover_bg
        self._fg_active = active_fg

        self.bind("<Button-1>", lambda e: self._on_click())
        self.bind("<Enter>", lambda e: self._on_hover())
        self.bind("<Leave>", lambda e: self._on_leave())

    def _on_click(self):
        if self._command:
            self._command()

    def _on_hover(self):
        self.configure(bg=self._bg_hover, fg=self._fg_active)

    def _on_leave(self):
        self.configure(bg=self._bg_normal, fg=self._fg_normal)


class Pill(tk.Label):
    """Pill/badge component"""
    def __init__(self, parent, text="", status="done", **kwargs):
        status_colors = {
            "pending": (PILL_PENDING_BG, PILL_PENDING_FG),
            "done": (PILL_DONE_BG, PILL_DONE_FG),
            "processing": (PILL_PROC_BG, PILL_PROC_FG),
        }
        bg, fg = status_colors.get(status, (PANEL_BG, TEXT_MUTED))

        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=FONT_SMALL,
            padx=8,
            pady=2,
            relief="flat",
            **kwargs
        )


class Alert(tk.Frame):
    """Alert/notification row"""
    def __init__(self, parent, severity="info", title="", message="", **kwargs):
        super().__init__(parent, bg=PANEL_BG, **kwargs)

        # Dot color
        severity_colors = {
            "error": ACCENT_RED,
            "warning": ACCENT_AMBER,
            "success": ACCENT_GREEN,
            "info": ACCENT_BLUE,
        }
        dot_color = severity_colors.get(severity, ACCENT_BLUE)

        # Dot
        dot = tk.Label(self, text="●", fg=dot_color, bg=PANEL_BG, font=("Arial", 8))
        dot.pack(side="left", padx=(PADDING_MEDIUM, PADDING_SMALL), pady=PADDING_MEDIUM)

        # Content
        content = tk.Frame(self, bg=PANEL_BG)
        content.pack(side="left", fill="both", expand=True, pady=PADDING_MEDIUM)

        tk.Label(
            content, text=title, bg=PANEL_BG, fg=TEXT_PRIMARY,
            font=FONT_BODY, anchor="w", justify="left"
        ).pack(fill="x", anchor="w")

        tk.Label(
            content, text=message, bg=PANEL_BG, fg=TEXT_MUTED,
            font=FONT_SMALL, anchor="w", justify="left"
        ).pack(fill="x", anchor="w", pady=(2, 0))


class KPICard(tk.Frame):
    """KPI Card: value + label + trend"""
    def __init__(self, parent, label="", value="", unit="", trend=None, trend_color=None, **kwargs):
        super().__init__(
            parent,
            bg=PANEL_BG,
            highlightbackground=PANEL_BORDER,
            highlightthickness=1,
            **kwargs
        )

        # Label (ALL CAPS)
        tk.Label(
            self,
            text=label.upper(),
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=FONT_SECTION,
            anchor="w"
        ).pack(fill="x", padx=PADDING_LARGE, pady=(PADDING_LARGE, PADDING_SMALL))

        # Value + Unit
        value_frame = tk.Frame(self, bg=PANEL_BG)
        value_frame.pack(fill="x", padx=PADDING_LARGE)

        tk.Label(
            value_frame,
            text=str(value),
            bg=PANEL_BG,
            fg=trend_color or ACCENT_BLUE,
            font=("Segoe UI", 20, "bold"),
            anchor="w"
        ).pack(side="left", anchor="w")

        if unit:
            tk.Label(
                value_frame,
                text=f" {unit}",
                bg=PANEL_BG,
                fg=TEXT_MUTED,
                font=FONT_BODY,
                anchor="w"
            ).pack(side="left", anchor="w", padx=(PADDING_SMALL, 0))

        # Trend
        if trend is not None:
            trend_frame = tk.Frame(self, bg=PANEL_BG)
            trend_frame.pack(fill="x", padx=PADDING_LARGE, pady=(PADDING_SMALL, PADDING_LARGE))

            arrow = "↑" if trend > 0 else "↓" if trend < 0 else "→"
            trend_fg = ACCENT_GREEN if trend > 0 else ACCENT_RED if trend < 0 else TEXT_MUTED

            tk.Label(
                trend_frame,
                text=f"{arrow} {abs(trend):.1f}% từ tháng trước",
                bg=PANEL_BG,
                fg=trend_fg,
                font=FONT_SMALL,
                anchor="w"
            ).pack(fill="x", anchor="w")


class ProgressBar(tk.Canvas):
    """Custom progress bar"""
    def __init__(self, parent, value=0, max_value=100, height=6, **kwargs):
        super().__init__(
            parent,
            height=height,
            bg=PAGE_BG,
            highlightthickness=0,
            bd=0,
            **kwargs
        )
        self.max_value = max_value
        self.value = value
        self._draw()

    def set_value(self, value):
        self.value = min(value, self.max_value)
        self._draw()

    def _draw(self):
        self.delete("all")
        width = self.winfo_width()
        if width > 1:
            progress_width = (self.value / self.max_value) * width
            self.create_rectangle(0, 0, progress_width, self.winfo_height(), fill=ACCENT_BLUE, outline="")


class StatusLabel(tk.Label):
    """Status label with color"""
    def __init__(self, parent, text="", status="info", **kwargs):
        status_colors = {
            "success": (ACCENT_GREEN, "white"),
            "error": (ACCENT_RED, "white"),
            "warning": (ACCENT_AMBER, "white"),
            "info": (ACCENT_BLUE, "white"),
            "pending": (ACCENT_AMBER, "white"),
        }
        bg, fg = status_colors.get(status, (PANEL_BG, TEXT_MUTED))

        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=FONT_SMALL,
            padx=PADDING_MEDIUM,
            pady=4,
            relief="flat",
            **kwargs
        )


class InfoBox(tk.Frame):
    """Info box: label + input"""
    def __init__(self, parent, label="", value="", readonly=False, **kwargs):
        super().__init__(parent, bg=PANEL_BG, **kwargs)

        tk.Label(
            self,
            text=label,
            bg=PANEL_BG,
            fg=TEXT_SECONDARY,
            font=FONT_SMALL,
            anchor="w"
        ).pack(fill="x", anchor="w", pady=(0, 4))

        if readonly:
            # Read-only display
            tk.Label(
                self,
                text=value,
                bg="#F8FAFC",
                fg=TEXT_PRIMARY,
                font=FONT_BODY,
                anchor="w",
                relief="solid",
                bd=1,
                padx=PADDING_MEDIUM,
                pady=PADDING_SMALL,
            ).pack(fill="x", anchor="w")
        else:
            # Editable input
            var = tk.StringVar(value=value)
            tk.Entry(
                self,
                textvariable=var,
                font=FONT_BODY,
                bg=PANEL_BG,
                fg=TEXT_PRIMARY,
                relief="solid",
                bd=1,
                insertbackground=ACCENT_BLUE,
            ).pack(fill="x", anchor="w")
            self.var = var

    def get(self):
        return getattr(self, 'var', tk.StringVar()).get()

    def set(self, value):
        if hasattr(self, 'var'):
            self.var.set(value)


class TwoColumnForm(tk.Frame):
    """Two-column form layout"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=PANEL_BG, **kwargs)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self._row = 0

    def add_row(self, label1, widget1, label2=None, widget2=None):
        """Add row with 1 or 2 columns"""
        tk.Label(
            self, text=label1, bg=PANEL_BG, fg=TEXT_SECONDARY,
            font=FONT_SMALL, anchor="w"
        ).grid(row=self._row, column=0, sticky="w", padx=PADDING_MEDIUM, pady=(PADDING_MEDIUM, 4))

        widget1.grid(row=self._row + 1, column=0, sticky="ew", padx=PADDING_MEDIUM, pady=(0, PADDING_MEDIUM))

        if label2 and widget2:
            tk.Label(
                self, text=label2, bg=PANEL_BG, fg=TEXT_SECONDARY,
                font=FONT_SMALL, anchor="w"
            ).grid(row=self._row, column=1, sticky="w", padx=PADDING_MEDIUM, pady=(PADDING_MEDIUM, 4))

            widget2.grid(row=self._row + 1, column=1, sticky="ew", padx=PADDING_MEDIUM, pady=(0, PADDING_MEDIUM))
            self._row += 2
        else:
            self._row += 2

    def get_values(self):
        """Collect all values from widgets"""
        pass
