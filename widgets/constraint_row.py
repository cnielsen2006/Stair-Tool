import tkinter as tk
from tkinter import ttk


class ConstraintRow(ttk.Frame):
    """A labeled pair of min/max entry fields for dimension constraints."""

    def __init__(self, parent, label: str, min_default: float,
                 max_default: float, command=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._command = command

        ttk.Label(self, text=label, font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(4, 0))

        ttk.Label(self, text="Min:").grid(row=1, column=0, sticky="w", padx=(0, 2))
        self._min_var = tk.StringVar(value=f"{min_default:.2f}")
        self._min_entry = ttk.Entry(self, textvariable=self._min_var, width=7, justify="right")
        self._min_entry.grid(row=1, column=1, padx=(0, 8))

        ttk.Label(self, text="Max:").grid(row=1, column=2, sticky="w", padx=(0, 2))
        self._max_var = tk.StringVar(value=f"{max_default:.2f}")
        self._max_entry = ttk.Entry(self, textvariable=self._max_var, width=7, justify="right")
        self._max_entry.grid(row=1, column=3)

        ttk.Label(self, text="in", foreground="#555555").grid(row=1, column=4, padx=(2, 0))

        for entry in (self._min_entry, self._max_entry):
            entry.bind("<Return>",   self._on_commit)
            entry.bind("<FocusOut>", self._on_commit)

    def _on_commit(self, _=None):
        self._validate_highlight()
        if self._command:
            self._command()

    def _validate_highlight(self):
        try:
            lo = float(self._min_var.get())
            hi = float(self._max_var.get())
            ok = lo < hi
        except ValueError:
            ok = False
        color = "" if ok else "#FFCCCC"
        self._min_entry.config(background=color)
        self._max_entry.config(background=color)

    def get_min(self) -> float:
        try:
            return float(self._min_var.get())
        except ValueError:
            return 0.0

    def get_max(self) -> float:
        try:
            return float(self._max_var.get())
        except ValueError:
            return 0.0

    def set_values(self, min_val: float, max_val: float):
        self._min_var.set(f"{min_val:.2f}")
        self._max_var.set(f"{max_val:.2f}")
        self._validate_highlight()
