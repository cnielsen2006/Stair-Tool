import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from typing import Optional

from constants import (
    CANVAS_WIDTH, CANVAS_HEIGHT, CANVAS_MARGIN,
    DIAGRAM_BG, STEP_FILL, STEP_OUTLINE, LABEL_COLOR,
    GROUND_COLOR, OPTIMAL_COLOR, INVALID_COLOR,
    COMFORT_IDEAL_LO, COMFORT_IDEAL_HI, COMFORT_WARN_LO, COMFORT_WARN_HI,
    ANGLE_IDEAL_LO, ANGLE_IDEAL_HI, ANGLE_WARN_LO, ANGLE_WARN_HI,
    ANCHOR_BOLT_DIAMETER,
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
        self._support_every_n: int = 3
        self._steps_range = (2, 50, [])  # (n_lo, n_hi, valid_ns)
        self._hover_data: dict = {}  # tag -> tooltip text string
        self._tooltip_id = None  # canvas item id of active tooltip

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
        self._canvas.bind("<Motion>", self._on_canvas_motion)
        self._canvas.bind("<Leave>", self._on_canvas_leave)

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
            ("supports",  "Support Uprights:"),
            ("bolts",     "Through Bolts:"),
        ]
        for col, (key, lbl) in enumerate(row1_defs):
            ttk.Label(stats, text=lbl, font=("Segoe UI", 8, "bold")).grid(
                row=1, column=col * 2, sticky="e", padx=(8 if col else 0, 2), pady=(4, 0))
            var = tk.StringVar(value="—")
            self._stat_vars[key] = var
            ttk.Label(stats, textvariable=var).grid(
                row=1, column=col * 2 + 1, sticky="w", pady=(4, 0))


        self._status_label = None  # removed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, model: StairModel, selected_risers: Optional[int],
               stringer_count: int = 3, stair_width: float = 36.0,
               tread_board_width: float = 5.5, tread_board_label: str = "",
               tread_board_gap: float = 0.25, nosing_overhang: float = 0.75,
               stringer_lumber_ft: int = 0, bottom_plumb_cut: bool = False,
               anchor_debug: bool = False,
               support_every_n: int = 3):
        self._model      = model
        self._stringer_count = stringer_count
        self._stair_width = stair_width
        self._support_every_n = max(1, support_every_n)
        self._tread_board_width = tread_board_width
        self._tread_board_label = tread_board_label
        self._tread_board_gap = tread_board_gap
        self._nosing_overhang = nosing_overhang
        self._stringer_lumber_ft = stringer_lumber_ft
        self._bottom_plumb_cut = bottom_plumb_cut
        self._anchor_debug = anchor_debug
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

    def _on_canvas_motion(self, event):
        """Show tooltip when hovering over a bolt or step."""
        c = self._canvas
        # Remove previous tooltip and dimension overlay
        if self._tooltip_id is not None:
            c.delete("hover_tooltip")
            # Restore hidden dimensions
            for item in c.find_withtag("dim"):
                c.itemconfigure(item, state="normal")
            self._tooltip_id = None
        # Check what's under the cursor
        items = c.find_overlapping(event.x - 3, event.y - 3,
                                   event.x + 3, event.y + 3)
        for item in items:
            tags = c.gettags(item)
            for tag in tags:
                if tag not in self._hover_data:
                    continue
                entry = self._hover_data[tag]
                is_bolt = tag.startswith("bolt_")
                if callable(entry):
                    # Hide existing dims so bolt overlay is readable
                    if is_bolt:
                        for dim_item in c.find_withtag("dim"):
                            c.itemconfigure(dim_item, state="hidden")
                    text = entry(c)  # draw dimensions on canvas
                else:
                    text = entry
                if is_bolt:
                    # No floating tooltip for bolts — the on-canvas
                    # arrows and labels are sufficient
                    self._tooltip_id = True  # sentinel so leave restores dims
                else:
                    # Floating tooltip for steps
                    tx, ty = event.x + 12, event.y - 18
                    tid = c.create_text(
                        tx, ty, text=text, anchor="sw",
                        fill="#1a3366", font=("Segoe UI", 9, "bold"),
                        tags="hover_tooltip")
                    bbox = c.bbox(tid)
                    if bbox:
                        cw = c.winfo_width()
                        if bbox[2] > cw - 4:
                            tx -= (bbox[2] - cw + 8)
                            c.coords(tid, tx, ty)
                            bbox = c.bbox(tid)
                        if bbox[1] < 4:
                            ty += (8 - bbox[1])
                            c.coords(tid, tx, ty)
                            bbox = c.bbox(tid)
                        pad = 3
                        rid = c.create_rectangle(
                            bbox[0] - pad, bbox[1] - pad,
                            bbox[2] + pad, bbox[3] + pad,
                            fill="#FFFFDD", outline="#888888",
                            tags="hover_tooltip")
                        c.tag_raise(tid, rid)
                    self._tooltip_id = tid
                return

    def _on_canvas_leave(self, _event):
        """Remove tooltip when cursor leaves canvas."""
        if self._tooltip_id is not None:
            self._canvas.delete("hover_tooltip")
            # Restore hidden dimensions
            for item in self._canvas.find_withtag("dim"):
                self._canvas.itemconfigure(item, state="normal")
            self._tooltip_id = None

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
            score = self._model._score(riser, tread)
            return StepConfig(n, riser, tread, score, valid, rot, stringer_len)
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


        # Stringer info (length varies with N since slope = riser/tread)
        sl_in = cfg.stringer_length
        sl_ft = sl_in / 12.0
        self._stat_vars["stringer"].set(f"{sl_in:.2f}\"")
        self._stat_vars["stringer_ft"].set(f"{sl_ft:.2f} ft")
        n_risers = cfg.n_risers
        n_step_treads = n_risers - 2  # exclude landing
        support_steps = list(range(self._support_every_n, n_step_treads + 1, self._support_every_n))
        n_supports = len(support_steps)
        self._stat_vars["supports"].set(f"{n_supports} (every {self._support_every_n} steps)")
        self._stat_vars["bolts"].set(f"{n_supports}")

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
        self._hover_data.clear()
        self._tooltip_id = None

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
        bottom_margin = margin + 30  # extra room for Total Run dimension
        usable_w = cw - 2 * margin
        usable_h = ch - margin - bottom_margin

        if usable_w <= 0 or usable_h <= 0:
            return

        scale = min(usable_w / total_run, usable_h / total_rise)

        # Origin: bottom-left of staircase in canvas coords
        ox = margin
        oy = ch - bottom_margin

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
        import math as _m_step
        _step_angle = _m_step.atan2(riser, tread)
        _step_cos_a = _m_step.cos(_step_angle)
        _step_notch_depth = riser * _step_cos_a
        _step_throat = 11.25 - _step_notch_depth
        for i in range(n - 1):
            x0, y0 = px(i * tread, i * riser)
            x1, y1 = px((i + 1) * tread, (i + 1) * riser)
            step_tag = f"step_{i}"
            # Swap y because canvas y is inverted
            c.create_rectangle(x0, y1, x1, y0,
                                fill=fill_color, outline=STEP_OUTLINE, width=1,
                                tags=step_tag)
            self._hover_data[step_tag] = (
                f"Step {i+1}: tread {tread:.3f}\", riser {riser:.3f}\", "
                f"notch {_step_notch_depth:.3f}\", throat {_step_throat:.3f}\"")
            # Magnifying glass icon in center of step
            scx, scy = (x0 + x1) / 2, (y0 + y1) / 2
            sr = 4
            c.create_oval(scx - sr, scy - sr, scx + sr, scy + sr,
                          outline="#4477AA", width=1.2, tags=step_tag)
            c.create_line(scx + sr * 0.6, scy + sr * 0.6,
                          scx + sr * 1.6, scy + sr * 1.6,
                          fill="#4477AA", width=1.5, tags=step_tag)

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

        # (First-step riser/tread dimensions removed — shown in step detail circle)

        # ── Overall dimensions ─────────────────────────────────────────
        dim_color = "#444455"
        tick = 6

        # Right-side dimension: ground → landing (total rise)
        dim_offset_x = 38  # pixels right of the stair right edge
        land_cx, land_cy = px(total_run, total_rise)
        rs_bot_cx, rs_bot_cy = px(total_run, 0)
        rdim_x = land_cx + dim_offset_x
        # Extension lines
        c.create_line(land_cx, land_cy, rdim_x + tick, land_cy, fill=dim_color, width=1, tags="dim")
        c.create_line(rs_bot_cx, rs_bot_cy, rdim_x + tick, rs_bot_cy, fill=dim_color, width=1, tags="dim")
        # Arrow
        c.create_line(rdim_x, rs_bot_cy, rdim_x, land_cy,
                      arrow=tk.BOTH, fill=dim_color, width=1, tags="dim")
        # Label
        c.create_text(rdim_x + tick + 3, (land_cy + rs_bot_cy) / 2,
                      text=f"Total Rise\n{total_rise:.2f}\"",
                      fill=dim_color, font=("Segoe UI", 9), anchor="w", tags="dim")

        # Bottom dimension: total run
        dim_offset_y = 30
        bx_left,  by_bot = px(0,         0)
        bx_right, _      = px(total_run, 0)
        bdim_y = by_bot + dim_offset_y
        c.create_line(bx_left,  by_bot, bx_left,  bdim_y + tick, fill=dim_color, width=1, tags="dim")
        c.create_line(bx_right, by_bot, bx_right, bdim_y + tick, fill=dim_color, width=1, tags="dim")
        c.create_line(bx_left, bdim_y, bx_right, bdim_y,
                      arrow=tk.BOTH, fill=dim_color, width=1, tags="dim")
        c.create_text((bx_left + bx_right) / 2, bdim_y + tick + 2,
                      text=f"Total Run: {total_run:.2f}\"",
                      fill=dim_color, font=("Segoe UI", 9), anchor="n", tags="dim")

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
        # --- Side 1: top face P0→P1 ---
        top_face_dx = total_run - P0_phys[0]
        top_face_dy = stringer_top_y - P0_phys[1]
        top_face_len = _math.sqrt(top_face_dx**2 + top_face_dy**2)
        # Board length: the rectangular board must contain the full stringer
        # shape.  Project all vertices onto the along-stringer axis; the
        # extent (max − min) is the true required board length.
        if self._bottom_plumb_cut:
            def _along_proj(phys_x, phys_y):
                return phys_x * cos_a + phys_y * sin_a
            _proj_vals = [_along_proj(*v) for v in poly_phys]
            _proj_min = min(_proj_vals)
            _proj_max = max(_proj_vals)
            stringer_len_in = _proj_max - _proj_min
            # How far back P0 is from the true board start (proj_min)
            _p0_offset = _along_proj(*P0_phys) - _proj_min
        else:
            stringer_len_in = top_face_len
            _p0_offset = 0.0
        self._effective_stringer_len = stringer_len_in  # for materials list
        sl_ft = stringer_len_in / 12.0
        # Dimension line at original axis-aligned position (straight up)
        tfd_y0 = P0cy - sdim_gap
        tfd_y1 = P1cy - sdim_gap
        # Extension lines go perpendicular to the top face from each vertex
        # to meet the horizontal dim-line position.
        # Perpendicular (90° CCW from face direction in canvas coords):
        _face_dx = P1cx - P0cx   # positive (right)
        _face_dy = P1cy - P0cy   # negative (up in canvas)
        _perp_x = _face_dy       # CCW 90°: (dy, -dx)
        _perp_y = -_face_dx
        # Extension from P0: travel along perp until y = P0cy - sdim_gap
        _t0 = -sdim_gap / _perp_y
        tfd_x0 = P0cx + _t0 * _perp_x
        # Extension from P1: travel along perp until y = P1cy - sdim_gap
        _t1 = -sdim_gap / _perp_y
        tfd_x1 = P1cx + _t1 * _perp_x
        c.create_line(P0cx, P0cy, tfd_x0, tfd_y0, fill=str_col, width=1, tags="dim")
        c.create_line(P1cx, P1cy, tfd_x1, tfd_y1, fill=str_col, width=1, tags="dim")
        c.create_line(tfd_x0, tfd_y0, tfd_x1, tfd_y1, arrow=tk.BOTH, fill=str_col, width=1, tags="dim")
        tfd_mx, tfd_my = (tfd_x0 + tfd_x1) / 2, (tfd_y0 + tfd_y1) / 2
        _str_ang_deg = _math.degrees(angle)
        c.create_text(tfd_mx, tfd_my - 6,
                      text=f"Top face: {top_face_len:.2f}\" ({sl_ft:.2f} ft)",
                      fill=str_col, font=("Segoe UI", 9), anchor="s",
                      angle=_str_ang_deg, tags="dim")

        # --- Side 2: top plumb cut P1→P2 (perpendicular = horizontal) ---
        tp_off = 14  # pixels to the right in canvas x
        tpc_x0, tpc_y0 = P1cx + tp_off, P1cy
        tpc_x1, tpc_y1 = P2cx + tp_off, P2cy
        c.create_line(P1cx, P1cy, tpc_x0, tpc_y0, fill=str_col, width=1, tags="dim")
        c.create_line(P2cx, P2cy, tpc_x1, tpc_y1, fill=str_col, width=1, tags="dim")
        c.create_line(tpc_x0, tpc_y0, tpc_x1, tpc_y1, arrow=tk.BOTH, fill=str_col, width=1, tags="dim")
        c.create_text(tpc_x0 + 3, (tpc_y0 + tpc_y1) / 2,
                      text=f"{BW_div_cos:.2f}\"", fill=str_col,
                      font=("Segoe UI", 9), anchor="w", tags="dim")

        # --- Side 3: bottom face P2→P3 ---
        import math as _m3
        bot_face_dx = total_run - P3_phys[0]
        bot_face_dy = (stringer_top_y - BW_div_cos) - P3_phys[1]
        bot_face_in = _m3.sqrt(bot_face_dx**2 + bot_face_dy**2)
        bot_face_ft = bot_face_in / 12.0
        # Dimension line at original axis-aligned position (straight down)
        bfd_y0 = P3cy + sdim_gap
        bfd_y1 = P2cy + sdim_gap
        # Extension lines perpendicular to bottom face (90° CW = below face)
        # CW 90° from face direction: (-dy, dx)
        _bperp_x = -_face_dy     # CW 90°: (-dy, dx)
        _bperp_y =  _face_dx
        # Extension from P3: travel along perp until y = P3cy + sdim_gap
        _bt0 = sdim_gap / _bperp_y
        bfd_x0 = P3cx + _bt0 * _bperp_x
        # Extension from P2: travel along perp until y = P2cy + sdim_gap
        _bt1 = sdim_gap / _bperp_y
        bfd_x1 = P2cx + _bt1 * _bperp_x
        c.create_line(P3cx, P3cy, bfd_x0, bfd_y0, fill=str_col, width=1, tags="dim")
        c.create_line(P2cx, P2cy, bfd_x1, bfd_y1, fill=str_col, width=1, tags="dim")
        c.create_line(bfd_x0, bfd_y0, bfd_x1, bfd_y1, arrow=tk.BOTH, fill=str_col, width=1, tags="dim")
        bfd_mx, bfd_my = (bfd_x0 + bfd_x1) / 2, (bfd_y0 + bfd_y1) / 2
        c.create_text(bfd_mx, bfd_my + 6,
                      text=f"Bottom face: {bot_face_in:.2f}\" ({bot_face_ft:.2f} ft)",
                      fill=str_col, font=("Segoe UI", 9), anchor="n",
                      angle=_math.degrees(angle), tags="dim")

        # --- Side 4: bottom end (perpendicular to ground = vertical) ---
        if self._bottom_plumb_cut:
            # Two segments: plumb cut P0→P4, then ground seat P4→P3
            # Ground seat is horizontal → perpendicular is vertical
            seat_len = BW_div_sin - tread
            foot_off = 14   # pixels below ground line
            ffd_x0, ffd_y0 = P4cx, P4cy + foot_off
            ffd_x1, ffd_y1 = P3cx, P3cy + foot_off
            c.create_line(P4cx, P4cy, ffd_x0, ffd_y0, fill=str_col, width=1, tags="dim")
            c.create_line(P3cx, P3cy, ffd_x1, ffd_y1, fill=str_col, width=1, tags="dim")
            c.create_line(ffd_x0, ffd_y0, ffd_x1, ffd_y1, arrow=tk.BOTH, fill=str_col, width=1, tags="dim")
            c.create_text((ffd_x0 + ffd_x1) / 2, ffd_y0 + 3,
                          text=f"Seat: {seat_len:.2f}\"",
                          fill=str_col, font=("Segoe UI", 9), anchor="n", tags="dim")
        else:
            # Default: horizontal foot along ground from P3 to P0
            # Ground is horizontal → perpendicular is vertical
            foot_off = 14   # pixels below ground line
            ffd_x0, ffd_y0 = P3cx, P3cy + foot_off
            ffd_x1, ffd_y1 = P0cx, P0cy + foot_off
            c.create_line(P3cx, P3cy, ffd_x0, ffd_y0, fill=str_col, width=1, tags="dim")
            c.create_line(P0cx, P0cy, ffd_x1, ffd_y1, fill=str_col, width=1, tags="dim")
            c.create_line(ffd_x0, ffd_y0, ffd_x1, ffd_y1, arrow=tk.BOTH, fill=str_col, width=1, tags="dim")
            c.create_text((ffd_x0 + ffd_x1) / 2, ffd_y0 + 3,
                          text=f"Foot: {BW_div_sin:.2f}\"",
                          fill=str_col, font=("Segoe UI", 9), anchor="n", tags="dim")


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

            # Riser label above the top face
            if i <= 9:   # avoid crowding on many steps
                lbl_cx = cnr_cx + perp(4)[0]
                lbl_cy = cnr_cy + perp(4)[1]
                c.create_text(lbl_cx, lbl_cy,
                              text=f"R{i}", fill=NOTCH_COLOR,
                              font=("Segoe UI", 6), anchor="sw", tags="dim")

        # --- Bottom bearing indicator ---
        # Small vertical line on the ground to show the bottom bearing point.
        if self._bottom_plumb_cut:
            bear_cx, bear_cy = px(tread, 0)
        else:
            bear_cx, bear_cy = px(0, 0)
        c.create_line(bear_cx, bear_cy, bear_cx, bear_cy + 8,
                      fill="#7A5533", width=3, tags="dim")
        c.create_text(bear_cx + 3, bear_cy + 10,
                      text="\u22a5", fill="#7A5533",
                      font=("Segoe UI", 7), anchor="n", tags="dim")

        # (stringer length label moved to the dimension line below the board)

        # Support posts: placed at every Nth step position along the stair.
        POST_W_IN = 3.5                     # actual 4×4 post width (inches)
        half_post = POST_W_IN / 2.0
        n_step_treads = n - 2  # exclude landing
        support_step_indices = list(range(self._support_every_n, n_step_treads + 1, self._support_every_n))
        for si, step_i in enumerate(support_step_indices):
            sup_phys_x = step_i * tread + tread / 2
            sup_top_face_y = sup_phys_x * (stringer_top_y / total_run)
            sup_bot_face_y = sup_top_face_y - BW_div_cos
            sup_post_top_y = sup_bot_face_y + 0.75 * BW_div_cos
            post_left_cx, post_top_cy  = px(sup_phys_x - half_post, sup_post_top_y)
            post_right_cx, post_bot_cy = px(sup_phys_x + half_post, 0)
            c.create_rectangle(post_left_cx, post_top_cy,
                               post_right_cx, post_bot_cy,
                               fill="#FF8800", outline="#884400", width=1)
            c.create_text((post_left_cx + post_right_cx) / 2,
                          post_bot_cy + 3, text=f"S{si+1}",
                          fill="#884400", font=("Segoe UI", 6), anchor="n", tags="dim")

        # ── Wall-mount anchor bolt markers ──────────────────────────────
        # Per-board bolt placement:
        #   1. Subtract end margin from each board → usable length
        #   2. Divide usable length by max spacing → bolt count
        #   3. Distribute bolts evenly across usable length
        # Y-axis: 75% from top face toward bottom face (bulk of wood above bolt)
        # Perpendicular-to-board helper (same direction as join markers).
        # cross(+d) = above top face, cross(-d) = into board.
        def _cross(dist_in):
            return -dist_in * sin_a * scale, -dist_in * cos_a * scale

        # ── Board join computation (used by anchors, join markers, materials) ──
        # Resolve lumber length and compute board segment edges with
        # joins snapped to nearest riser base for structural integrity.
        lumber_length_ft = self._stringer_lumber_ft
        if lumber_length_ft == 0:
            _standard_lengths = [8, 10, 12, 14, 16, 18, 20]
            lumber_length_ft = _standard_lengths[-1]
            for length_ft in _standard_lengths:
                if length_ft >= stringer_len_in / 12.0:
                    lumber_length_ft = length_ft
                    break
        lumber_length_in = lumber_length_ft * 12.0

        step_slope = _math.hypot(tread, riser)
        riser_bases_from_board_start = []
        for i in range(n):
            pos = _p0_offset + i * step_slope
            if 0 < pos < stringer_len_in:
                riser_bases_from_board_start.append(pos)

        board_slope_edges = [0.0]
        if lumber_length_in > 0 and lumber_length_in < stringer_len_in:
            num_boards = _math.ceil(stringer_len_in / lumber_length_in)
            used_snaps = set()
            for board_index in range(1, num_boards):
                raw_join = board_index * lumber_length_in
                best = None
                best_dist = float('inf')
                for rb in riser_bases_from_board_start:
                    d = abs(rb - raw_join)
                    if d < best_dist and rb not in used_snaps:
                        best_dist = d
                        best = rb
                if best is not None:
                    used_snaps.add(best)
                    join_from_p0 = best - _p0_offset
                    if 0 < join_from_p0 < top_face_len:
                        board_slope_edges.append(join_from_p0)
        board_slope_edges.append(top_face_len)
        self._board_slope_edges = board_slope_edges
        self._lumber_length_ft = lumber_length_ft
        self._stringer_len_in = stringer_len_in

        # ── Through-bolt markers at support positions ─────────────────
        if True:
            ANCHOR_COLOR = "#2255AA"
            BOLT_VISUAL_RADIUS = max(1.5, ANCHOR_BOLT_DIAMETER * 4)
            bolt_visual_radius_px = BOLT_VISUAL_RADIUS * scale
            BOLT_DEPTH_FRACTION = 0.75
            perp_into_board_x = sin_a
            perp_into_board_y = -cos_a
            bolt_perp_depth = BOLT_DEPTH_FRACTION * BOARD_W_IN

            def bolt_canvas_position(slope_distance_from_p0):
                """Canvas (x,y) for a bolt at given slope distance along
                the top face from P0, dropped vertically 75% of board width
                so the bolt stays on the same vertical line as the top-face point."""
                top_face_phys_x = P0_phys[0] + slope_distance_from_p0 * cos_a
                top_face_phys_y = P0_phys[1] + slope_distance_from_p0 * sin_a
                bolt_phys_x = top_face_phys_x
                bolt_phys_y = top_face_phys_y - BOLT_DEPTH_FRACTION * BOARD_W_IN
                return px(bolt_phys_x, bolt_phys_y)

            # Place a through-bolt at every Nth step position along the
            # stringer.  Each bolt sits at the step's riser-base on the
            # top face, expressed as a slope distance from P0.
            step_slope = _math.hypot(tread, riser)
            n_step_treads_bolt = n - 2  # exclude landing
            bolt_step_indices = list(range(self._support_every_n, n_step_treads_bolt + 1, self._support_every_n))
            all_bolt_slope_positions = []
            all_bolt_segment_info = []
            for step_i in bolt_step_indices:
                mid_tread_x = step_i * tread + tread / 2
                pos = (mid_tread_x - P0_phys[0]) / cos_a
                if pos < 0 or pos > top_face_len:
                    continue
                # Find which board segment this bolt falls in
                seg_start = board_slope_edges[0]
                seg_end = board_slope_edges[-1]
                for seg_idx in range(len(board_slope_edges) - 1):
                    if board_slope_edges[seg_idx] <= pos <= board_slope_edges[seg_idx + 1]:
                        seg_start = board_slope_edges[seg_idx]
                        seg_end = board_slope_edges[seg_idx + 1]
                        break
                all_bolt_slope_positions.append(pos)
                all_bolt_segment_info.append((pos, seg_start, seg_end))

            self._anchor_count = len(all_bolt_slope_positions)

            # Debug guide lines: green = board edges, blue = bolt X
            if self._anchor_debug:
                for edge_slope in board_slope_edges:
                    edge_phys_x = P0_phys[0] + edge_slope * cos_a
                    edge_canvas_x = px(edge_phys_x, 0)[0]
                    c.create_line(edge_canvas_x, 0, edge_canvas_x, 2000,
                                  fill="green", width=1, dash=(2, 2))
                for bolt_slope in all_bolt_slope_positions:
                    bolt_phys_x = P0_phys[0] + bolt_slope * cos_a
                    bolt_canvas_x = px(bolt_phys_x, 0)[0]
                    c.create_line(bolt_canvas_x, 0, bolt_canvas_x, 2000,
                                  fill="blue", width=1, dash=(6, 3))

            # 5. Draw each bolt at its slope distance projected onto the top face
            DIM_COLOR = "#DD4400"
            for bolt_number, bolt_distance in enumerate(all_bolt_slope_positions):
                bolt_x, bolt_y = bolt_canvas_position(bolt_distance)
                bolt_tag = f"bolt_{bolt_number}"
                c.create_oval(
                    bolt_x - bolt_visual_radius_px, bolt_y - bolt_visual_radius_px,
                    bolt_x + bolt_visual_radius_px, bolt_y + bolt_visual_radius_px,
                    fill="#BBDDFF", outline=ANCHOR_COLOR, width=2,
                    tags=bolt_tag)
                crosshair_radius = bolt_visual_radius_px * 0.6
                c.create_line(bolt_x - crosshair_radius, bolt_y,
                              bolt_x + crosshair_radius, bolt_y,
                              fill=ANCHOR_COLOR, width=1, tags=bolt_tag)
                c.create_line(bolt_x, bolt_y - crosshair_radius,
                              bolt_x, bolt_y + crosshair_radius,
                              fill=ANCHOR_COLOR, width=1, tags=bolt_tag)
                label_offset_x, label_offset_y = perp(-BOARD_W_IN * 0.25 - 6)
                c.create_text(bolt_x + label_offset_x, bolt_y + label_offset_y,
                              text=f"A{bolt_number+1}", fill=ANCHOR_COLOR,
                              font=("Segoe UI", 6), anchor="n", tags=bolt_tag)
                # Store bolt hover callback that draws dimension lines.
                # Start from the bolt's canvas position and use along/perp
                # to draw board-relative dimension arrows.
                _, seg_start, seg_end = all_bolt_segment_info[bolt_number]
                offset_from_top = BOLT_DEPTH_FRACTION * BOARD_W_IN
                # Flat board distances. The physical board piece runs:
                #   first segment: from -_p0_offset to first join (or board end)
                #   middle segments: from join to join (= seg_start to seg_end)
                #   last segment: from last join to stringer_len_in - _p0_offset
                board_start = -_p0_offset if seg_start == 0.0 else seg_start
                board_end_slope = (stringer_len_in - _p0_offset
                                   if seg_end == top_face_len else seg_end)
                dist_from_start = bolt_distance - board_start
                dist_from_end_val = board_end_slope - bolt_distance
                if dist_from_start <= dist_from_end_val:
                    offset_from_near_end = dist_from_start
                    near_edge = board_start
                else:
                    offset_from_near_end = dist_from_end_val
                    near_edge = board_end_slope
                _ad = _math.degrees(angle)
                _bx, _by = bolt_x, bolt_y
                # Arrow endpoint: board-end perpendicular at bolt depth.
                # From top-face point at near_edge, go into board using
                # cross() direction (same as join markers).
                # The bolt's perpendicular depth from the top face =
                # vertical_drop * cos(angle).
                perp_depth = offset_from_top * cos_a
                ne_tf_cx, ne_tf_cy = px(
                    P0_phys[0] + near_edge * cos_a,
                    P0_phys[1] + near_edge * sin_a)
                cd = _cross(-perp_depth)
                _ne_cx = ne_tf_cx + cd[0]
                _ne_cy = ne_tf_cy + cd[1]
                _end_d = offset_from_near_end
                # Side inset arrow: perpendicular to board, from bolt to top face.
                # Bolt is dropped vertically by offset_from_top from top face,
                # so perpendicular distance to top face = offset_from_top * cos(angle).
                _top_d = offset_from_top * cos_a
                _bolt_phys_x = P0_phys[0] + bolt_distance * cos_a
                _bolt_phys_y = P0_phys[1] + bolt_distance * sin_a - offset_from_top
                # Point on top face perpendicularly above bolt:
                _perp_top_x = _bolt_phys_x - _top_d * sin_a
                _perp_top_y = _bolt_phys_y + _top_d * cos_a
                _pt_cx, _pt_cy = px(_perp_top_x, _perp_top_y)
                def _make_hover(_lbl, _end_d, _top_d,
                                _bx, _by, _necx, _necy,
                                _ptcx, _ptcy,
                                _ad=_ad, _dc=DIM_COLOR):
                    def draw(canvas):
                        tag = "hover_tooltip"
                        # 1. Along board: board end → bolt
                        canvas.create_line(_necx, _necy, _bx, _by,
                                           arrow=tk.BOTH, fill=_dc,
                                           width=2, tags=tag)
                        lmx = (_necx + _bx) / 2
                        lmy = (_necy + _by) / 2
                        canvas.create_text(
                            lmx, lmy,
                            text=f"{_end_d:.1f}\"",
                            fill=_dc, font=("Segoe UI", 9, "bold"),
                            anchor="n", angle=_ad, tags=tag)
                        # 2. Perp from top edge to bolt
                        canvas.create_line(_ptcx, _ptcy, _bx, _by,
                                           arrow=tk.BOTH, fill=_dc,
                                           width=2, tags=tag)
                        pmx = (_ptcx + _bx) / 2
                        pmy = (_ptcy + _by) / 2
                        canvas.create_text(
                            pmx, pmy,
                            text=f"{_top_d:.2f}\"",
                            fill=_dc, font=("Segoe UI", 9, "bold"),
                            anchor="n", angle=_ad - 90, tags=tag)
                        return (f"{_lbl}: {_end_d:.1f}\" from end, "
                                f"{_top_d:.2f}\" from top")
                    return draw
                self._hover_data[bolt_tag] = _make_hover(
                    f"A{bolt_number+1}", _end_d, _top_d,
                    _bx, _by, _ne_cx, _ne_cy,
                    _pt_cx, _pt_cy)
                # Magnifying glass icon above bolt head
                mag_ox, mag_oy = perp(BOARD_W_IN * 0.15 + 5)
                mcx, mcy = bolt_x + mag_ox, bolt_y + mag_oy
                mr = 4  # lens radius in pixels
                c.create_oval(mcx - mr, mcy - mr, mcx + mr, mcy + mr,
                              outline=ANCHOR_COLOR, width=1.2, tags=bolt_tag)
                # Handle (short line from bottom-right of lens)
                c.create_line(mcx + mr * 0.6, mcy + mr * 0.6,
                              mcx + mr * 1.6, mcy + mr * 1.6,
                              fill=ANCHOR_COLOR, width=1.5, tags=bolt_tag)

            # Spacing dimension between first two bolts:
            # short arrow leads on each side of a centered label
            if len(all_bolt_slope_positions) >= 2:
                first_bolt_spacing = (all_bolt_slope_positions[1]
                                      - all_bolt_slope_positions[0])
                first_bolt_x, first_bolt_y = bolt_canvas_position(
                    all_bolt_slope_positions[0])
                second_bolt_x, second_bolt_y = bolt_canvas_position(
                    all_bolt_slope_positions[1])
                spacing_label_x = (first_bolt_x + second_bolt_x) / 2
                spacing_label_y = (first_bolt_y + second_bolt_y) / 2
                # Leave a gap around the label for the text; short leads fill the rest
                lead_gap_px = 28  # half-width of gap around label in pixels
                along_unit_x = cos_a
                along_unit_y = -sin_a  # canvas y is flipped
                # Inset arrow starts away from bolt heads to avoid overlap
                bolt_inset_px = bolt_visual_radius_px + 2
                # Arrow from near first bolt toward label
                lead_start_first_x = first_bolt_x + bolt_inset_px * along_unit_x
                lead_start_first_y = first_bolt_y + bolt_inset_px * along_unit_y
                lead_end_toward_first_x = spacing_label_x - lead_gap_px * along_unit_x
                lead_end_toward_first_y = spacing_label_y - lead_gap_px * along_unit_y
                c.create_line(lead_start_first_x, lead_start_first_y,
                              lead_end_toward_first_x, lead_end_toward_first_y,
                              arrow=tk.FIRST, fill=ANCHOR_COLOR, width=1, tags="dim")
                # Arrow from near second bolt toward label
                lead_start_second_x = second_bolt_x - bolt_inset_px * along_unit_x
                lead_start_second_y = second_bolt_y - bolt_inset_px * along_unit_y
                lead_end_toward_second_x = spacing_label_x + lead_gap_px * along_unit_x
                lead_end_toward_second_y = spacing_label_y + lead_gap_px * along_unit_y
                c.create_line(lead_start_second_x, lead_start_second_y,
                              lead_end_toward_second_x, lead_end_toward_second_y,
                              arrow=tk.FIRST, fill=ANCHOR_COLOR, width=1, tags="dim")
                c.create_text(spacing_label_x, spacing_label_y,
                              text=f"{first_bolt_spacing:.1f}\" o.c.",
                              fill=ANCHOR_COLOR, font=("Segoe UI", 9),
                              anchor="center", angle=_math.degrees(angle), tags="dim")

        # ── Board end markers (dashed perpendicular lines) ──────────
        # Draw at the physical start and end of the board (before cuts).
        BOARD_END_OVERHANG = 8.0
        _p0_cx, _p0_cy = px(P0_phys[0], P0_phys[1])
        for board_end_slope in [-_p0_offset, stringer_len_in - _p0_offset]:
            be_along = along(board_end_slope)
            be_cx = _p0_cx + be_along[0]
            be_cy = _p0_cy + be_along[1]
            be_a_cx = be_cx + _cross(BOARD_END_OVERHANG)[0]
            be_a_cy = be_cy + _cross(BOARD_END_OVERHANG)[1]
            be_b_cx = be_cx + _cross(-BOARD_W_IN - BOARD_END_OVERHANG)[0]
            be_b_cy = be_cy + _cross(-BOARD_W_IN - BOARD_END_OVERHANG)[1]
            c.create_line(be_a_cx, be_a_cy, be_b_cx, be_b_cy,
                          fill="#CC0000", width=2, dash=(6, 3))

        # ── Board join markers ────────────────────────────────────────
        # Reuse snapped join positions from self._board_slope_edges
        # (computed in the anchor section above; edges are P0-relative).
        edges = getattr(self, '_board_slope_edges', [0.0, top_face_len])
        join_positions = edges[1:-1]  # interior edges are the joins

        if join_positions:
            import math as _math
            JOIN_COLOR = "#CC0000"
            OVERHANG = 8.0

            def cross(dist_in):
                """Canvas-perpendicular to stringer, +ve = above top face."""
                return -dist_in * sin_a * scale, -dist_in * cos_a * scale

            for ji, d_top in enumerate(join_positions, 1):
                along_x, along_y = along(d_top)
                tf_cx, tf_cy = px(P0_phys[0], P0_phys[1])
                tf_cx += along_x
                tf_cy += along_y
                ja_cx = tf_cx + cross(OVERHANG)[0]
                ja_cy = tf_cy + cross(OVERHANG)[1]
                jb_cx = tf_cx + cross(-BOARD_W_IN - OVERHANG)[0]
                jb_cy = tf_cy + cross(-BOARD_W_IN - OVERHANG)[1]
                c.create_line(ja_cx, ja_cy, jb_cx, jb_cy,
                              fill=JOIN_COLOR, width=2, dash=(6, 3))
                lbl_cx = tf_cx + cross(-BOARD_W_IN - OVERHANG - 4)[0]
                lbl_cy = tf_cy + cross(-BOARD_W_IN - OVERHANG - 4)[1]
                c.create_text(lbl_cx, lbl_cy,
                              text=f"Join {ji}",
                              fill=JOIN_COLOR, font=("Segoe UI", 7, "bold"),
                              anchor="n")

            # ── Per-board segment dimensions along top face ──────────
            # Convert edges from P0-relative to board-start-relative so
            # the first board includes the portion before P0 (plumb cut)
            # and the last board extends to the physical board end.
            breaks_from_p0 = list(edges)
            breaks_from_p0[0] = -_p0_offset             # board physical start
            breaks_from_p0[-1] = stringer_len_in - _p0_offset  # board physical end

            BD_COLOR = "#995522"
            bd_gap = sdim_gap + 18

            for si in range(len(breaks_from_p0) - 1):
                d0_p0 = breaks_from_p0[si]      # P0-relative slope pos
                d1_p0 = breaks_from_p0[si + 1]
                seg_len = d1_p0 - d0_p0

                a0x, a0y = along(d0_p0)
                a1x, a1y = along(d1_p0)
                base_x, base_y = px(P0_phys[0], P0_phys[1])
                t0x = base_x + a0x
                t0y = base_y + a0y
                t1x = base_x + a1x
                t1y = base_y + a1y

                s0y = t0y - bd_gap
                s1y = t1y - bd_gap
                _bt0_bd = -bd_gap / _perp_y
                s0x = t0x + _bt0_bd * _perp_x
                _bt1_bd = -bd_gap / _perp_y
                s1x = t1x + _bt1_bd * _perp_x

                c.create_line(t0x, t0y, s0x, s0y, fill=BD_COLOR, width=1, tags="dim")
                c.create_line(t1x, t1y, s1x, s1y, fill=BD_COLOR, width=1, tags="dim")
                c.create_line(s0x, s0y, s1x, s1y,
                              arrow=tk.BOTH, fill=BD_COLOR, width=1, tags="dim")

                mx = (s0x + s1x) / 2
                my = (s0y + s1y) / 2
                seg_ft = seg_len / 12.0
                lbl = f"{seg_len:.1f}\" ({seg_ft:.1f}')"
                c.create_text(mx, my - 6,
                              text=lbl, fill=BD_COLOR,
                              font=("Segoe UI", 9),
                              anchor="s",
                              angle=_math.degrees(angle), tags="dim")

        # ── Stair angle arc indicator ──────────────────────────────────
        # Draw a protractor-style arc in the bottom-left corner of the
        # open triangle between the bottom-face dim line and the ground.
        import math as _math
        ang_deg = _math.degrees(angle)   # angle already computed above

        # Arc origin: where the bottom-face dimension line (extended)
        # meets the ground line.  This is the true vertex of the open
        # triangular space below the stringer.
        _, _ground_cy = px(0, 0)          # canvas y of ground
        _bfd_dx = bfd_x1 - bfd_x0        # dim line direction (canvas)
        _bfd_dy = bfd_y1 - bfd_y0
        if abs(_bfd_dy) > 0.01:
            _t_gnd = (_ground_cy - bfd_y0) / _bfd_dy
            _arc_gnd_x = bfd_x0 + _t_gnd * _bfd_dx
        else:
            _arc_gnd_x = bfd_x0
        # Shift the origin along the bisector of the angle so that
        # the arc has equal clearance from both the ground line and
        # the bottom-face dimension line.
        _arc_margin = 8   # desired clearance in pixels from each line
        _half_ang = _math.radians(ang_deg / 2)
        # Distance along bisector to achieve _arc_margin perpendicular
        # clearance from each bounding line:
        _bisect_dist = _arc_margin / _math.sin(_half_ang) if _half_ang > 0.01 else _arc_margin
        # Bisector direction in canvas coords (CCW ang_deg/2 from east,
        # canvas y is inverted so sin component is negated)
        arc_ox = _arc_gnd_x + _bisect_dist * _math.cos(_half_ang)
        arc_oy = _ground_cy - _bisect_dist * _math.sin(_half_ang)

        # Arc radius — scale with canvas but keep readable
        arc_r = max(28, min(55, usable_w * 0.10))

        # tkinter create_arc uses a bounding box; arc goes CCW from start angle.
        # tk angles: 0° = 3-o'clock (east), positive = CCW.
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
            stipple="gray25", tags="dim",
        )
        # Arc outline in the same colour, slightly bolder
        c.create_arc(
            arc_ox - arc_r, arc_oy - arc_r,
            arc_ox + arc_r, arc_oy + arc_r,
            start=arc_start, extent=arc_extent,
            style=tk.ARC,
            outline=arc_color, width=2, tags="dim",
        )

        # Radial line along the stringer direction (top edge of arc)
        rad_end_x = arc_ox + arc_r * _math.cos(_math.radians(ang_deg))
        rad_end_y = arc_oy - arc_r * _math.sin(_math.radians(ang_deg))
        c.create_line(arc_ox, arc_oy, rad_end_x, rad_end_y,
                      fill=arc_color, width=1, tags="dim")

        # Angle text label at mid-arc, just outside the arc
        label_r = arc_r + 10
        mid_ang_rad = _math.radians(ang_deg / 2)
        lbl_x = arc_ox + label_r * _math.cos(mid_ang_rad)
        lbl_y = arc_oy - label_r * _math.sin(mid_ang_rad)
        c.create_text(lbl_x, lbl_y,
                      text=f"{ang_deg:.1f}°",
                      fill=arc_color, font=("Segoe UI", 9, "bold"),
                      anchor="w", tags="dim")

        # Angle rating text just below the arc's horizontal edge
        if ANGLE_IDEAL_LO <= ang_deg <= ANGLE_IDEAL_HI:
            ang_rating = "Ideal"
        elif ANGLE_WARN_LO <= ang_deg < ANGLE_IDEAL_LO:
            ang_rating = "Slightly shallow"
        elif ANGLE_IDEAL_HI < ang_deg <= ANGLE_WARN_HI:
            ang_rating = "Slightly steep"
        elif ang_deg < ANGLE_WARN_LO:
            ang_rating = "Too shallow"
        else:
            ang_rating = "Too steep"
        c.create_text(arc_ox + arc_r / 2, arc_oy + 6,
                      text=ang_rating,
                      fill=arc_color, font=("Segoe UI", 9),
                      anchor="n", tags="dim")

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
            # Perpendicular extension meets axis-aligned y-offset (must match _redraw_canvas)
            _face_dx = P2cx - P3cx
            _face_dy = P2cy - P3cy
            _bperp_x = -_face_dy   # CW 90°
            _bperp_y =  _face_dx
            _bt = sdim_gap / _bperp_y if abs(_bperp_y) > 0.01 else 0
            bfd_x0 = P3cx + _bt * _bperp_x
            bfd_y0 = P3cy + sdim_gap
            bfd_x1 = P2cx + _bt * _bperp_x
            bfd_y1 = P2cy + sdim_gap

            # Right-wall / ground corner
            right_ground_cx = ox + total_run * scale
            right_ground_cy = oy

            # Incircle of the triangle (equal whitespace to all 3 edges)
            cx, cy, inradius = self._incircle(
                bfd_x0, bfd_y0,           # A: bottom-face dim start
                right_ground_cx, right_ground_cy,  # B: right/ground corner
                bfd_x1, bfd_y1,           # C: bottom-face dim end
            )
            # Scale circle to ~half the available triangle space
            tri_xs = [bfd_x0, right_ground_cx, bfd_x1]
            tri_ys = [bfd_y0, right_ground_cy, bfd_y1]
            tri_w = max(tri_xs) - min(tri_xs)
            tri_h = max(tri_ys) - min(tri_ys)
            radius = max(40, (1/6) * min(tri_w, tri_h))
        else:
            cx = cw - CANVAS_MARGIN - radius - 4
            cy = ch - CANVAS_MARGIN - radius - 4

        # Background circle
        c.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                      fill="#F0F0F0", outline="#999999", width=1)

        # Scale all internal sizes relative to radius (baseline 75px)
        k = radius / 75.0
        font_size = max(6, int(round(9 * k)))
        font_dim = ("Segoe UI", font_size)
        font_bold = ("Segoe UI", font_size, "bold")

        # Fit the step inside the circle with padding
        pad = 22 * k
        draw_w = radius * 2 - pad * 2
        draw_h = radius * 2 - pad * 2
        label_reserve = 14 * k
        draw_h -= label_reserve

        # Scale so both riser and tread fit
        s = min(draw_w / tread, draw_h / riser)

        step_w = tread * s
        step_h = riser * s

        # Position the step L-shape centred in available area
        avail_cx = cx
        avail_cy = cy + label_reserve / 2
        sx0 = avail_cx - step_w / 2
        sy1 = avail_cy + step_h / 2
        sx1 = sx0 + step_w
        sy0 = sy1 - step_h

        c.create_rectangle(sx0, sy0, sx1, sy1,
                           fill=STEP_FILL, outline=STEP_OUTLINE, width=max(1, int(2 * k)))

        # Riser dimension arrow (right side)
        arr_x = sx1 + 8 * k
        c.create_line(arr_x, sy1, arr_x, sy0,
                      arrow=tk.BOTH, fill=LABEL_COLOR, width=1)
        c.create_text(arr_x + 3 * k, (sy0 + sy1) / 2,
                      text=f"{riser:.3f}\"", fill=LABEL_COLOR,
                      font=font_dim, anchor="w")

        # Tread dimension arrow (below)
        arr_y = sy1 + 8 * k
        c.create_line(sx0, arr_y, sx1, arr_y,
                      arrow=tk.BOTH, fill=LABEL_COLOR, width=1)
        c.create_text((sx0 + sx1) / 2, arr_y + 3 * k,
                      text=f"{tread:.3f}\"", fill=LABEL_COLOR,
                      font=font_dim, anchor="n")

        # Diagonal hypotenuse dimension (lower-left to upper-right)
        import math as _math
        hyp = _math.hypot(riser, tread)
        c.create_line(sx0, sy1, sx1, sy0,
                      arrow=tk.BOTH, fill=LABEL_COLOR, width=1)
        # Label centred on the diagonal, offset toward upper-left
        diag_mx = (sx0 + sx1) / 2
        diag_my = (sy0 + sy1) / 2
        # Perpendicular offset (up-left from the line)
        diag_dx = sx1 - sx0
        diag_dy = sy0 - sy1  # negative because canvas y is flipped
        diag_len = _math.hypot(diag_dx, diag_dy) or 1
        perp_x = diag_dy / diag_len  # perpendicular unit (rotated 90° CCW)
        perp_y = -diag_dx / diag_len
        label_off = 8 * k
        c.create_text(diag_mx + perp_x * label_off, diag_my + perp_y * label_off,
                      text=f"{hyp:.3f}\"", fill=LABEL_COLOR,
                      font=font_dim, angle=_math.degrees(_math.atan2(riser, tread)))

        # 2R+T label centred between circle top and step top
        c.create_text(cx, (cy - radius + sy0) / 2,
                      text=f"2R+T = {rot:.2f}\"",
                      fill="#444455", font=font_bold)

    # ------------------------------------------------------------------
    # Materials list
    # ------------------------------------------------------------------

    def _draw_materials_list(self, c: tk.Canvas, cw: int, ch: int,
                             cfg: "StepConfig"):
        """Draw a materials summary box in the upper-left area below the step inset."""
        import math as _math

        n_risers = cfg.n_risers
        n_treads = n_risers - 2  # step treads only (exclude landing)
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

        # Stringer lumber length: use effective board length (accounts for
        # bottom plumb cut geometry) when available, else model value.
        eff_len = getattr(self, '_effective_stringer_len', cfg.stringer_length)
        sl_ft = eff_len / 12.0
        standard_lengths = [8, 10, 12, 14, 16, 18, 20]
        stringer_lumber_ft = self._stringer_lumber_ft
        if stringer_lumber_ft == 0:
            stringer_lumber_ft = standard_lengths[-1]
            for slen in standard_lengths:
                if slen >= sl_ft:
                    stringer_lumber_ft = slen
                    break
        lumber_in = stringer_lumber_ft * 12.0

        # Compute per-board segment lengths from snapped edges.
        # Edges are P0-relative slope distances; convert to board-start-
        # relative by adding _p0_offset so the first/last segments include
        # the plumb cut overhang.
        edges = getattr(self, '_board_slope_edges', [0.0, eff_len])
        stringer_len_stored = getattr(self, '_stringer_len_in', eff_len)
        # _p0_offset = stringer_len_in - top_face_len (edges[-1] is top_face_len)
        _p0_off = stringer_len_stored - edges[-1]
        breaks = [e + _p0_off for e in edges]
        # Ensure first break starts at 0 and last at stringer_len
        breaks[0] = 0.0
        breaks[-1] = stringer_len_stored
        segment_lengths = []
        for i in range(len(breaks) - 1):
            segment_lengths.append(breaks[i + 1] - breaks[i])
        boards_per_stringer = len(segment_lengths) if segment_lengths else 1
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
            # List each segment's required cut length and minimum lumber size
            for si, seg_len in enumerate(segment_lengths):
                seg_ft = seg_len / 12.0
                # Find shortest standard lumber that covers this segment
                min_lumber_ft = standard_lengths[-1]
                for slen in standard_lengths:
                    if slen >= seg_ft:
                        min_lumber_ft = slen
                        break
                c.create_text(box_x + 8, y,
                              text=f"{stringer_count}x  2x12 x {min_lumber_ft}' — board {si+1} ({seg_len:.1f}\" cut)",
                              fill=body_color, font=body_font, anchor="nw")
                y += line_h
            c.create_text(box_x + 8, y,
                          text=f"Joins at riser bases — {boards_per_stringer} boards/stringer",
                          fill="#777777", font=("Segoe UI", 8), anchor="nw")
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
            y += line_h

        # --- Wall-mount through bolts ---
        anchor_count = getattr(self, '_anchor_count', 0)
        if anchor_count > 0:
            y += 4
            c.create_line(box_x, y - 2, box_x + 180, y - 2,
                          fill="#AAAAAA", width=1)
            c.create_text(box_x, y, text="Through Bolts:",
                          fill=hdr_color, font=("Segoe UI", 9, "bold"), anchor="nw")
            y += line_h
            bolt_dia_frac = f'{ANCHOR_BOLT_DIAMETER:.0f}"' if ANCHOR_BOLT_DIAMETER >= 1 else f'1/2"'
            c.create_text(box_x + 8, y,
                          text=f"{anchor_count}x  {bolt_dia_frac} through bolt at supports",
                          fill=body_color, font=body_font, anchor="nw")
