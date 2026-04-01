import tkinter as tk
from tkinter import ttk
from typing import Optional

from constants import (
    CANVAS_WIDTH, CANVAS_HEIGHT, CANVAS_MARGIN,
    DIAGRAM_BG, STEP_FILL, STEP_OUTLINE, LABEL_COLOR,
    GROUND_COLOR, OPTIMAL_COLOR, INVALID_COLOR,
    COMFORT_IDEAL_LO, COMFORT_IDEAL_HI, COMFORT_WARN_LO, COMFORT_WARN_HI,
    ANGLE_IDEAL_LO, ANGLE_IDEAL_HI, ANGLE_WARN_LO, ANGLE_WARN_HI,
)
from models import StairModel, StepConfig


class ResultsPanel(ttk.Frame):
    """Right panel: stair diagram canvas + computed results summary."""

    def __init__(self, parent, on_risers_change=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._on_risers_change = on_risers_change
        self._model: Optional[StairModel] = None
        self._selected_risers: Optional[int]   = None
        self._all_configs = []
        self._current_rot: Optional[float] = None  # 2R+T for gauge
        self._stringer_count: int = 3
        self._stair_width: float = 36.0
        self._tread_board_width: float = 5.5

        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Canvas
        canvas_frame = ttk.LabelFrame(self, text="Stair Diagram", padding=4)
        canvas_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._canvas = tk.Canvas(
            canvas_frame,
            width=CANVAS_WIDTH, height=CANVAS_HEIGHT,
            background=DIAGRAM_BG, relief="sunken", bd=1,
        )
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # Summary area
        summary_frame = ttk.LabelFrame(self, text="Results", padding=8)
        summary_frame.pack(fill="x", padx=4, pady=(0, 4))

        # N selector row
        sel_row = ttk.Frame(summary_frame)
        sel_row.pack(fill="x", pady=(0, 6))
        ttk.Label(sel_row, text="Steps (including landing):").pack(side="left")
        self._steps_var = tk.StringVar()
        self._steps_spinbox = ttk.Spinbox(
            sel_row, textvariable=self._steps_var, width=6,
            command=self._on_steps_spinbox,
        )
        self._steps_spinbox.pack(side="left", padx=(4, 0))
        self._steps_spinbox.bind("<Return>",   self._on_steps_spinbox)
        self._steps_spinbox.bind("<FocusOut>", self._on_steps_spinbox)
        self._valid_range_label = ttk.Label(sel_row, text="", foreground="#555555")
        self._valid_range_label.pack(side="left", padx=(8, 0))

        # Stats grid — row 0: step dims + validity
        stats = ttk.Frame(summary_frame)
        stats.pack(fill="x")
        self._stat_vars = {}
        row0_defs = [
            ("riser",  "Riser Height:"),
            ("tread",  "Tread Depth:"),
            ("rot",    "2R + T:"),
            ("status", "Status:"),
        ]
        for col, (key, lbl) in enumerate(row0_defs):
            ttk.Label(stats, text=lbl, font=("Segoe UI", 8, "bold")).grid(
                row=0, column=col * 2, sticky="e", padx=(8 if col else 0, 2))
            var = tk.StringVar(value="—")
            self._stat_vars[key] = var
            ttk.Label(stats, textvariable=var).grid(
                row=0, column=col * 2 + 1, sticky="w")

        # Row 1: stringer info
        row1_defs = [
            ("stringer", "Stringer Length:"),
            ("stringer_ft", "(feet):"),
            ("supports",  "Intermediate Supports:"),
            ("spacing",   "Support Spacing:"),
        ]
        for col, (key, lbl) in enumerate(row1_defs):
            ttk.Label(stats, text=lbl, font=("Segoe UI", 8, "bold")).grid(
                row=1, column=col * 2, sticky="e", padx=(8 if col else 0, 2), pady=(4, 0))
            var = tk.StringVar(value="—")
            self._stat_vars[key] = var
            ttk.Label(stats, textvariable=var).grid(
                row=1, column=col * 2 + 1, sticky="w", pady=(4, 0))

        # Row 2: angle info
        row2_defs = [
            ("angle",       "Stair Angle:"),
            ("angle_rating","Angle Rating:"),
        ]
        for col, (key, lbl) in enumerate(row2_defs):
            ttk.Label(stats, text=lbl, font=("Segoe UI", 8, "bold")).grid(
                row=2, column=col * 2, sticky="e", padx=(8 if col else 0, 2), pady=(4, 0))
            var = tk.StringVar(value="—")
            self._stat_vars[key] = var
            val_lbl = ttk.Label(stats, textvariable=var)
            val_lbl.grid(row=2, column=col * 2 + 1, sticky="w", pady=(4, 0))
            if key == "angle_rating":
                self._angle_rating_label = val_lbl

        # Comfort gauge
        gauge_frame = ttk.Frame(summary_frame)
        gauge_frame.pack(fill="x", pady=(6, 2))
        ttk.Label(gauge_frame, text="Comfort:", font=("Segoe UI", 8, "bold")).pack(side="left")
        self._comfort_label = ttk.Label(gauge_frame, text="", font=("Segoe UI", 8))
        self._comfort_label.pack(side="right")

        self._gauge_canvas = tk.Canvas(summary_frame, height=18, bd=0,
                                       highlightthickness=0, background="#EEEEEE")
        self._gauge_canvas.pack(fill="x", pady=(0, 4))
        self._gauge_canvas.bind("<Configure>", self._redraw_gauge)

        self._status_label = ttk.Label(
            summary_frame, text="", font=("Segoe UI", 9, "bold"))
        self._status_label.pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, model: StairModel, selected_risers: Optional[int],
               stringer_count: int = 3, stair_width: float = 36.0,
               tread_board_width: float = 5.5):
        self._model      = model
        self._stringer_count = stringer_count
        self._stair_width = stair_width
        self._tread_board_width = tread_board_width
        self._all_configs = model.compute_configs()
        valid_ns = [c.n_risers for c in self._all_configs if c.is_valid]

        # Configure spinbox to span the full search range (valid + nearby invalid)
        # Always include selected_risers in the range so a user-entered value isn't clamped
        # Spinbox shows steps (treads = risers - 1); internally we track risers.
        all_ns = [c.n_risers for c in self._all_configs]
        n_lo = min(all_ns) if all_ns else 2
        n_hi = max(all_ns) if all_ns else 50
        if selected_risers is not None:
            n_lo = min(n_lo, selected_risers)
            n_hi = max(n_hi, selected_risers)
        self._steps_spinbox.config(from_=n_lo - 1, to=n_hi - 1)
        if valid_ns:
            lo, hi = min(valid_ns), max(valid_ns)
            rng_text = f"valid: {lo - 1}" if lo == hi else f"valid: {lo - 1}–{hi - 1}"
            self._valid_range_label.config(text=rng_text, foreground="#555555")
        else:
            self._valid_range_label.config(text="no valid solution", foreground=INVALID_COLOR)

        # Set selected N (risers) — always honor an explicitly provided value
        if selected_risers is not None:
            self._selected_risers = selected_risers
        elif valid_ns:
            opt = model.optimal_config()
            self._selected_risers = opt.n_risers if opt else valid_ns[0]
        else:
            # fallback: show closest possible
            self._selected_risers = self._all_configs[len(self._all_configs)//2].n_risers \
                if self._all_configs else 2

        self._steps_var.set(str(self._selected_risers - 1))
        self._refresh()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_steps_spinbox(self, _=None):
        try:
            steps = int(self._steps_var.get())
        except ValueError:
            return
        n = steps + 1  # convert steps (treads) to risers
        self._selected_risers = n
        self._refresh()
        if self._on_risers_change:
            self._on_risers_change(n)

    def _on_canvas_resize(self, _=None):
        if self._model and self._selected_risers:
            self._redraw_canvas()

    def _refresh(self):
        cfg = self._find_config(self._selected_risers)
        self._update_summary(cfg)
        self._redraw_canvas()

    def _find_config(self, n: Optional[int]) -> Optional[StepConfig]:
        if n is None:
            return None
        for c in self._all_configs:
            if c.n_risers == n:
                return c
        # N is outside the precomputed range — compute on-the-fly
        if self._model and n >= 2:
            from models import StepConfig
            import math
            riser = self._model.total_rise / n
            tread = self._model.total_run / (n - 1)
            valid = (
                self._model.min_rise  <= riser <= self._model.max_rise and
                self._model.min_tread <= tread <= self._model.max_tread
            )
            rot = 2 * riser + tread
            stringer_len = math.sqrt(self._model.total_rise**2 + self._model.total_run**2)
            from models import STRINGER_MAX_SPAN_IN
            n_supports = max(0, math.ceil(stringer_len / STRINGER_MAX_SPAN_IN) - 1)
            spacing = stringer_len / (n_supports + 1) if n_supports > 0 else stringer_len
            score = self._model._score(riser, tread)
            return StepConfig(n, riser, tread, score, valid, rot, stringer_len, n_supports, spacing)
        return None

    def _update_summary(self, cfg: Optional[StepConfig]):
        if cfg is None:
            for var in self._stat_vars.values():
                var.set("—")
            self._status_label.config(text="No data", foreground=INVALID_COLOR)
            self._current_rot = None
            self._redraw_gauge()
            return


        self._stat_vars["riser"].set(f"{cfg.riser_height:.3f}\"")
        self._stat_vars["tread"].set(f"{cfg.tread_depth:.3f}\"")
        rot = cfg.rule_of_thumb
        self._current_rot = rot
        self._stat_vars["rot"].set(f"{rot:.2f}\" (ideal 24–25)")
        self._redraw_gauge()

        # Angle info
        import math as _math
        ang_deg = _math.degrees(_math.atan2(self._model.total_rise, self._model.total_run))
        self._stat_vars["angle"].set(f"{ang_deg:.1f}°  (ideal {ANGLE_IDEAL_LO:.0f}°–{ANGLE_IDEAL_HI:.0f}°)")
        if ANGLE_IDEAL_LO <= ang_deg <= ANGLE_IDEAL_HI:
            ang_rating, ang_color = "Ideal", OPTIMAL_COLOR
        elif ANGLE_WARN_LO <= ang_deg < ANGLE_IDEAL_LO:
            ang_rating, ang_color = "Slightly shallow", "#CC7700"
        elif ANGLE_IDEAL_HI < ang_deg <= ANGLE_WARN_HI:
            ang_rating, ang_color = "Slightly steep", "#CC7700"
        elif ang_deg < ANGLE_WARN_LO:
            ang_rating, ang_color = "Too shallow", INVALID_COLOR
        else:
            ang_rating, ang_color = "Too steep", INVALID_COLOR
        self._stat_vars["angle_rating"].set(ang_rating)
        self._angle_rating_label.config(foreground=ang_color)

        # Stringer info (stringer_length is same for all N since total_rise/run fixed)
        sl_in = cfg.stringer_length
        sl_ft = sl_in / 12.0
        self._stat_vars["stringer"].set(f"{sl_in:.2f}\"")
        self._stat_vars["stringer_ft"].set(f"{sl_ft:.2f} ft")
        if cfg.support_count == 0:
            self._stat_vars["supports"].set("None required")
            self._stat_vars["spacing"].set(f"Full span {sl_ft:.1f} ft")
        else:
            self._stat_vars["supports"].set(str(cfg.support_count))
            self._stat_vars["spacing"].set(f"{cfg.support_spacing / 12:.2f} ft o.c.")

        if cfg.is_valid:
            opt = self._model.optimal_config() if self._model else None
            is_opt = opt and opt.n_risers == cfg.n_risers
            if is_opt:
                self._stat_vars["status"].set("Optimal")
                self._status_label.config(
                    text=f"{cfg.n_risers - 1} steps ({cfg.n_risers} risers) — Optimal",
                    foreground=OPTIMAL_COLOR)
            else:
                self._stat_vars["status"].set("Valid")
                self._status_label.config(
                    text=f"{cfg.n_risers - 1} steps ({cfg.n_risers} risers) — Valid (not optimal)",
                    foreground="#005599")
        else:
            self._stat_vars["status"].set("Out of range")
            reasons = []
            if self._model:
                if not (self._model.min_rise <= cfg.riser_height <= self._model.max_rise):
                    reasons.append(
                        f"riser {cfg.riser_height:.2f}\" outside "
                        f"[{self._model.min_rise}\"–{self._model.max_rise}\"]")
                if not (self._model.min_tread <= cfg.tread_depth <= self._model.max_tread):
                    reasons.append(
                        f"tread {cfg.tread_depth:.2f}\" outside "
                        f"[{self._model.min_tread}\"–{self._model.max_tread}\"]")
            self._status_label.config(
                text="Out of range: " + "; ".join(reasons) if reasons else "Out of range",
                foreground=INVALID_COLOR)

    # ------------------------------------------------------------------
    # Comfort gauge
    # ------------------------------------------------------------------

    def _redraw_gauge(self, _=None):
        gc = self._gauge_canvas
        gc.delete("all")
        gw = gc.winfo_width() or 400
        gh = gc.winfo_height() or 18

        rot = self._current_rot

        # Background gradient zones (too steep | warn | ideal | warn | too shallow)
        # Map COMFORT_WARN_LO..COMFORT_WARN_HI onto the full gauge width
        full_lo  = COMFORT_WARN_LO - 2   # 20"  — extreme steep
        full_hi  = COMFORT_WARN_HI + 2   # 29"  — extreme shallow

        def rot_to_x(v):
            return max(0, min(gw, (v - full_lo) / (full_hi - full_lo) * gw))

        # Zone colors: red → orange → green → orange → red
        zones = [
            (full_lo,          COMFORT_WARN_LO,  "#E05050"),  # too steep
            (COMFORT_WARN_LO,  COMFORT_IDEAL_LO, "#E0A020"),  # borderline steep
            (COMFORT_IDEAL_LO, COMFORT_IDEAL_HI, "#40AA40"),  # ideal
            (COMFORT_IDEAL_HI, COMFORT_WARN_HI,  "#E0A020"),  # borderline shallow
            (COMFORT_WARN_HI,  full_hi,           "#E05050"),  # too shallow
        ]
        for z_lo, z_hi, color in zones:
            x0 = rot_to_x(z_lo)
            x1 = rot_to_x(z_hi)
            if x1 > x0:
                gc.create_rectangle(x0, 0, x1, gh, fill=color, outline="")

        # Zone boundary tick marks
        for v in (COMFORT_WARN_LO, COMFORT_IDEAL_LO, COMFORT_IDEAL_HI, COMFORT_WARN_HI):
            x = rot_to_x(v)
            gc.create_line(x, 0, x, gh, fill="#FFFFFF", width=1)
            gc.create_text(x, gh - 1, text=f"{v:.0f}\"", fill="#FFFFFF",
                           font=("Segoe UI", 6), anchor="s")

        # Labels at edges
        gc.create_text(2, gh // 2, text="Steep", fill="#FFFFFF",
                       font=("Segoe UI", 6), anchor="w")
        gc.create_text(gw - 2, gh // 2, text="Shallow", fill="#FFFFFF",
                       font=("Segoe UI", 6), anchor="e")

        if rot is None:
            self._comfort_label.config(text="—", foreground="#555555")
            return

        # Indicator needle
        needle_x = rot_to_x(rot)
        gc.create_line(needle_x, 0, needle_x, gh, fill="#000000", width=3)
        gc.create_polygon(
            needle_x - 5, 0, needle_x + 5, 0, needle_x, 7,
            fill="#000000", outline="")

        # Comfort label text
        if COMFORT_IDEAL_LO <= rot <= COMFORT_IDEAL_HI:
            label, color = "Ideal", OPTIMAL_COLOR
        elif COMFORT_WARN_LO <= rot < COMFORT_IDEAL_LO:
            label, color = "Slightly steep", "#CC7700"
        elif COMFORT_IDEAL_HI < rot <= COMFORT_WARN_HI:
            label, color = "Slightly shallow", "#CC7700"
        elif rot < COMFORT_WARN_LO:
            label, color = "Too steep", INVALID_COLOR
        else:
            label, color = "Too shallow", INVALID_COLOR

        self._comfort_label.config(text=f"2R+T = {rot:.2f}\"  —  {label}", foreground=color)

    # ------------------------------------------------------------------
    # Canvas drawing
    # ------------------------------------------------------------------

    def _redraw_canvas(self):
        c = self._canvas
        c.delete("all")

        # Background
        cw = c.winfo_width()  or CANVAS_WIDTH
        ch = c.winfo_height() or CANVAS_HEIGHT
        c.config(background=DIAGRAM_BG)

        if not self._model or self._selected_risers is None:
            c.create_text(cw / 2, ch / 2, text="No data", fill="#AAAAAA", font=("Segoe UI", 14))
            return

        cfg = self._find_config(self._selected_risers)
        if cfg is None:
            return

        n      = cfg.n_risers
        riser  = cfg.riser_height
        tread  = cfg.tread_depth
        total_rise = self._model.total_rise
        total_run  = self._model.total_run

        margin = CANVAS_MARGIN
        usable_w = cw - 2 * margin
        usable_h = ch - 2 * margin

        if usable_w <= 0 or usable_h <= 0:
            return

        scale = min(usable_w / total_run, usable_h / total_rise)

        # Origin: bottom-left of staircase in canvas coords
        ox = margin
        oy = ch - margin

        def px(phys_x, phys_y):
            """Physical inches → canvas pixels."""
            return ox + phys_x * scale, oy - phys_y * scale

        # Ground line
        gx1, gy1 = px(0, 0)
        gx2, gy2 = px(total_run, 0)
        c.create_line(gx1 - 4, gy1, gx2 + 4, gy2,
                      fill=GROUND_COLOR, width=2, dash=(4, 3))

        # Draw filled step rectangles
        # N risers, N-1 treads → treads indexed 0..N-2
        fill_color = STEP_FILL if cfg.is_valid else "#FFE0E0"
        for i in range(n - 1):
            x0, y0 = px(i * tread, i * riser)
            x1, y1 = px((i + 1) * tread, (i + 1) * riser)
            # Swap y because canvas y is inverted
            c.create_rectangle(x0, y1, x1, y0,
                                fill=fill_color, outline=STEP_OUTLINE, width=1)

        # Stair profile polyline
        points = list(px(0, 0))
        for i in range(n - 1):
            # horizontal tread (going right)
            points += list(px((i + 1) * tread, i * riser))
            # vertical riser (going up)
            points += list(px((i + 1) * tread, (i + 1) * riser))
        # top landing edge (top-right)
        tx, ty = px(total_run, total_rise)
        points += [tx, ty]
        c.create_line(points, fill=STEP_OUTLINE, width=2, joinstyle="miter")

        # Vertical wall line (left side)
        lx0, ly0 = px(0, 0)
        lx1, ly1 = px(0, total_rise)
        c.create_line(lx0, ly0, lx1, ly1, fill=STEP_OUTLINE, width=2)

        # Dimension: riser arrow on first riser
        rx, ry_bot = px(0, 0)
        rx, ry_top = px(0, riser)
        arm_x = rx - 18
        c.create_line(arm_x, ry_bot, arm_x, ry_top,
                      arrow=tk.BOTH, fill=LABEL_COLOR, width=1)
        c.create_text(arm_x - 4, (ry_bot + ry_top) / 2,
                      text=f"{riser:.2f}\"", fill=LABEL_COLOR,
                      font=("Segoe UI", 7), anchor="e")

        # Dimension: tread arrow on first tread (if N > 1)
        if n > 1:
            tx_left, ty_h = px(0, riser)
            tx_right, _   = px(tread, riser)
            arm_y = ty_h + 18
            c.create_line(tx_left, arm_y, tx_right, arm_y,
                          arrow=tk.BOTH, fill=LABEL_COLOR, width=1)
            c.create_text((tx_left + tx_right) / 2, arm_y + 10,
                          text=f"{tread:.2f}\"", fill=LABEL_COLOR,
                          font=("Segoe UI", 7))

        # ── Overall dimensions ─────────────────────────────────────────
        dim_color = "#444455"
        tick = 6

        # Right-side dimension: ground → landing (total rise)
        dim_offset_x = 38  # pixels right of the stair right edge
        land_cx, land_cy = px(total_run, total_rise)
        rs_bot_cx, rs_bot_cy = px(total_run, 0)
        rdim_x = land_cx + dim_offset_x
        # Extension lines
        c.create_line(land_cx, land_cy, rdim_x + tick, land_cy, fill=dim_color, width=1)
        c.create_line(rs_bot_cx, rs_bot_cy, rdim_x + tick, rs_bot_cy, fill=dim_color, width=1)
        # Arrow
        c.create_line(rdim_x, rs_bot_cy, rdim_x, land_cy,
                      arrow=tk.BOTH, fill=dim_color, width=1)
        # Label
        c.create_text(rdim_x + tick + 3, (land_cy + rs_bot_cy) / 2,
                      text=f"Total Rise\n{total_rise:.2f}\"",
                      fill=dim_color, font=("Segoe UI", 7), anchor="w")

        # Bottom dimension: total run
        dim_offset_y = 30
        bx_left,  by_bot = px(0,         0)
        bx_right, _      = px(total_run, 0)
        bdim_y = by_bot + dim_offset_y
        c.create_line(bx_left,  by_bot, bx_left,  bdim_y + tick, fill=dim_color, width=1)
        c.create_line(bx_right, by_bot, bx_right, bdim_y + tick, fill=dim_color, width=1)
        c.create_line(bx_left, bdim_y, bx_right, bdim_y,
                      arrow=tk.BOTH, fill=dim_color, width=1)
        c.create_text((bx_left + bx_right) / 2, bdim_y + tick + 2,
                      text=f"Total Run: {total_run:.2f}\"",
                      fill=dim_color, font=("Segoe UI", 7), anchor="n")

        # ── 2×12 Stringer ─────────────────────────────────────────────
        # Geometry conventions:
        #   • BOARD_W_IN = 11.25" (actual 2×12 width, measured along the face)
        #   • "Mid-board placement": the step notch corner (riser-tread junction)
        #     sits exactly on the top face of the board, centred in the board
        #     width.  Tread-seat cut depth = HALF_W from top face (horizontal);
        #     riser-seat cut depth = HALF_W from back face (vertical).
        #   • The top face of the board passes through all riser-tread corners.
        #   • End cuts are PLUMB (vertical), not square to the board.
        #
        # Coordinate system (physical inches, origin = stair bottom-left):
        #   x → run direction,  y → rise direction (up)
        #   The stringer centre-line runs from (0,0) to (total_run, total_rise).
        #   Top face = centre-line offset HALF_W in the +perp direction (above).
        #   Bottom face = centre-line offset HALF_W in the -perp direction.
        #
        # Perpendicular direction (physical, pointing "above" the top face):
        #   perp_phys = (-sin θ,  cos θ)  where θ = atan2(rise, run)
        #   In canvas coords (y flipped): perp_canvas = (sin θ · s, -cos θ · s)
        BOARD_W_IN = 11.25   # actual 2×12 width along board face
        HALF_W     = BOARD_W_IN / 2.0

        import math as _math
        angle = _math.atan2(total_rise, total_run)
        cos_a, sin_a = _math.cos(angle), _math.sin(angle)

        # Canvas-space helpers: offsets from a reference point.
        def along(dist_in):
            """Along-stringer offset (canvas px)."""
            return dist_in * cos_a * scale, -dist_in * sin_a * scale

        def perp(dist_in):
            """Perpendicular-to-stringer offset, +ve = above top face (canvas px)."""
            return dist_in * sin_a * scale, -dist_in * cos_a * scale

        # Plumb (vertical in physical space) offset — used for end cuts.
        def plumb(dist_in):
            """Vertical offset in physical space (canvas px)."""
            return 0.0, -dist_in * scale

        stringer_len_in = cfg.stringer_length

        # --- Position the stringer so its TOP FACE passes through the corners ---
        # The riser-tread corner for step i (1-indexed) is at physical
        # (i*tread, i*riser).  The stringer top face is the line through all
        # those corners, which in the normalised frame is simply the diagonal
        # itself (they're collinear by definition).
        #
        # So: top-face line = the (0,0)→(total_run, total_rise) diagonal.
        # Centre-line = top face offset HALF_W downward (below face).
        # Origin for drawing: bottom-left corner (0,0) in physical space,
        # shifted HALF_W below the top face.
        #
        # Canvas anchor for the centre-line start:
        ref_cx, ref_cy = px(0, 0)   # top-face at x=0 is physical (0, 0)
        # centre-line start = top-face start offset HALF_W below (perp -HALF_W)
        cl_x0 = ref_cx + perp(-HALF_W)[0]
        cl_y0 = ref_cy + perp(-HALF_W)[1]
        # centre-line end
        cl_x1 = ref_cx + along(stringer_len_in)[0] + perp(-HALF_W)[0]
        cl_y1 = ref_cy + along(stringer_len_in)[1] + perp(-HALF_W)[1]

        # Helper: canvas position of a point on the CENTRE-LINE at arc-length d
        def cl_pt(d_in):
            return cl_x0 + along(d_in)[0], cl_y0 + along(d_in)[1]

        # Helper: canvas position on the TOP FACE at arc-length d
        def top_pt(d_in):
            cx, cy = cl_pt(d_in)
            return cx + perp(HALF_W)[0], cy + perp(HALF_W)[1]

        # Helper: canvas position on the BOTTOM FACE at arc-length d
        def bot_pt(d_in):
            cx, cy = cl_pt(d_in)
            return cx + perp(-HALF_W)[0], cy + perp(-HALF_W)[1]

        # --- Build the stringer outline polygon with PLUMB end cuts ---
        # Bottom plumb cut:
        #   The stringer bottom-end sits on the floor (y=0 physical).
        #   The plumb cut intersects: top face at x_top_bot, bottom face at x_bot_bot.
        #
        # The top face in physical coords: y = x * tan(θ)  →  the top-face
        # points trace the stair diagonal exactly (they ARE at y = x*tan θ).
        # At the bottom end the plumb cut is at x = 0 (left wall / floor junction).
        # Top-face point at x=0 → physical (0, 0), which IS the stair corner.
        # Bottom-face point: same x=0, but BOARD_W_IN lower along the board →
        #   physical offset from top = (-sin θ * BOARD_W_IN, -cos θ * BOARD_W_IN)
        #   but a plumb cut is vertical, so we need the x where the bottom face
        #   intersects x = 0 (plumb cut plane).
        #
        # Bottom face equation (physical): y = x*tan(θ) - BOARD_W_IN / cos(θ)
        #   (shifted BOARD_W_IN perpendicular below top face)
        # At x=0: y_bot_bottom_face = -BOARD_W_IN / cos(θ)  (below ground, clipped)
        # We draw the plumb cut from the top-face point down to the ground (y=0),
        # then along the ground to where the bottom face hits ground level.
        #
        # Bottom face hits y=0: 0 = x*tan(θ) - BOARD_W_IN/cos(θ)
        #   x_ground = BOARD_W_IN / sin(θ)   (run distance from origin)
        #
        # So the bottom-end outline (in physical coords) is:
        #   top-face at x=0: (0, 0)
        #   plumb down to ground: (0, 0)  — same point, it's the stair origin
        #   along ground to: (BOARD_W_IN/sin θ, 0)
        #   up the bottom face to where it meets the board proper.
        # But for simplicity we just clip the bottom to the ground line.
        #
        # For the top end (plumb cut at x = total_run):
        #   top-face at x=total_run: physical (total_run, total_rise)
        #   bottom-face at plumb x=total_run: y = total_run*tan θ - BOARD_W_IN/cos θ
        #   = total_rise - BOARD_W_IN/cos θ   (which is below total_rise)
        #
        # Build the polygon as a series of physical points, convert to canvas.
        # We use 6 vertices (hexagon for plumb-cut board):
        #
        #  P0 (top-face, bottom-end)    = (0,            0)
        #  P1 (top-face, top-end)       = (total_run,    total_rise)
        #  P2 (bot-face, top-end plumb) = (total_run,    total_rise - BW/cos θ)
        #  P3 (bot-face along bottom run back to where it hits ground if needed,
        #       otherwise straight to P4)
        #  P4 (ground at x = BW/sin θ)                      ← bottom foot
        #  P5 (origin / ground at x=0) — only if top face starts above ground

        BW_div_cos = BOARD_W_IN / cos_a      # vertical drop across board width
        BW_div_sin = BOARD_W_IN / sin_a      # horizontal run across board width

        # Physical vertices
        poly_phys = [
            (0.0,        0.0),                          # P0 top-face bottom-end
            (total_run,  total_rise),                   # P1 top-face top-end
            (total_run,  total_rise - BW_div_cos),      # P2 bottom-face top-end (plumb)
            (BW_div_sin, 0.0),                          # P3 bottom-face hits ground
        ]
        # Convert to canvas coords
        poly_canvas = []
        for (px_phys, py_phys) in poly_phys:
            cx_pt, cy_pt = px(px_phys, py_phys)
            poly_canvas.extend([cx_pt, cy_pt])

        c.create_polygon(poly_canvas,
                         fill="#D4B896", outline="#7A5533", width=2,
                         stipple="gray50")

        # ── Stringer board: dimension all 4 sides ──────────────────────
        # The cut stringer is a 4-sided shape (parallelogram with plumb ends):
        #   P0 = (0, 0)                         top-face, bottom-end (stair origin)
        #   P1 = (total_run, total_rise)         top-face, top-end
        #   P2 = (total_run, total_rise-BW/cosθ) bottom-face, top-end (plumb cut)
        #   P3 = (BW/sinθ, 0)                   bottom-face, bottom-end (at ground)
        #
        # Side lengths:
        #   P0→P1 (top face)    = stringer_length  (hypotenuse)
        #   P1→P2 (top plumb)   = BW_div_cos        (vertical height of top cut)
        #   P2→P3 (bottom face) = stringer_length  (parallel to top)
        #   P3→P0 (bottom foot) = BW_div_sin        (horizontal run at base)
        #
        # Canvas coords of all four corners
        P0cx, P0cy = px(0.0,        0.0)
        P1cx, P1cy = px(total_run,  total_rise)
        P2cx, P2cy = px(total_run,  total_rise - BW_div_cos)
        P3cx, P3cy = px(BW_div_sin, 0.0)

        str_col = "#7A5533"
        sdim_gap = 24   # pixels gap between face and dimension line

        # --- Side 1: top face P0→P1 (offset straight up in canvas) ---
        sl_ft = cfg.stringer_length / 12.0
        tfd_x0, tfd_y0 = P0cx, P0cy - sdim_gap
        tfd_x1, tfd_y1 = P1cx, P1cy - sdim_gap
        c.create_line(P0cx, P0cy, tfd_x0, tfd_y0, fill=str_col, width=1)
        c.create_line(P1cx, P1cy, tfd_x1, tfd_y1, fill=str_col, width=1)
        c.create_line(tfd_x0, tfd_y0, tfd_x1, tfd_y1, arrow=tk.BOTH, fill=str_col, width=1)
        tfd_mx, tfd_my = (tfd_x0 + tfd_x1) / 2, (tfd_y0 + tfd_y1) / 2
        c.create_text(tfd_mx, tfd_my - 6,
                      text=f"Top face: {cfg.stringer_length:.2f}\" ({sl_ft:.2f} ft)",
                      fill=str_col, font=("Segoe UI", 7), anchor="s")

        # --- Side 2: top plumb cut P1→P2 (to the right of the cut) ---
        tp_off = 14  # pixels to the right in canvas x
        tpc_x0, tpc_y0 = P1cx + tp_off, P1cy
        tpc_x1, tpc_y1 = P2cx + tp_off, P2cy
        c.create_line(P1cx, P1cy, tpc_x0, tpc_y0, fill=str_col, width=1)
        c.create_line(P2cx, P2cy, tpc_x1, tpc_y1, fill=str_col, width=1)
        c.create_line(tpc_x0, tpc_y0, tpc_x1, tpc_y1, arrow=tk.BOTH, fill=str_col, width=1)
        c.create_text(tpc_x0 + 3, (tpc_y0 + tpc_y1) / 2,
                      text=f"{BW_div_cos:.2f}\"", fill=str_col,
                      font=("Segoe UI", 7), anchor="w")

        # --- Side 3: bottom face P2→P3 (offset straight down in canvas) ---
        bfd_x0, bfd_y0 = P3cx, P3cy + sdim_gap
        bfd_x1, bfd_y1 = P2cx, P2cy + sdim_gap
        c.create_line(P3cx, P3cy, bfd_x0, bfd_y0, fill=str_col, width=1)
        c.create_line(P2cx, P2cy, bfd_x1, bfd_y1, fill=str_col, width=1)
        c.create_line(bfd_x0, bfd_y0, bfd_x1, bfd_y1, arrow=tk.BOTH, fill=str_col, width=1)
        bfd_mx, bfd_my = (bfd_x0 + bfd_x1) / 2, (bfd_y0 + bfd_y1) / 2
        c.create_text(bfd_mx, bfd_my + 6,
                      text=f"Bottom face: {cfg.stringer_length:.2f}\" ({sl_ft:.2f} ft)",
                      fill=str_col, font=("Segoe UI", 7), anchor="n")

        # --- Side 4: bottom foot P3→P0 (horizontal at ground, below) ---
        foot_off = 14   # pixels below ground line
        ffd_x0, ffd_y0 = P3cx, P3cy + foot_off
        ffd_x1, ffd_y1 = P0cx, P0cy + foot_off
        c.create_line(P3cx, P3cy, ffd_x0, ffd_y0, fill=str_col, width=1)
        c.create_line(P0cx, P0cy, ffd_x1, ffd_y1, fill=str_col, width=1)
        c.create_line(ffd_x0, ffd_y0, ffd_x1, ffd_y1, arrow=tk.BOTH, fill=str_col, width=1)
        c.create_text((ffd_x0 + ffd_x1) / 2, ffd_y0 + 3,
                      text=f"Foot: {BW_div_sin:.2f}\"",
                      fill=str_col, font=("Segoe UI", 7), anchor="n")

        # Centre-line (mid-board reference) — from P0+perp(-HALF_W) to P1+perp(-HALF_W)
        # In physical space the centre-line midpoint at each end:
        #   bottom: physical (0,0) offset HALF_W perpendicular below top face
        #   top:    physical (total_run, total_rise) offset similarly
        ml_x0_c, ml_y0_c = px(0, 0)
        ml_x1_c, ml_y1_c = px(total_run, total_rise)
        # Offset both ends HALF_W perpendicular (below top face = perp(-HALF_W))
        ml_x0_c += perp(-HALF_W)[0]; ml_y0_c += perp(-HALF_W)[1]
        ml_x1_c += perp(-HALF_W)[0]; ml_y1_c += perp(-HALF_W)[1]
        c.create_line(ml_x0_c, ml_y0_c, ml_x1_c, ml_y1_c,
                      fill="#7A5533", width=1, dash=(4, 3))

        # --- Step notch cut lines ---
        # Each riser-tread corner is at physical (i*tread, i*riser) on the TOP FACE.
        # Mid-board notch: tread seat cuts HALF_W deep (horizontal, perpendicular
        # to stringer length) and riser seat cuts HALF_W deep (vertical, plumb).
        # We draw the L-shaped notch outline on the board face.
        NOTCH_COLOR = "#CC4400"

        for i in range(1, n):
            corner_px = i * tread   # physical x of riser-tread corner
            corner_py = i * riser   # physical y

            # Corner canvas position (on top face)
            cnr_cx, cnr_cy = px(corner_px, corner_py)

            # Tread seat: horizontal cut (constant y = corner_py) going back
            # along the stringer by HALF_W in the perpendicular direction.
            # End of tread seat on the centre-line (perp HALF_W below corner):
            ts_cx = cnr_cx + perp(-HALF_W)[0]
            ts_cy = cnr_cy + perp(-HALF_W)[1]

            # Riser seat: vertical (plumb) cut going down from corner by
            # HALF_W perpendicular.  Bottom of riser seat = same point ts.
            # We represent the riser as a line from the corner straight down
            # to the centre-line level (HALF_W below along-board direction).
            rs_cx = cnr_cx + perp(-HALF_W)[0]
            rs_cy = cnr_cy + perp(-HALF_W)[1]

            # Draw the L: tread arm (horizontal across board, perp direction)
            c.create_line(cnr_cx, cnr_cy, ts_cx, ts_cy,
                          fill=NOTCH_COLOR, width=1, dash=(3, 2))
            # Riser arm (plumb, from corner down to board bottom face)
            rs_bot_cx = cnr_cx + perp(-HALF_W)[0]
            rs_bot_cy = cnr_cy + perp(-HALF_W)[1]
            c.create_line(cnr_cx, cnr_cy, rs_bot_cx, rs_bot_cy,
                          fill=NOTCH_COLOR, width=1, dash=(3, 2))

            # Small dot at the notch corner (centre-line intersection)
            r_dot = 2
            c.create_oval(ts_cx - r_dot, ts_cy - r_dot,
                          ts_cx + r_dot, ts_cy + r_dot,
                          fill=NOTCH_COLOR, outline="")

            # Riser label above the top face
            if i <= 9:   # avoid crowding on many steps
                lbl_cx = cnr_cx + perp(4)[0]
                lbl_cy = cnr_cy + perp(4)[1]
                c.create_text(lbl_cx, lbl_cy,
                              text=f"R{i}", fill=NOTCH_COLOR,
                              font=("Segoe UI", 6), anchor="sw")

        # --- Bottom bearing indicator ---
        # Small vertical line at x=0 on the ground to show the plumb bottom cut.
        bear_cx, bear_cy = px(0, 0)
        c.create_line(bear_cx, bear_cy, bear_cx, bear_cy + 8,
                      fill="#7A5533", width=3)
        c.create_text(bear_cx + 3, bear_cy + 10,
                      text="⊥", fill="#7A5533",
                      font=("Segoe UI", 7), anchor="n")

        # (stringer length label moved to the dimension line below the board)

        # Intermediate support markers along the stringer centre-line
        if cfg.support_count > 0:
            for i in range(1, cfg.support_count + 1):
                t_frac = i / (cfg.support_count + 1)
                sup_phys_x = t_frac * total_run
                sup_phys_y = t_frac * total_rise
                scx_top, scy_top = px(sup_phys_x, sup_phys_y)
                # Place on centre-line (HALF_W below top face)
                scx = scx_top + perp(-HALF_W)[0]
                scy = scy_top + perp(-HALF_W)[1]
                r = 5
                c.create_oval(scx - r, scy - r, scx + r, scy + r,
                              fill="#FF8800", outline="#884400", width=1)
                c.create_text(scx + r + 2, scy, text=f"S{i}",
                              fill="#884400", font=("Segoe UI", 6), anchor="w")

        # ── Stair angle arc indicator ──────────────────────────────────
        # Draw a protractor-style arc at the bottom-left corner of the stair
        # from horizontal (0°) up to the stringer angle, with colour coding.
        import math as _math
        ang_deg = _math.degrees(angle)   # angle already computed above

        # Arc radius in pixels — scale with canvas size but keep readable
        arc_r = max(28, min(50, usable_w * 0.08))

        # Canvas origin of the arc = bottom-left stair corner
        arc_ox, arc_oy = px(0, 0)

        # tkinter create_arc uses a bounding box; arc goes CCW from start angle.
        # tk angles: 0° = 3-o'clock (east), positive = CCW.
        # Stringer goes from horizontal (east=0°) up by ang_deg.
        arc_start = 0          # east (horizontal ground line)
        arc_extent = ang_deg   # sweep CCW up to stringer angle

        # Choose colour by zone
        if ANGLE_IDEAL_LO <= ang_deg <= ANGLE_IDEAL_HI:
            arc_color = "#40AA40"
        elif ANGLE_WARN_LO <= ang_deg <= ANGLE_WARN_HI:
            arc_color = "#E0A020"
        else:
            arc_color = "#E05050"

        # Filled pie-slice (style=tk.PIESLICE) for the angle zone
        c.create_arc(
            arc_ox - arc_r, arc_oy - arc_r,
            arc_ox + arc_r, arc_oy + arc_r,
            start=arc_start, extent=arc_extent,
            style=tk.PIESLICE,
            fill=arc_color, outline=arc_color, width=0,
            stipple="gray25",
        )
        # Arc outline in the same colour, slightly bolder
        c.create_arc(
            arc_ox - arc_r, arc_oy - arc_r,
            arc_ox + arc_r, arc_oy + arc_r,
            start=arc_start, extent=arc_extent,
            style=tk.ARC,
            outline=arc_color, width=2,
        )

        # Radial line along the stringer direction (top edge of arc)
        rad_end_x = arc_ox + arc_r * _math.cos(_math.radians(ang_deg))
        rad_end_y = arc_oy - arc_r * _math.sin(_math.radians(ang_deg))
        c.create_line(arc_ox, arc_oy, rad_end_x, rad_end_y,
                      fill=arc_color, width=1)

        # Angle text label at mid-arc, just outside the arc
        label_r = arc_r + 10
        mid_ang_rad = _math.radians(ang_deg / 2)
        lbl_x = arc_ox + label_r * _math.cos(mid_ang_rad)
        lbl_y = arc_oy - label_r * _math.sin(mid_ang_rad)
        c.create_text(lbl_x, lbl_y,
                      text=f"{ang_deg:.1f}°",
                      fill=arc_color, font=("Segoe UI", 7, "bold"),
                      anchor="w")

        # Step count label (above top landing)
        lx, ly = px(total_run / 2, total_rise)
        status_text = f"{n - 1} steps"
        status_color = OPTIMAL_COLOR if cfg.is_valid else INVALID_COLOR
        c.create_text(lx, ly - 6, text=status_text,
                      fill=status_color, font=("Segoe UI", 10, "bold"), anchor="s")

        # Step detail inset
        self._draw_step_detail(c, cw, ch, cfg)

        # Materials list (upper-left, below the step detail inset)
        self._draw_materials_list(c, cw, ch, cfg)

    # ------------------------------------------------------------------
    # Step detail inset
    # ------------------------------------------------------------------

    def _draw_step_detail(self, c: tk.Canvas, cw: int, ch: int,
                          cfg: "StepConfig"):
        """Draw a circular inset in the upper-left showing a single zoomed step."""
        riser = cfg.riser_height
        tread = cfg.tread_depth
        rot   = cfg.rule_of_thumb

        # Inset geometry — inside the lower-right corner of the stair chart,
        # where the rise and run dimension lines meet.
        radius = 75
        if self._model:
            total_run  = self._model.total_run
            total_rise = self._model.total_rise
            margin = CANVAS_MARGIN
            usable_w = cw - 2 * margin
            usable_h = ch - 2 * margin
            scale = min(usable_w / total_run, usable_h / total_rise) if total_run and total_rise else 1
            # Anchor to the rise dim line (right) and ground line (bottom)
            right_x = margin + total_run * scale + 32  # just inside rise dim line
            ground_y = ch - margin                     # the dashed ground line
            cx = right_x - radius
            cy = ground_y - radius
        else:
            cx = cw - CANVAS_MARGIN - radius - 4
            cy = ch - CANVAS_MARGIN - radius - 4

        # Background circle
        c.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                      fill="#F0F0F0", outline="#999999", width=1)

        # Fit the step inside the circle with padding
        pad = 22          # leave room for dimension arrows + labels
        draw_w = radius * 2 - pad * 2   # available width for tread
        draw_h = radius * 2 - pad * 2   # available height for riser
        # Reserve top slice for the 2R+T label
        label_reserve = 14
        draw_h -= label_reserve

        # Scale so both riser and tread fit
        s = min(draw_w / tread, draw_h / riser)

        step_w = tread * s   # pixels for tread
        step_h = riser * s   # pixels for riser

        # Position the step L-shape: bottom-left corner of the step
        # Center the step within the available area (below the label reserve)
        avail_cx = cx
        avail_cy = cy + label_reserve / 2
        sx0 = avail_cx - step_w / 2   # left edge of tread
        sy1 = avail_cy + step_h / 2   # bottom of riser (lower tread surface)
        sx1 = sx0 + step_w            # right edge of tread
        sy0 = sy1 - step_h            # top of riser

        # Draw the L-shaped step profile (filled)
        # The step: vertical riser on the left, horizontal tread on the bottom
        c.create_rectangle(sx0, sy0, sx1, sy1,
                           fill=STEP_FILL, outline=STEP_OUTLINE, width=2)

        # Riser dimension arrow (right side)
        arr_x = sx1 + 8
        c.create_line(arr_x, sy1, arr_x, sy0,
                      arrow=tk.BOTH, fill=LABEL_COLOR, width=1)
        c.create_text(arr_x + 3, (sy0 + sy1) / 2,
                      text=f"{riser:.3f}\"", fill=LABEL_COLOR,
                      font=("Segoe UI", 7), anchor="w")

        # Tread dimension arrow (below)
        arr_y = sy1 + 8
        c.create_line(sx0, arr_y, sx1, arr_y,
                      arrow=tk.BOTH, fill=LABEL_COLOR, width=1)
        c.create_text((sx0 + sx1) / 2, arr_y + 3,
                      text=f"{tread:.3f}\"", fill=LABEL_COLOR,
                      font=("Segoe UI", 7), anchor="n")

        # 2R+T label at the top of the inset
        c.create_text(cx, cy - radius + 10,
                      text=f"2R+T = {rot:.2f}\"",
                      fill="#444455", font=("Segoe UI", 7, "bold"))

    # ------------------------------------------------------------------
    # Materials list
    # ------------------------------------------------------------------

    def _draw_materials_list(self, c: tk.Canvas, cw: int, ch: int,
                             cfg: "StepConfig"):
        """Draw a materials summary box in the upper-left area below the step inset."""
        import math as _math

        n_risers = cfg.n_risers
        n_treads = n_risers - 1  # tread count = step count (risers - 1)
        stringer_count = self._stringer_count
        stair_width = self._stair_width
        board_w = self._tread_board_width

        # How many boards per tread to cover the stair width?
        boards_per_tread = _math.ceil(stair_width / board_w)
        total_tread_boards = boards_per_tread * n_treads

        # Each tread board length = tread depth + nose overhang (~1")
        # but we just report tread depth as the cut length
        tread_cut_len = cfg.tread_depth

        # Stringer lumber: next standard length >= stringer_length
        sl_ft = cfg.stringer_length / 12.0
        standard_lengths = [8, 10, 12, 14, 16, 18, 20]
        stringer_lumber_ft = standard_lengths[-1]
        for slen in standard_lengths:
            if slen >= sl_ft:
                stringer_lumber_ft = slen
                break

        # Position: upper-left of the diagram
        box_x = CANVAS_MARGIN + 4
        box_y = CANVAS_MARGIN + 4
        line_h = 18
        hdr_font = ("Segoe UI", 10, "bold")
        body_font = ("Segoe UI", 9)
        hdr_color = "#333344"
        body_color = "#444455"

        # Header
        c.create_text(box_x, box_y, text="Materials List",
                      fill=hdr_color, font=hdr_font, anchor="nw")
        y = box_y + line_h + 2

        # Separator line
        c.create_line(box_x, y - 2, box_x + 180, y - 2,
                      fill="#AAAAAA", width=1)

        # Stringers
        c.create_text(box_x, y, text="Stringers:",
                      fill=hdr_color, font=("Segoe UI", 9, "bold"), anchor="nw")
        y += line_h
        c.create_text(box_x + 8, y,
                      text=f"{stringer_count}x  2x12 x {stringer_lumber_ft}' ",
                      fill=body_color, font=body_font, anchor="nw")
        y += line_h

        # Treads
        c.create_text(box_x, y, text="Treads:",
                      fill=hdr_color, font=("Segoe UI", 9, "bold"), anchor="nw")
        y += line_h

        # Find the board label for current width
        board_label = f"{board_w}\""
        from constants import TREAD_BOARD_OPTIONS
        for lbl, w in TREAD_BOARD_OPTIONS.items():
            if abs(w - board_w) < 0.01:
                # Extract just the dimension part e.g. "1x6"
                board_label = lbl.split(" ")[0]
                break

        if boards_per_tread == 1:
            c.create_text(box_x + 8, y,
                          text=f"{n_treads}x  {board_label} x {tread_cut_len:.1f}\"",
                          fill=body_color, font=body_font, anchor="nw")
        else:
            c.create_text(box_x + 8, y,
                          text=f"{total_tread_boards}x  {board_label} x {tread_cut_len:.1f}\"",
                          fill=body_color, font=body_font, anchor="nw")
            y += line_h
            c.create_text(box_x + 8, y,
                          text=f"({boards_per_tread} boards/tread x {n_treads} treads)",
                          fill="#777777", font=("Segoe UI", 8), anchor="nw")
        y += line_h

        # Width coverage note
        actual_coverage = boards_per_tread * board_w
        overhang = actual_coverage - stair_width
        if overhang > 0.1:
            c.create_text(box_x + 8, y,
                          text=f"Rip last board by {overhang:.2f}\"",
                          fill="#996600", font=("Segoe UI", 8), anchor="nw")
