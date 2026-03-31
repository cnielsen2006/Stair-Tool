import tkinter as tk
from tkinter import ttk

from constants import (
    DEFAULT_MIN_RISE, DEFAULT_MAX_RISE,
    DEFAULT_MIN_TREAD, DEFAULT_MAX_TREAD,
    RISE_MIN_IN, RISE_MAX_IN,
    RUN_MIN_IN,  RUN_MAX_IN,
)
from widgets.labeled_slider import LabeledSlider
from widgets.constraint_row import ConstraintRow

_DEFAULTS = {
    "total_rise": 108.0,
    "total_run":  144.0,
    "min_rise":   DEFAULT_MIN_RISE,
    "max_rise":   DEFAULT_MAX_RISE,
    "min_tread":  DEFAULT_MIN_TREAD,
    "max_tread":  DEFAULT_MAX_TREAD,
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
        return {
            "total_rise": self.rise_slider.get(),
            "total_run":  self.run_slider.get(),
            "min_rise":   self.rise_constraints.get_min(),
            "max_rise":   self.rise_constraints.get_max(),
            "min_tread":  self.tread_constraints.get_min(),
            "max_tread":  self.tread_constraints.get_max(),
        }
