import tkinter as tk
from tkinter import ttk

from constants import (
    DEFAULT_MIN_RISE, DEFAULT_MAX_RISE,
    DEFAULT_MIN_TREAD, DEFAULT_MAX_TREAD,
    RISE_MIN_IN, RISE_MAX_IN,
    RUN_MIN_IN,  RUN_MAX_IN,
    DEFAULT_STRINGER_COUNT, DEFAULT_STAIR_WIDTH,
    DEFAULT_TREAD_BOARD_WIDTH, TREAD_BOARD_OPTIONS,
)
from widgets.labeled_slider import LabeledSlider
from widgets.constraint_row import ConstraintRow

_DEFAULTS = {
    "total_rise":       108.0,
    "total_run":        144.0,
    "min_rise":         DEFAULT_MIN_RISE,
    "max_rise":         DEFAULT_MAX_RISE,
    "min_tread":        DEFAULT_MIN_TREAD,
    "max_tread":        DEFAULT_MAX_TREAD,
    "stringer_count":   DEFAULT_STRINGER_COUNT,
    "stair_width":      DEFAULT_STAIR_WIDTH,
    "tread_board_width": DEFAULT_TREAD_BOARD_WIDTH,
}


class InputPanel(ttk.LabelFrame):
    """Left panel: total rise/run sliders and per-step constraint fields."""

    def __init__(self, parent, on_change=None, on_constraint_change=None,
                 initial: dict | None = None, **kwargs):
        super().__init__(parent, text="Stair Dimensions", padding=10, **kwargs)
        self._on_change = on_change
        self._on_constraint_change = on_constraint_change
        iv = {**_DEFAULTS, **(initial or {})}

        # --- Total Rise ---
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(0, 6))
        ttk.Label(self, text="Overall Dimensions", foreground="#444444",
                  font=("Segoe UI", 8)).pack(anchor="w")

        self.rise_slider = LabeledSlider(
            self, label="Total Rise",
            from_=RISE_MIN_IN, to=RISE_MAX_IN,
            initial=iv["total_rise"], unit="in", resolution=0.5,
            command=self._changed,
        )
        self.rise_slider.pack(fill="x", pady=(4, 0))

        self.run_slider = LabeledSlider(
            self, label="Total Run",
            from_=RUN_MIN_IN, to=RUN_MAX_IN,
            initial=iv["total_run"], unit="in", resolution=0.5,
            command=self._changed,
        )
        self.run_slider.pack(fill="x", pady=(8, 0))

        # --- Per-step constraints ---
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(12, 6))
        ttk.Label(self, text="Per-Step Constraints (IBC/IRC defaults)",
                  foreground="#444444", font=("Segoe UI", 8)).pack(anchor="w")

        self.rise_constraints = ConstraintRow(
            self, label="Riser Height",
            min_default=iv["min_rise"], max_default=iv["max_rise"],
            command=self._constraint_changed,
        )
        self.rise_constraints.pack(fill="x", pady=(4, 0))

        self.tread_constraints = ConstraintRow(
            self, label="Tread Depth",
            min_default=iv["min_tread"], max_default=iv["max_tread"],
            command=self._constraint_changed,
        )
        self.tread_constraints.pack(fill="x", pady=(4, 0))

        # --- Construction details ---
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(12, 6))
        ttk.Label(self, text="Construction Details",
                  foreground="#444444", font=("Segoe UI", 8)).pack(anchor="w")

        cons_frame = ttk.Frame(self)
        cons_frame.pack(fill="x", pady=(4, 0))

        # Stringer count
        ttk.Label(cons_frame, text="Stringers:", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w", pady=(2, 0))
        self._stringer_count_var = tk.StringVar(value=str(iv["stringer_count"]))
        self._stringer_count_spin = ttk.Spinbox(
            cons_frame, textvariable=self._stringer_count_var,
            from_=2, to=10, width=5, command=self._changed)
        self._stringer_count_spin.grid(row=0, column=1, sticky="w", padx=(4, 0), pady=(2, 0))
        self._stringer_count_spin.bind("<Return>", lambda _: self._changed())
        self._stringer_count_spin.bind("<FocusOut>", lambda _: self._changed())

        # Stair width
        ttk.Label(cons_frame, text="Stair Width:", font=("Segoe UI", 9, "bold")).grid(
            row=1, column=0, sticky="w", pady=(2, 0))
        width_entry_frame = ttk.Frame(cons_frame)
        width_entry_frame.grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(2, 0))
        self._stair_width_var = tk.StringVar(value=f"{iv['stair_width']:.1f}")
        self._stair_width_entry = ttk.Entry(
            width_entry_frame, textvariable=self._stair_width_var, width=6, justify="right")
        self._stair_width_entry.pack(side="left")
        ttk.Label(width_entry_frame, text="in", foreground="#555555").pack(side="left", padx=(2, 0))
        self._stair_width_entry.bind("<Return>", lambda _: self._changed())
        self._stair_width_entry.bind("<FocusOut>", lambda _: self._changed())

        # Tread board width (dropdown)
        ttk.Label(cons_frame, text="Tread Lumber:", font=("Segoe UI", 9, "bold")).grid(
            row=2, column=0, sticky="w", pady=(2, 0))
        # Find the label matching the saved width
        saved_bw = iv["tread_board_width"]
        board_labels = list(TREAD_BOARD_OPTIONS.keys())
        initial_label = board_labels[0]
        for lbl, w in TREAD_BOARD_OPTIONS.items():
            if abs(w - saved_bw) < 0.01:
                initial_label = lbl
                break
        self._tread_board_var = tk.StringVar(value=initial_label)
        self._tread_board_combo = ttk.Combobox(
            cons_frame, textvariable=self._tread_board_var,
            values=board_labels, state="readonly", width=14)
        self._tread_board_combo.grid(row=2, column=1, sticky="w", padx=(4, 0), pady=(2, 0))
        self._tread_board_combo.bind("<<ComboboxSelected>>", lambda _: self._changed())

        # --- Reset button ---
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(12, 6))
        ttk.Button(self, text="Reset to IBC/IRC Defaults",
                   command=self._reset_defaults).pack(anchor="w")

    def _changed(self):
        if self._on_change:
            self._on_change()

    def _constraint_changed(self):
        if self._on_constraint_change:
            self._on_constraint_change()
        elif self._on_change:
            self._on_change()

    def _reset_defaults(self):
        self.rise_constraints.set_values(DEFAULT_MIN_RISE, DEFAULT_MAX_RISE)
        self.tread_constraints.set_values(DEFAULT_MIN_TREAD, DEFAULT_MAX_TREAD)
        self._constraint_changed()

    def get_inputs(self) -> dict:
        try:
            stringer_count = int(self._stringer_count_var.get())
        except ValueError:
            stringer_count = DEFAULT_STRINGER_COUNT
        try:
            stair_width = float(self._stair_width_var.get())
        except ValueError:
            stair_width = DEFAULT_STAIR_WIDTH
        board_label = self._tread_board_var.get()
        tread_board_width = TREAD_BOARD_OPTIONS.get(board_label, DEFAULT_TREAD_BOARD_WIDTH)
        return {
            "total_rise":       self.rise_slider.get(),
            "total_run":        self.run_slider.get(),
            "min_rise":         self.rise_constraints.get_min(),
            "max_rise":         self.rise_constraints.get_max(),
            "min_tread":        self.tread_constraints.get_min(),
            "max_tread":        self.tread_constraints.get_max(),
            "stringer_count":   stringer_count,
            "stair_width":      stair_width,
            "tread_board_width": tread_board_width,
        }
