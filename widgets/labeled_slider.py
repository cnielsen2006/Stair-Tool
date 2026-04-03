import tkinter as tk
from tkinter import ttk


class LabeledSlider(ttk.Frame):
    """Composite widget: label + numeric entry on the same row, slider below."""

    def __init__(self, parent, label: str, from_: float, to: float,
                 initial: float, unit: str = "in", resolution: float = 1.0,
                 command=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._command   = command
        self._from      = from_
        self._to        = to
        self._resolution = resolution
        self._updating  = False  # prevent feedback loops

        self._var = tk.DoubleVar(value=initial)

        # Title row: label on left, entry + unit + feet label on right
        title_frame = ttk.Frame(self)
        title_frame.pack(fill="x")
        ttk.Label(title_frame, text=label, font=("Segoe UI", 9, "bold")).pack(side="left")

        self._unit_label = ttk.Label(title_frame, text="", foreground="#555555")
        self._unit_label.pack(side="right")

        ttk.Label(title_frame, text=unit, foreground="#555555").pack(side="right", padx=(2, 4))
        self._entry_var = tk.StringVar(value=f"{initial:.1f}")
        self._entry = ttk.Entry(title_frame, textvariable=self._entry_var, width=6,
                                justify="right")
        self._entry.pack(side="right")

        # Slider
        self._scale = ttk.Scale(
            self, from_=from_, to=to,
            orient="horizontal",
            variable=self._var,
            command=self._on_scale_moved,
        )
        self._scale.pack(fill="x", pady=(2, 0))

        self._entry.bind("<Return>",    self._on_entry_commit)
        self._entry.bind("<FocusOut>",  self._on_entry_commit)
        self._entry_var.trace_add("write", self._on_entry_typed)

        # Mouse-wheel support: Shift+scroll = fine (1/5 speed)
        self._scale.bind("<MouseWheel>", self._on_mousewheel)

        self._update_unit_label()

    def _update_unit_label(self):
        v = self._var.get()
        feet = int(v) // 12
        inches = v - feet * 12
        if feet:
            self._unit_label.config(text=f"({feet}' {inches:.1f}\")")
        else:
            self._unit_label.config(text=f"({v:.1f}\")")

    def _on_scale_moved(self, _=None):
        if self._updating:
            return
        self._updating = True
        v = round(self._var.get() / self._resolution) * self._resolution
        self._var.set(v)
        self._entry_var.set(f"{v:.1f}")
        self._update_unit_label()
        self._updating = False
        if self._command:
            self._command()

    def _on_mousewheel(self, event):
        """Handle mouse wheel on slider. Shift = fine adjustment (1/5 speed)."""
        # Windows: event.delta is typically ±120 per notch
        direction = 1 if event.delta > 0 else -1
        span = self._to - self._from
        step = span * 0.01  # normal: 1% of range per notch
        if event.state & 0x1:  # Shift key held
            step *= 0.2       # fine: 0.2% of range per notch
        step = max(step, self._resolution)  # never less than resolution
        new_val = self._var.get() + direction * step
        new_val = max(self._from, min(self._to, new_val))
        new_val = round(new_val / self._resolution) * self._resolution
        self._var.set(new_val)
        self._on_scale_moved()
        return "break"  # prevent default scroll behavior

    def _on_entry_typed(self, *_):
        pass  # validation happens on commit

    def _on_entry_commit(self, _=None):
        if self._updating:
            return
        try:
            v = float(self._entry_var.get())
            v = max(self._from, min(self._to, v))
            v = round(v / self._resolution) * self._resolution
        except ValueError:
            v = self._var.get()
        self._updating = True
        self._var.set(v)
        self._entry_var.set(f"{v:.1f}")
        self._update_unit_label()
        self._updating = False
        if self._command:
            self._command()

    def get(self) -> float:
        return self._var.get()

    def set(self, value: float):
        self._updating = True
        self._var.set(value)
        self._entry_var.set(f"{value:.1f}")
        self._update_unit_label()
        self._updating = False
