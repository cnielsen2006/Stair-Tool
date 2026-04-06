import tkinter as tk
from tkinter import ttk

from constants import (
    DEFAULT_MIN_RISE, DEFAULT_MAX_RISE,
    DEFAULT_MIN_TREAD, DEFAULT_MAX_TREAD,
    RISE_MIN_IN, RISE_MAX_IN,
    RUN_MIN_IN,  RUN_MAX_IN,
    DEFAULT_STRINGER_COUNT, DEFAULT_STAIR_WIDTH,
    DEFAULT_TREAD_BOARD_WIDTH, TREAD_BOARD_OPTIONS,
    DEFAULT_TREAD_BOARD_GAP, DEFAULT_NOSING_OVERHANG,
    DEFAULT_SUPPORT_EVERY_N,
    DEFAULT_STRINGER_LUMBER_FT, STRINGER_LUMBER_OPTIONS,
    DEFAULT_BOTTOM_PLUMB_CUT, DEFAULT_ANCHOR_DEBUG,
    COMFORT_IDEAL_LO, COMFORT_IDEAL_HI, COMFORT_WARN_LO, COMFORT_WARN_HI,
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
    "tread_board_gap":  DEFAULT_TREAD_BOARD_GAP,
    "nosing_overhang":  DEFAULT_NOSING_OVERHANG,
    "support_every_n":  DEFAULT_SUPPORT_EVERY_N,
    "stringer_lumber_ft": DEFAULT_STRINGER_LUMBER_FT,
    "bottom_plumb_cut": DEFAULT_BOTTOM_PLUMB_CUT,
    "anchor_debug": DEFAULT_ANCHOR_DEBUG,
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

        # Comfort gauge (2R+T) — compact colored bar below Total Run
        gauge_row = ttk.Frame(self)
        gauge_row.pack(fill="x", pady=(4, 0))
        ttk.Label(gauge_row, text="Comfort:", font=("Segoe UI", 8),
                  foreground="#555555").pack(side="left")
        self._gauge_canvas = tk.Canvas(gauge_row, width=0, height=10, bd=0,
                                       highlightthickness=0, background="#EEEEEE")
        self._gauge_canvas.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self._gauge_canvas.bind("<Configure>", self._redraw_gauge)
        self._current_rot = None

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

        # Step count selector
        step_row = ttk.Frame(self)
        step_row.pack(fill="x", pady=(6, 0))
        ttk.Label(step_row, text="Steps (incl. landing):",
                  font=("Segoe UI", 9, "bold")).pack(side="left")
        self._steps_var = tk.StringVar()
        self._steps_spinbox = ttk.Spinbox(
            step_row, textvariable=self._steps_var, width=6,
            command=self._on_steps_spinbox,
        )
        self._steps_spinbox.pack(side="left", padx=(4, 0))
        self._steps_spinbox.bind("<Return>",   self._on_steps_spinbox)
        self._steps_spinbox.bind("<FocusOut>", self._on_steps_spinbox)
        self._valid_range_label = ttk.Label(step_row, text="", foreground="#555555")
        self._valid_range_label.pack(side="left", padx=(8, 0))

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
        # Restore the exact label if saved, otherwise match by width
        saved_label = iv.get("tread_board_label", "")
        saved_bw = iv["tread_board_width"]
        board_labels = list(TREAD_BOARD_OPTIONS.keys())
        initial_label = board_labels[0]
        if saved_label in TREAD_BOARD_OPTIONS:
            initial_label = saved_label
        else:
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

        # Tread board gap
        ttk.Label(cons_frame, text="Board Gap:", font=("Segoe UI", 9, "bold")).grid(
            row=3, column=0, sticky="w", pady=(2, 0))
        gap_frame = ttk.Frame(cons_frame)
        gap_frame.grid(row=3, column=1, sticky="w", padx=(4, 0), pady=(2, 0))
        self._tread_gap_var = tk.StringVar(value=f"{iv['tread_board_gap']:.2f}")
        self._tread_gap_entry = ttk.Entry(
            gap_frame, textvariable=self._tread_gap_var, width=6, justify="right")
        self._tread_gap_entry.pack(side="left")
        ttk.Label(gap_frame, text="in", foreground="#555555").pack(side="left", padx=(2, 0))
        self._tread_gap_entry.bind("<Return>", lambda _: self._changed())
        self._tread_gap_entry.bind("<FocusOut>", lambda _: self._changed())

        # Nosing overhang tolerance
        ttk.Label(cons_frame, text="Nosing Overhang:", font=("Segoe UI", 9, "bold")).grid(
            row=4, column=0, sticky="w", pady=(2, 0))
        nosing_frame = ttk.Frame(cons_frame)
        nosing_frame.grid(row=4, column=1, sticky="w", padx=(4, 0), pady=(2, 0))
        self._nosing_var = tk.StringVar(value=f"{iv['nosing_overhang']:.2f}")
        self._nosing_entry = ttk.Entry(
            nosing_frame, textvariable=self._nosing_var, width=6, justify="right")
        self._nosing_entry.pack(side="left")
        ttk.Label(nosing_frame, text="in", foreground="#555555").pack(side="left", padx=(2, 0))
        self._nosing_entry.bind("<Return>", lambda _: self._changed())
        self._nosing_entry.bind("<FocusOut>", lambda _: self._changed())

        # Stringer lumber length
        ttk.Label(cons_frame, text="Stringer Lumber:", font=("Segoe UI", 9, "bold")).grid(
            row=5, column=0, sticky="w", pady=(2, 0))
        lumber_labels = ["Auto"] + [f"{ft}'" for ft in STRINGER_LUMBER_OPTIONS if ft > 0]
        saved_lumber = iv["stringer_lumber_ft"]
        if saved_lumber == 0:
            initial_lumber = "Auto"
        else:
            initial_lumber = f"{saved_lumber}'"
            if initial_lumber not in lumber_labels:
                initial_lumber = "Auto"
        self._stringer_lumber_var = tk.StringVar(value=initial_lumber)
        self._stringer_lumber_combo = ttk.Combobox(
            cons_frame, textvariable=self._stringer_lumber_var,
            values=lumber_labels, state="readonly", width=14)
        self._stringer_lumber_combo.grid(row=5, column=1, sticky="w", padx=(4, 0), pady=(2, 0))
        self._stringer_lumber_combo.bind("<<ComboboxSelected>>", lambda _: self._changed())

        # Support upright every Nth step
        ttk.Label(cons_frame, text="Support Every:", font=("Segoe UI", 9, "bold")).grid(
            row=6, column=0, sticky="w", pady=(2, 0))
        support_row = ttk.Frame(cons_frame)
        support_row.grid(row=6, column=1, sticky="w", padx=(4, 0), pady=(2, 0))
        self._support_every_n_var = tk.StringVar(value=str(iv["support_every_n"]))
        self._support_every_n_spin = ttk.Spinbox(
            support_row, textvariable=self._support_every_n_var,
            from_=1, to=20, width=4, command=self._changed)
        self._support_every_n_spin.pack(side="left")
        ttk.Label(support_row, text="steps", foreground="#555555").pack(side="left", padx=(2, 0))
        self._support_every_n_spin.bind("<Return>", lambda _: self._changed())
        self._support_every_n_spin.bind("<FocusOut>", lambda _: self._changed())

        # Bottom plumb cut checkbox
        self._bottom_plumb_cut_var = tk.BooleanVar(value=iv["bottom_plumb_cut"])
        self._bottom_plumb_cut_cb = ttk.Checkbutton(
            cons_frame, text="Bottom plumb cut",
            variable=self._bottom_plumb_cut_var, command=self._changed)
        self._bottom_plumb_cut_cb.grid(row=7, column=0, columnspan=2,
                                        sticky="w", pady=(2, 0))

        # Anchor debug guide lines checkbox
        self._anchor_debug_var = tk.BooleanVar(value=iv["anchor_debug"])
        self._anchor_debug_cb = ttk.Checkbutton(
            cons_frame, text="Anchor debug lines",
            variable=self._anchor_debug_var, command=self._changed)
        self._anchor_debug_cb.grid(row=8, column=0, columnspan=2,
                                    sticky="w", pady=(2, 0))

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

    def _on_steps_spinbox(self, _=None):
        if self._on_change:
            self._on_change()

    def get_selected_steps(self) -> int | None:
        """Return the spinbox value as risers (steps + 1), or None."""
        try:
            return int(self._steps_var.get()) + 1
        except ValueError:
            return None

    def set_steps_range(self, n_lo: int, n_hi: int, valid_lo: int | None,
                        valid_hi: int | None, selected_risers: int):
        """Update the step-count spinbox range, valid-range label, and value."""
        self._steps_spinbox.config(from_=n_lo - 1, to=n_hi - 1)
        if valid_lo is not None:
            if valid_lo == valid_hi:
                rng_text = f"valid: {valid_lo - 1}"
            else:
                rng_text = f"valid: {valid_lo - 1}\u2013{valid_hi - 1}"
            self._valid_range_label.config(text=rng_text, foreground="#555555")
        else:
            self._valid_range_label.config(text="no valid solution", foreground="#CC3333")
        self._steps_var.set(str(selected_risers - 1))

    def set_comfort_rot(self, rot: float | None):
        """Update the 2R+T comfort gauge value."""
        self._current_rot = rot
        self._redraw_gauge()

    def _redraw_gauge(self, _=None):
        gc = self._gauge_canvas
        gc.delete("all")
        gw = gc.winfo_width() or 200
        gh = gc.winfo_height() or 10

        rot = self._current_rot
        full_lo = COMFORT_WARN_LO - 2
        full_hi = COMFORT_WARN_HI + 2

        def rot_to_x(v):
            return max(0, min(gw, (v - full_lo) / (full_hi - full_lo) * gw))

        zones = [
            (full_lo,          COMFORT_WARN_LO,  "#E05050"),
            (COMFORT_WARN_LO,  COMFORT_IDEAL_LO, "#E0A020"),
            (COMFORT_IDEAL_LO, COMFORT_IDEAL_HI, "#40AA40"),
            (COMFORT_IDEAL_HI, COMFORT_WARN_HI,  "#E0A020"),
            (COMFORT_WARN_HI,  full_hi,           "#E05050"),
        ]
        for z_lo, z_hi, color in zones:
            x0 = rot_to_x(z_lo)
            x1 = rot_to_x(z_hi)
            if x1 > x0:
                gc.create_rectangle(x0, 0, x1, gh, fill=color, outline="")

        for v in (COMFORT_WARN_LO, COMFORT_IDEAL_LO, COMFORT_IDEAL_HI, COMFORT_WARN_HI):
            x = rot_to_x(v)
            gc.create_line(x, 0, x, gh, fill="#FFFFFF", width=1)

        if rot is None:
            return

        needle_x = rot_to_x(rot)
        gc.create_line(needle_x, 0, needle_x, gh, fill="#000000", width=2)
        gc.create_polygon(
            needle_x - 3, 0, needle_x + 3, 0, needle_x, 4,
            fill="#000000", outline="")

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
        try:
            tread_board_gap = float(self._tread_gap_var.get())
            if tread_board_gap < 0:
                tread_board_gap = 0.0
        except ValueError:
            tread_board_gap = DEFAULT_TREAD_BOARD_GAP
        try:
            nosing_overhang = float(self._nosing_var.get())
            if nosing_overhang < 0:
                nosing_overhang = 0.0
        except ValueError:
            nosing_overhang = DEFAULT_NOSING_OVERHANG
        lumber_sel = self._stringer_lumber_var.get()
        if lumber_sel == "Auto":
            stringer_lumber_ft = 0
        else:
            try:
                stringer_lumber_ft = int(lumber_sel.rstrip("'"))
            except ValueError:
                stringer_lumber_ft = 0
        try:
            support_every_n = max(1, int(self._support_every_n_var.get()))
        except ValueError:
            support_every_n = DEFAULT_SUPPORT_EVERY_N
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
            "tread_board_label": board_label,
            "tread_board_gap": tread_board_gap,
            "nosing_overhang": nosing_overhang,
            "support_every_n":  support_every_n,
            "stringer_lumber_ft": stringer_lumber_ft,
            "bottom_plumb_cut": self._bottom_plumb_cut_var.get(),
            "anchor_debug": self._anchor_debug_var.get(),
        }
