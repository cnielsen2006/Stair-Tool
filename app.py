import json
import os
import sys
import tkinter as tk
from tkinter import ttk
from typing import Optional

from constants import SETTINGS_FILE
from models import StairModel
from panels.input_panel import InputPanel
from panels.results_panel import ResultsPanel

ICON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stairs.ico")


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Stair Calculator — IBC/IRC")
        self.root.minsize(960, 580)

        if os.path.isfile(ICON_FILE):
            self.root.iconbitmap(ICON_FILE)

        style = ttk.Style()
        style.theme_use("clam")

        saved = self._load_settings()
        self._selected_risers: Optional[int] = saved.get("selected_risers") if saved else None
        self._build_ui(saved)
        self._recalculate()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_settings(self) -> dict | None:
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _save_settings(self):
        data = self.input_panel.get_inputs()
        if self._selected_risers is not None:
            data["selected_risers"] = self._selected_risers
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _on_close(self):
        self._save_settings()
        self.root.destroy()

    def _build_ui(self, saved: dict | None = None):
        self.root.columnconfigure(0, weight=0, minsize=280)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.input_panel = InputPanel(
            self.root, on_change=self._on_inputs_changed,
            on_constraint_change=self._on_constraints_changed, initial=saved)
        self.input_panel.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        self.results_panel = ResultsPanel(self.root)
        self.results_panel.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self.root, textvariable=self._status_var,
            relief="sunken", anchor="w", padding=(4, 2))
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

        # Keyboard shortcut: Ctrl+R → reset defaults
        self.root.bind("<Control-r>", lambda _: self.input_panel._reset_defaults())

    def _on_inputs_changed(self):
        # Do not reset _selected_risers — preserve the user's explicit step count
        self._recalculate()

    def _on_constraints_changed(self):
        # Constraints changed — preserve the user's selected N, just recalculate
        self._recalculate()

    def _recalculate(self):
        inputs = self.input_panel.get_inputs()
        # Separate construction params from model params
        stringer_count = inputs.pop("stringer_count", 3)
        stair_width = inputs.pop("stair_width", 36.0)
        tread_board_width = inputs.pop("tread_board_width", 5.5)
        tread_board_label = inputs.pop("tread_board_label", "")
        tread_board_gap = inputs.pop("tread_board_gap", 0.25)
        nosing_overhang = inputs.pop("nosing_overhang", 0.75)
        stringer_lumber_ft = inputs.pop("stringer_lumber_ft", 0)

        # Read step count from input panel spinbox (may be None on first run)
        spinbox_risers = self.input_panel.get_selected_steps()
        n = spinbox_risers or self._selected_risers

        model = StairModel(**inputs)
        opt   = model.optimal_config()

        if opt:
            if not n:
                n = opt.n_risers
            self._status_var.set(
                f"Optimal: {opt.n_risers - 1} steps ({opt.n_risers} risers)  |  "
                f"Rise {opt.riser_height:.3f}\"  Tread {opt.tread_depth:.3f}\"  "
                f"2R+T={opt.rule_of_thumb:.2f}\""
            )
        else:
            if not n:
                n_lo, n_hi = model.valid_n_range()
                n = (n_lo + n_hi) // 2 if n_lo else 2
            self._status_var.set("No valid step count — adjust constraints or total dimensions.")

        self.results_panel.update(model, n, stringer_count, stair_width,
                                  tread_board_width, tread_board_label,
                                  tread_board_gap, nosing_overhang,
                                  stringer_lumber_ft)

        # Push resolved range info back to the input panel spinbox
        self._selected_risers = self.results_panel._selected_risers
        n_lo, n_hi, valid_ns = self.results_panel._steps_range
        valid_lo = min(valid_ns) if valid_ns else None
        valid_hi = max(valid_ns) if valid_ns else None
        self.input_panel.set_steps_range(n_lo, n_hi, valid_lo, valid_hi,
                                         self._selected_risers)

    def run(self):
        self.root.mainloop()
