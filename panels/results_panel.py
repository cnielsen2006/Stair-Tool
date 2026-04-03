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

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._model: Optional[StairModel] = None
        self._selected_risers: Optional[int]   = None
        self._all_configs = []
        self._current_rot: Optional[float] = None  # 2R+T value (read by app.py)

        self._stringer_count: int = 3
        self._stair_width: float = 36.0
        self._tread_board_width: float = 5.5
        self._tread_board_label: str = ""
        self._tread_board_gap: float = 0.25
        self._nosing_overhang: float = 0.75
        self._stringer_lumber_ft: int = 0  # 0 = auto
        self._bottom_plumb_cut: bool = False
        self._steps_range = (2, 50, [])  # (n_lo, n_hi, valid_ns)

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

        self._status_label = None  # removed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, model: StairModel, selected_risers: Optional[int],
               stringer_count: int = 3, stair_width: float = 36.0,
               tread_board_width: float = 5.5, tread_board_label: str = "",
               tread_board_gap: float = 0.25, nosing_overhang: float = 0.75,
               stringer_lumber_ft: int = 0, bottom_plumb_cut: bool = False):
        self._model      = model
        self._stringer_count = stringer_count
        self._stair_width = stair_width
        self._tread_board_width = tread_board_width
        self._tread_board_label = tread_board_label
        self._tread_board_gap = tread_board_gap
        self._nosing_overhang = nosing_overhang
        self._stringer_lumber_ft = stringer_lumber_ft
        self._bottom_plumb_cut = bottom_plumb_cut
        self._all_configs = model.compute_configs()
        valid_ns = [c.n_risers for c in self._all_configs if c.is_valid]

        # Determine valid range for the spinbox (managed by input_panel now)
        all_ns = [c.n_risers for c in self._all_configs]
        n_lo = min(all_ns) if all_ns else 2
        n_hi = max(all_ns) if all_ns else 50
        if selected_risers is not None:
            n_lo = min(n_lo, selected_risers)
            n_hi = max(n_hi, selected_risers)

        # Resolve selected N (risers)
        if selected_risers is not None:
            self._selected_risers = selected_risers
        elif valid_ns:
            opt = model.optimal_config()
            self._selected_risers = opt.n_risers if opt else valid_ns[0]
        else:
            self._selected_risers = self._all_configs[len(self._all_configs)//2].n_risers \
                if self._all_configs else 2

        # Return range info so the caller can update the input panel spinbox
        self._steps_range = (n_lo, n_hi, valid_ns)
        self._refresh()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
            stringer_top_y = (n - 1) * riser
            stringer_len = math.sqrt(stringer_top_y**2 + self._model.total_run**2)
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
            self._current_rot = None
            return

        self._stat_vars["riser"].set(f"{cfg.riser_height:.3f}\"")
        self._stat_vars["tread"].set(f"{cfg.tread_depth:.3f}\"")
        rot = cfg.rule_of_thumb
        self._current_rot = rot

        # Include comfort rating inline with the 2R+T value
        if COMFORT_IDEAL_LO <= rot <= COMFORT_IDEAL_HI:
            comfort = "Ideal"
        elif COMFORT_WARN_LO <= rot < COMFORT_IDEAL_LO:
            comfort = "Slightly steep"
        elif COMFORT_IDEAL_HI < rot <= COMFORT_WARN_HI:
            comfort = "Slightly shallow"
        elif rot < COMFORT_WARN_LO:
            comfort = "Too steep"
        else:
            comfort = "Too shallow"
        self._stat_vars["rot"].set(f"{rot:.2f}\" — {comfort}")

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

        # Stringer info (length varies with N since slope = riser/tread)
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
            self._stat_vars["status"].set("Optimal" if is_opt else "Valid")
        else:
            self._stat_vars["status"].set("Out of range")

    # ------------------------------------------------------------------
    # Comfort gauge
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
        #   The stringer centre-line runs from (0,0) to (total_run, stringer_top_y).
        #   Top face = centre-line offset HALF_W in the +perp direction (above).
        #   Bottom face = centre-line offset HALF_W in the -perp direction.
        #
        # Perpendicular direction (physical, pointing "above" the top face):
        #   perp_phys = (-sin θ,  cos θ)  where θ = atan2(rise, run)
        #   In canvas coords (y flipped): perp_canvas = (sin θ · s, -cos θ · s)
        BOARD_W_IN = 11.25   # actual 2×12 width along board face
        HALF_W     = BOARD_W_IN / 2.0

        import math as _math
        # The stringer top face must pass through the step corners at
        # (i*tread, i*riser).  Their slope is riser/tread, which differs
        # from total_rise/total_run because N risers but only N-1 treads.
        angle = _math.atan2(riser, tread)
        cos_a, sin_a = _math.cos(angle), _math.sin(angle)

        # The stringer top face at x=total_run reaches y=(N-1)*riser,
        # NOT total_rise (which is N*riser).  The last riser from there
        # up to the landing is part of the stair, not the stringer slope.
        stringer_top_y = (n - 1) * riser

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

        # ── Stringer geometry: determine bottom-end shape ────────────────
        BW_div_cos = BOARD_W_IN / cos_a      # vertical drop across board width
        BW_div_sin = BOARD_W_IN / sin_a      # horizontal run across board width

        # Physical vertices — bottom end changes depending on plumb cut option
        if self._bottom_plumb_cut:
            # Plumb cut at first step corner (x=tread), then level seat on ground.
            # 5-vertex polygon:
            #   P0 = (tread, riser)     top-face at first step corner
            #   P1 = top-face top-end   (unchanged)
            #   P2 = bottom-face top    (unchanged)
            #   P3 = (BW/sinθ, 0)       bottom-face meets ground
            #   P4 = (tread, 0)         ground at plumb cut
            P0_phys = (tread,       riser)
            P3_phys = (BW_div_sin,  0.0)
            P4_phys = (tread,       0.0)
        else:
            # Default: stringer tapers to a point, bottom face hits ground
            P0_phys = (0.0,        0.0)
            P3_phys = (BW_div_sin, 0.0)
            P4_phys = None  # not used

        # --- Position the stringer so its TOP FACE passes through the corners ---
        # Canvas anchor for centre-line start (top-face bottom-end):
        ref_cx, ref_cy = px(P0_phys[0], P0_phys[1])
        # centre-line start = top-face start offset HALF_W below (perp -HALF_W)
        cl_x0 = ref_cx + perp(-HALF_W)[0]
        cl_y0 = ref_cy + perp(-HALF_W)[1]

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

        # --- Build the stringer outline polygon ---
        poly_phys = [
            P0_phys,                                            # P0 top-face bottom-end
            (total_run,  stringer_top_y),                       # P1 top-face top-end
            (total_run,  stringer_top_y - BW_div_cos),          # P2 bottom-face top-end (plumb)
            P3_phys,                                            # P3 bottom-face bottom-end
        ]
        if P4_phys is not None:
            poly_phys.append(P4_phys)                           # P4 ground at plumb cut
        # Convert to canvas coords
        poly_canvas = []
        for (px_phys, py_phys) in poly_phys:
            cx_pt, cy_pt = px(px_phys, py_phys)
            poly_canvas.extend([cx_pt, cy_pt])

        c.create_polygon(poly_canvas,
                         fill="#D4B896", outline="#7A5533", width=2,
                         stipple="gray50")

        # ── Stringer board: dimension all 4 sides ──────────────────────
        # The cut stringer is a 4-sided shape:
        #   P0 = (0, 0)                              top-face, bottom-end
        #   P1 = (total_run, stringer_top_y)           top-face, top-end
        #   P2 = (total_run, stringer_top_y-BW/cosθ)  bottom-face, top-end (plumb)
        #   P3 = (BW/sinθ, 0)                         bottom-face meets ground
        #   P4 = (tread, 0)  [plumb cut only]          ground at plumb cut
        #
        # Canvas coords of polygon corners
        P0cx, P0cy = px(P0_phys[0], P0_phys[1])
        P1cx, P1cy = px(total_run,  stringer_top_y)
        P2cx, P2cy = px(total_run,  stringer_top_y - BW_div_cos)
        P3cx, P3cy = px(P3_phys[0], P3_phys[1])
        if P4_phys is not None:
            P4cx, P4cy = px(P4_phys[0], P4_phys[1])

        str_col = "#7A5533"
        sdim_gap = 24   # pixels gap between face and dimension line

        # --- Side 1: top face P0→P1 (offset straight up in canvas) ---
        top_face_dx = total_run - P0_phys[0]
        top_face_dy = stringer_top_y - P0_phys[1]
        top_face_len = _math.sqrt(top_face_dx**2 + top_face_dy**2)
        stringer_len_in = top_face_len  # effective stringer length (accounts for bottom cut)
        sl_ft = top_face_len / 12.0
        tfd_x0, tfd_y0 = P0cx, P0cy - sdim_gap
        tfd_x1, tfd_y1 = P1cx, P1cy - sdim_gap
        c.create_line(P0cx, P0cy, tfd_x0, tfd_y0, fill=str_col, width=1)
        c.create_line(P1cx, P1cy, tfd_x1, tfd_y1, fill=str_col, width=1)
        c.create_line(tfd_x0, tfd_y0, tfd_x1, tfd_y1, arrow=tk.BOTH, fill=str_col, width=1)
        tfd_mx, tfd_my = (tfd_x0 + tfd_x1) / 2, (tfd_y0 + tfd_y1) / 2
        c.create_text(tfd_mx, tfd_my - 6,
                      text=f"Top face: {top_face_len:.2f}\" ({sl_ft:.2f} ft)",
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
        import math as _m3
        bot_face_dx = total_run - P3_phys[0]
        bot_face_dy = (stringer_top_y - BW_div_cos) - P3_phys[1]
        bot_face_in = _m3.sqrt(bot_face_dx**2 + bot_face_dy**2)
        bot_face_ft = bot_face_in / 12.0
        bfd_x0, bfd_y0 = P3cx, P3cy + sdim_gap
        bfd_x1, bfd_y1 = P2cx, P2cy + sdim_gap
        c.create_line(P3cx, P3cy, bfd_x0, bfd_y0, fill=str_col, width=1)
        c.create_line(P2cx, P2cy, bfd_x1, bfd_y1, fill=str_col, width=1)
        c.create_line(bfd_x0, bfd_y0, bfd_x1, bfd_y1, arrow=tk.BOTH, fill=str_col, width=1)
        bfd_mx, bfd_my = (bfd_x0 + bfd_x1) / 2, (bfd_y0 + bfd_y1) / 2
        c.create_text(bfd_mx, bfd_my + 6,
                      text=f"Bottom face: {bot_face_in:.2f}\" ({bot_face_ft:.2f} ft)",
                      fill=str_col, font=("Segoe UI", 7), anchor="n")

        # --- Side 4: bottom end ---
        if self._bottom_plumb_cut:
            # Two segments: plumb cut P0→P4, then ground seat P4→P3

            # 4a: Plumb cut — vertical from P0 (tread, riser) to P4 (tread, 0)
            plumb_height = riser  # height of the plumb cut
            bp_off = 14  # pixels to the left in canvas x
            bpc_x0, bpc_y0 = P0cx - bp_off, P0cy
            bpc_x1, bpc_y1 = P4cx - bp_off, P4cy
            c.create_line(P0cx, P0cy, bpc_x0, bpc_y0, fill=str_col, width=1)
            c.create_line(P4cx, P4cy, bpc_x1, bpc_y1, fill=str_col, width=1)
            c.create_line(bpc_x0, bpc_y0, bpc_x1, bpc_y1, arrow=tk.BOTH, fill=str_col, width=1)
            c.create_text(bpc_x0 - 3, (bpc_y0 + bpc_y1) / 2,
                          text=f"{plumb_height:.2f}\"", fill=str_col,
                          font=("Segoe UI", 7), anchor="e")

            # 4b: Ground seat — horizontal from P4 (tread, 0) to P3 (BW/sinθ, 0)
            seat_len = BW_div_sin - tread
            foot_off = 14   # pixels below ground line
            ffd_x0, ffd_y0 = P4cx, P4cy + foot_off
            ffd_x1, ffd_y1 = P3cx, P3cy + foot_off
            c.create_line(P4cx, P4cy, ffd_x0, ffd_y0, fill=str_col, width=1)
            c.create_line(P3cx, P3cy, ffd_x1, ffd_y1, fill=str_col, width=1)
            c.create_line(ffd_x0, ffd_y0, ffd_x1, ffd_y1, arrow=tk.BOTH, fill=str_col, width=1)
            c.create_text((ffd_x0 + ffd_x1) / 2, ffd_y0 + 3,
                          text=f"Seat: {seat_len:.2f}\"",
                          fill=str_col, font=("Segoe UI", 7), anchor="n")
        else:
            # Default: horizontal foot along ground from P3 to P0
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
        ml_x0_c, ml_y0_c = px(P0_phys[0], P0_phys[1])
        ml_x1_c, ml_y1_c = px(total_run, stringer_top_y)
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
        # Small vertical line on the ground to show the bottom bearing point.
        if self._bottom_plumb_cut:
            bear_cx, bear_cy = px(tread, 0)
        else:
            bear_cx, bear_cy = px(0, 0)
        c.create_line(bear_cx, bear_cy, bear_cx, bear_cy + 8,
                      fill="#7A5533", width=3)
        c.create_text(bear_cx + 3, bear_cy + 10,
                      text="\u22a5", fill="#7A5533",
                      font=("Segoe UI", 7), anchor="n")

        # (stringer length label moved to the dimension line below the board)

        # Intermediate support markers along the stringer centre-line
        if cfg.support_count > 0:
            for i in range(1, cfg.support_count + 1):
                t_frac = i / (cfg.support_count + 1)
                sup_phys_x = t_frac * total_run
                sup_phys_y = t_frac * stringer_top_y
                scx_top, scy_top = px(sup_phys_x, sup_phys_y)
                # Place on centre-line (HALF_W below top face)
                scx = scx_top + perp(-HALF_W)[0]
                scy = scy_top + perp(-HALF_W)[1]
                r = 5
                c.create_oval(scx - r, scy - r, scx + r, scy + r,
                              fill="#FF8800", outline="#884400", width=1)
                c.create_text(scx + r + 2, scy, text=f"S{i}",
                              fill="#884400", font=("Segoe UI", 6), anchor="w")

        # ── Board join markers ────────────────────────────────────────
        # If the lumber is shorter than the stringer, draw perpendicular
        # lines across the board at each join location (every lumber_in
        # along the stringer from the bottom end).
        lumber_ft_val = self._stringer_lumber_ft
        if lumber_ft_val == 0:
            # Auto: pick shortest standard length
            _std = [8, 10, 12, 14, 16, 18, 20]
            lumber_ft_val = _std[-1]
            for _sl in _std:
                if _sl >= stringer_len_in / 12.0:
                    lumber_ft_val = _sl
                    break
        lumber_in = lumber_ft_val * 12.0
        if lumber_in > 0 and lumber_in < stringer_len_in:
            import math as _math
            JOIN_COLOR = "#CC0000"
            OVERHANG = 8.0  # inches beyond board edges for visibility
            n_joins = _math.ceil(stringer_len_in / lumber_in) - 1
            # Canvas-space perpendicular to the stringer direction.
            # along direction in canvas = (cos_a, -sin_a) (un-scaled).
            # True perpendicular in canvas (rotated 90° CW) = (-(-sin_a), cos_a)
            #   = (sin_a, cos_a) — but we want the one pointing "below" the
            #   top face (toward the bottom face / ground side), so negate:
            #   cross_dir = (-sin_a, -cos_a) per unit inch.
            # We'll scale manually.
            def cross(dist_in):
                """Canvas-perpendicular to stringer, +ve = above top face."""
                return -dist_in * sin_a * scale, -dist_in * cos_a * scale

            for ji in range(1, n_joins + 1):
                d_in = ji * lumber_in  # distance along stringer from bottom
                if d_in >= stringer_len_in:
                    break
                # Position on the top face at distance d_in along the stringer
                along_x, along_y = along(d_in)
                tf_cx, tf_cy = px(P0_phys[0], P0_phys[1])
                tf_cx += along_x
                tf_cy += along_y
                # Line extends from above the top face to below the bottom face
                # using true canvas perpendicular direction
                ja_cx = tf_cx + cross(OVERHANG)[0]
                ja_cy = tf_cy + cross(OVERHANG)[1]
                jb_cx = tf_cx + cross(-BOARD_W_IN - OVERHANG)[0]
                jb_cy = tf_cy + cross(-BOARD_W_IN - OVERHANG)[1]
                # Draw the join line perpendicular across the board
                c.create_line(ja_cx, ja_cy, jb_cx, jb_cy,
                              fill=JOIN_COLOR, width=2, dash=(6, 3))
                # Label below bottom face
                lbl_cx = tf_cx + cross(-BOARD_W_IN - OVERHANG - 4)[0]
                lbl_cy = tf_cy + cross(-BOARD_W_IN - OVERHANG - 4)[1]
                c.create_text(lbl_cx, lbl_cy,
                              text=f"Join {ji}",
                              fill=JOIN_COLOR, font=("Segoe UI", 7, "bold"),
                              anchor="n")

            # ── Per-board segment dimensions along top face ──────────
            # Build list of breakpoints along the stringer (inches from bottom end)
            breaks = [0.0]
            for ji in range(1, n_joins + 1):
                d = ji * lumber_in
                if d < stringer_len_in:
                    breaks.append(d)
            breaks.append(stringer_len_in)

            BD_COLOR = "#995522"
            # Offset further than the overall dim line (sdim_gap=24) so they
            # don't overlap.  Use straight canvas-Y like the overall dims.
            bd_gap = sdim_gap + 18

            for si in range(len(breaks) - 1):
                d0 = breaks[si]
                d1 = breaks[si + 1]
                seg_len = d1 - d0

                # Endpoints on top face
                a0x, a0y = along(d0)
                a1x, a1y = along(d1)
                base_x, base_y = px(P0_phys[0], P0_phys[1])
                t0x = base_x + a0x
                t0y = base_y + a0y
                t1x = base_x + a1x
                t1y = base_y + a1y

                # Dim line offset straight up in canvas (same direction as
                # the overall top-face dim, but further out)
                s0x, s0y = t0x, t0y - bd_gap
                s1x, s1y = t1x, t1y - bd_gap

                # Tick marks from top face to dim line
                c.create_line(t0x, t0y, s0x, s0y, fill=BD_COLOR, width=1)
                c.create_line(t1x, t1y, s1x, s1y, fill=BD_COLOR, width=1)

                # Dimension line with arrows
                c.create_line(s0x, s0y, s1x, s1y,
                              arrow=tk.BOTH, fill=BD_COLOR, width=1)

                # Label at midpoint, above the dim line
                mx = (s0x + s1x) / 2
                my = (s0y + s1y) / 2
                seg_ft = seg_len / 12.0
                lbl = f"{seg_len:.1f}\" ({seg_ft:.1f}')"
                c.create_text(mx, my - 6,
                              text=lbl, fill=BD_COLOR,
                              font=("Segoe UI", 7),
                              anchor="s")

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

        # Step detail inset
        self._draw_step_detail(c, cw, ch, cfg)

        # Materials list (upper-left, below the step detail inset)
        self._draw_materials_list(c, cw, ch, cfg)

    # ------------------------------------------------------------------
    # Triangle incircle helper
    # ------------------------------------------------------------------

    @staticmethod
    def _incircle(ax, ay, bx, by, cx_t, cy_t):
        """Return (incenter_x, incenter_y, inradius) for triangle ABC.

        The incenter is the point equidistant from all three sides,
        and the inradius is that distance — the largest circle that
        fits inside the triangle with equal whitespace to every edge.
        """
        import math as _math
        # Side lengths opposite each vertex
        a = _math.hypot(bx - cx_t, by - cy_t)   # side BC (opposite A)
        b = _math.hypot(ax - cx_t, ay - cy_t)   # side AC (opposite B)
        c_len = _math.hypot(ax - bx, ay - by)   # side AB (opposite C)
        perimeter = a + b + c_len
        if perimeter < 1e-6:
            return (ax + bx + cx_t) / 3, (ay + by + cy_t) / 3, 0
        # Incenter = weighted average of vertices by opposite side lengths
        ix = (a * ax + b * bx + c_len * cx_t) / perimeter
        iy = (a * ay + b * by + c_len * cy_t) / perimeter
        # Inradius = 2 * area / perimeter  (area via shoelace)
        area = abs((bx - ax) * (cy_t - ay) - (cx_t - ax) * (by - ay)) / 2
        inradius = 2 * area / perimeter
        return ix, iy, inradius

    # ------------------------------------------------------------------
    # Step detail inset
    # ------------------------------------------------------------------

    def _draw_step_detail(self, c: tk.Canvas, cw: int, ch: int,
                          cfg: "StepConfig"):
        """Draw a circular inset inscribed in the lower-right white-space triangle."""
        riser = cfg.riser_height
        tread = cfg.tread_depth
        rot   = cfg.rule_of_thumb

        # Compute the incircle of the lower-right triangle bounded by
        # the bottom stringer face dim line, the ground line, and the
        # right-side rise dimension.
        import math as _math
        radius = 75  # default / max
        if self._model:
            total_run  = self._model.total_run
            total_rise = self._model.total_rise
            margin = CANVAS_MARGIN
            usable_w = cw - 2 * margin
            usable_h = ch - 2 * margin
            scale = min(usable_w / total_run, usable_h / total_rise) if total_run and total_rise else 1
            ox = margin
            oy = ch - margin

            BOARD_W_IN = 11.25
            sdim_gap = 24  # must match _redraw_canvas
            n = cfg.n_risers
            angle = _math.atan2(riser, tread)
            cos_a, sin_a = _math.cos(angle), _math.sin(angle)
            BW_div_cos = BOARD_W_IN / cos_a
            BW_div_sin = BOARD_W_IN / sin_a
            # Bottom-face dim line endpoints (canvas coords)
            # P3 = (BW/sinθ, 0) in both modes (bottom face meets ground here)
            P3cx, P3cy = ox + BW_div_sin * scale, oy
            stringer_top_y = (n - 1) * riser
            P2cx, P2cy = ox + total_run * scale, oy - (stringer_top_y - BW_div_cos) * scale
            bfd_x0, bfd_y0 = P3cx, P3cy + sdim_gap
            bfd_x1, bfd_y1 = P2cx, P2cy + sdim_gap

            # Right-wall / ground corner
            right_ground_cx = ox + total_run * scale
            right_ground_cy = oy

            # Incircle of the triangle (equal whitespace to all 3 edges)
            cx, cy, inradius = self._incircle(
                bfd_x0, bfd_y0,           # A: bottom-face dim start
                right_ground_cx, right_ground_cy,  # B: right/ground corner
                bfd_x1, bfd_y1,           # C: bottom-face dim end
            )
            # Use the inradius but cap to a reasonable range
            radius = max(40, min(inradius - 4, 90))
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
        gap = self._tread_board_gap
        nosing = self._nosing_overhang

        # Boards are laid longwise across the stair width; each board
        # covers board_w of the tread depth, with gaps between boards.
        # The nosing overhang means we don't need to fully cover the
        # tread depth — the front nosing extends past the riser below.
        # Effective depth to cover: tread_depth - nosing_overhang
        # n boards with (n-1) gaps: n * board_w + (n-1) * gap >= effective_depth
        # Solving: n >= (effective_depth + gap) / (board_w + gap)
        effective_depth = max(board_w, cfg.tread_depth - nosing)
        boards_per_tread = _math.ceil((effective_depth + gap) / (board_w + gap))
        total_tread_boards = boards_per_tread * n_treads

        # Each board is cut to the stair width
        tread_cut_len = stair_width

        # Stringer lumber length: user-selected or auto (shortest standard >= stringer)
        sl_ft = cfg.stringer_length / 12.0
        standard_lengths = [8, 10, 12, 14, 16, 18, 20]
        stringer_lumber_ft = self._stringer_lumber_ft
        if stringer_lumber_ft == 0:
            # Auto: pick shortest standard length that fits
            stringer_lumber_ft = standard_lengths[-1]
            for slen in standard_lengths:
                if slen >= sl_ft:
                    stringer_lumber_ft = slen
                    break
        # How many boards per stringer (if lumber is shorter than stringer)
        lumber_in = stringer_lumber_ft * 12.0
        boards_per_stringer = _math.ceil(cfg.stringer_length / lumber_in) if lumber_in > 0 else 1
        total_stringer_boards = stringer_count * boards_per_stringer

        # Position: fixed upper-left corner of the canvas
        box_x = 8
        box_y = 8
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
        auto_tag = " (auto)" if self._stringer_lumber_ft == 0 else ""
        if boards_per_stringer == 1:
            c.create_text(box_x + 8, y,
                          text=f"{stringer_count}x  2x12 x {stringer_lumber_ft}'{auto_tag}",
                          fill=body_color, font=body_font, anchor="nw")
            y += line_h
        else:
            c.create_text(box_x + 8, y,
                          text=f"{total_stringer_boards}x  2x12 x {stringer_lumber_ft}'{auto_tag}",
                          fill=body_color, font=body_font, anchor="nw")
            y += line_h
            c.create_text(box_x + 8, y,
                          text=f"({boards_per_stringer} boards/stringer x {stringer_count} stringers)",
                          fill="#777777", font=("Segoe UI", 8), anchor="nw")
            y += line_h
            # Warning: lumber shorter than stringer
            short_color = "#CC7700" if lumber_in >= cfg.stringer_length * 0.5 else INVALID_COLOR
            c.create_text(box_x + 8, y,
                          text=f"Joins needed — {stringer_lumber_ft}' < {sl_ft:.1f}' stringer",
                          fill=short_color, font=("Segoe UI", 8), anchor="nw")
            y += line_h

        # Treads
        c.create_text(box_x, y, text="Treads:",
                      fill=hdr_color, font=("Segoe UI", 9, "bold"), anchor="nw")
        y += line_h

        # Use the selected board label (e.g. "2x6") from the dropdown
        board_label = self._tread_board_label.split(" ")[0] if self._tread_board_label else f"{board_w}\""

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

        # Depth coverage note — rip last board if it overhangs the tread
        actual_coverage = boards_per_tread * board_w + (boards_per_tread - 1) * gap
        overhang = actual_coverage - cfg.tread_depth
        if overhang > 0.1:
            c.create_text(box_x + 8, y,
                          text=f"Rip last board by {overhang:.2f}\"",
                          fill="#996600", font=("Segoe UI", 8), anchor="nw")
            y += line_h

        # --- Interior stringer notch cuts ---
        # The 2 outer stringers are uncut; interior stringers get notched.
        n_cut = max(0, stringer_count - 2)
        if n_cut > 0 and self._model:
            riser = cfg.riser_height
            tread_d = cfg.tread_depth

            angle = _math.atan2(riser, tread_d)
            cos_a = _math.cos(angle)

            # Notch depth perpendicular to board face = riser × cos(θ)
            BOARD_W_IN = 11.25  # actual 2×12 width
            notch_depth = riser * cos_a
            throat = BOARD_W_IN - notch_depth

            y += 4
            c.create_line(box_x, y - 2, box_x + 180, y - 2,
                          fill="#AAAAAA", width=1)

            cut_label = "Stringer Cuts" if n_cut > 1 else "Stringer Cut"
            cut_note = f"({n_cut} interior)" if n_cut > 1 else "(1 interior)"
            c.create_text(box_x, y, text=f"{cut_label} {cut_note}:",
                          fill=hdr_color, font=("Segoe UI", 9, "bold"), anchor="nw")
            y += line_h
            c.create_text(box_x + 8, y,
                          text=f"Tread seat (level): {tread_d:.3f}\"",
                          fill=body_color, font=body_font, anchor="nw")
            y += line_h
            c.create_text(box_x + 8, y,
                          text=f"Riser seat (plumb): {riser:.3f}\"",
                          fill=body_color, font=body_font, anchor="nw")
            y += line_h
            c.create_text(box_x + 8, y,
                          text=f"Notch depth: {notch_depth:.3f}\"",
                          fill=body_color, font=body_font, anchor="nw")
            y += line_h

            # Throat depth with warning if below IBC minimum (3.5")
            throat_color = body_color
            throat_extra = ""
            if throat < 3.5:
                throat_color = INVALID_COLOR
                throat_extra = "  < 3.5\" min!"
            elif throat < 4.0:
                throat_color = "#CC7700"
                throat_extra = "  (marginal)"
            c.create_text(box_x + 8, y,
                          text=f"Throat: {throat:.3f}\"{throat_extra}",
                          fill=throat_color, font=body_font, anchor="nw")
