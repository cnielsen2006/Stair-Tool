import os
from datetime import datetime
from io import BytesIO
from tkinter import filedialog, messagebox

from PIL import ImageGrab
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as pdfcanvas


def _dpi_scale() -> float:
    """Return screen DPI scale factor (1.0 on non-Windows or when unavailable).

    ImageGrab captures at physical pixels; tkinter winfo_* returns virtualized
    coordinates when the process is not DPI-aware. Multiply to reconcile.
    """
    if os.name != "nt":
        return 1.0
    try:
        import ctypes
        return ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100.0
    except Exception:
        return 1.0


def _widget_bbox(widget) -> tuple[int, int, int, int]:
    widget.update_idletasks()
    s = _dpi_scale()
    x = int(widget.winfo_rootx() * s)
    y = int(widget.winfo_rooty() * s)
    w = int(widget.winfo_width() * s)
    h = int(widget.winfo_height() * s)
    return (x, y, x + w, y + h)


def _grab(widget):
    widget.update_idletasks()
    return ImageGrab.grab(bbox=_widget_bbox(widget), all_screens=True)


def _ask_path(default_name: str) -> str | None:
    return filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        initialfile=default_name,
    ) or None


def _draw_image_fitted(pdf, image, x, y, max_w, max_h):
    iw, ih = image.size
    scale = min(max_w / iw, max_h / ih)
    w, h = iw * scale, ih * scale
    buf = BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    from reportlab.lib.utils import ImageReader
    pdf.drawImage(ImageReader(buf), x + (max_w - w) / 2, y + (max_h - h) / 2,
                  width=w, height=h, preserveAspectRatio=True, mask="auto")


def export_diagram_pdf(canvas_widget, stat_vars: dict, title: str = "Stair Diagram"):
    path = _ask_path(f"stair_diagram_{datetime.now():%Y%m%d_%H%M%S}.pdf")
    if not path:
        return
    try:
        img = _grab(canvas_widget)
        pdf = pdfcanvas.Canvas(path, pagesize=landscape(letter))
        pw, ph = landscape(letter)
        margin = 0.5 * inch

        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(margin, ph - margin, title)
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(pw - margin, ph - margin,
                            datetime.now().strftime("%Y-%m-%d %H:%M"))

        _draw_image_fitted(pdf, img,
                           margin, margin,
                           pw - 2 * margin, ph - 2 * margin - 0.4 * inch)
        pdf.save()
        _open_file(path)
    except Exception as exc:
        messagebox.showerror("Export failed", str(exc))


def export_report_pdf(root_widget, canvas_widget, inputs: dict, stat_vars: dict,
                      title: str = "Stair Calculator Report"):
    path = _ask_path(f"stair_report_{datetime.now():%Y%m%d_%H%M%S}.pdf")
    if not path:
        return
    try:
        window_img = _grab(root_widget)
        pdf = pdfcanvas.Canvas(path, pagesize=letter)
        pw, ph = letter
        margin = 0.5 * inch

        # --- Page 1: summary + inputs ---
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(margin, ph - margin, title)
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(pw - margin, ph - margin,
                            datetime.now().strftime("%Y-%m-%d %H:%M"))

        y = ph - margin - 0.4 * inch

        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin, y, "Results")
        y -= 0.22 * inch

        pdf.setFont("Helvetica", 10)
        result_rows = [
            ("Riser Height", stat_vars.get("riser", "")),
            ("Tread Depth", stat_vars.get("tread", "")),
            ("2R + T (comfort)", stat_vars.get("rot", "")),
            ("Status", stat_vars.get("status", "")),
            ("Stringer Length", stat_vars.get("stringer", "")),
            ("Stringer (feet)", stat_vars.get("stringer_ft", "")),
            ("Support Uprights", stat_vars.get("supports", "")),
            ("Through Bolts", stat_vars.get("bolts", "")),
        ]
        for label, value in result_rows:
            pdf.drawString(margin, y, f"{label}:")
            pdf.drawString(margin + 1.6 * inch, y, str(value))
            y -= 0.2 * inch

        y -= 0.15 * inch
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin, y, "Inputs")
        y -= 0.22 * inch

        pdf.setFont("Helvetica", 10)
        input_rows = [
            ("Total Rise", f"{inputs.get('total_rise', 0):.2f} in"),
            ("Total Run", f"{inputs.get('total_run', 0):.2f} in"),
            ("Rise Range", f"{inputs.get('min_rise', 0):.2f}\u2013{inputs.get('max_rise', 0):.2f} in"),
            ("Tread Range", f"{inputs.get('min_tread', 0):.2f}\u2013{inputs.get('max_tread', 0):.2f} in"),
            ("Stringers", str(inputs.get("stringer_count", ""))),
            ("Stair Width", f"{inputs.get('stair_width', 0):.2f} in"),
            ("Tread Lumber", inputs.get("tread_board_label", "")),
            ("Board Gap", f"{inputs.get('tread_board_gap', 0):.2f} in"),
            ("Nosing Overhang", f"{inputs.get('nosing_overhang', 0):.2f} in"),
            ("Stringer Lumber", f"{inputs.get('stringer_lumber_ft', 0)}'"
                                if inputs.get("stringer_lumber_ft") else "Auto"),
            ("Support Every", f"{inputs.get('support_every_n', 0)} steps"),
            ("Bottom Plumb Cut", "Yes" if inputs.get("bottom_plumb_cut") else "No"),
        ]
        for label, value in input_rows:
            pdf.drawString(margin, y, f"{label}:")
            pdf.drawString(margin + 1.6 * inch, y, str(value))
            y -= 0.2 * inch

        # Diagram on same page if space allows, else new page
        diagram_img = _grab(canvas_widget)
        if y - margin > 3 * inch:
            _draw_image_fitted(pdf, diagram_img,
                               margin, margin,
                               pw - 2 * margin, y - margin - 0.2 * inch)
        else:
            pdf.showPage()
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(margin, ph - margin, "Diagram")
            _draw_image_fitted(pdf, diagram_img,
                               margin, margin,
                               pw - 2 * margin, ph - 2 * margin - 0.4 * inch)

        # --- Page: full window screenshot ---
        pdf.showPage()
        pdf.setPageSize(landscape(letter))
        lw, lh = landscape(letter)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(margin, lh - margin, "Application View")
        _draw_image_fitted(pdf, window_img,
                           margin, margin,
                           lw - 2 * margin, lh - 2 * margin - 0.4 * inch)

        pdf.save()
        _open_file(path)
    except Exception as exc:
        messagebox.showerror("Export failed", str(exc))


def _open_file(path: str):
    try:
        if os.name == "nt":
            os.startfile(path)
        elif os.name == "posix":
            import subprocess
            opener = "open" if os.uname().sysname == "Darwin" else "xdg-open"
            subprocess.Popen([opener, path])
    except Exception:
        pass
