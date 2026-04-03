# Stair Tool

A desktop stair calculator built with Python and tkinter that computes optimal step configurations from total rise and run dimensions, validated against IBC/IRC building code constraints.

![Stair Tool Screenshot](docs/screenshot.png)

---

## Features

- **Interactive sliders** for total rise and run (in inches)
  - Mouse-wheel scrolling on sliders; **Shift+scroll for fine-tuning** (5× slower)
- **Per-step constraint controls** — adjustable min/max riser height and tread depth (IBC/IRC defaults pre-loaded)
- **Optimal step count selection** — scores all valid N values by closeness to ideal rise (7") and tread (11")
- **Step count selector** — spinbox in the left panel lets you pick any step count (including landing); constraints never override your choice
- **Construction details** — stringer count, stair width, tread lumber size, board gap, nosing overhang, and stringer lumber length inputs
- **Live stair diagram** — scaled canvas drawing with:
  - Step profile and filled rectangles
  - First-riser and first-tread dimension arrows
  - Overall rise/run dimension callouts
  - 2×12 stringer overlay with plumb end cuts, notch marks, and full 4-side dimensioning
  - Stair angle arc indicator (color-coded ideal/warn/bad zones)
  - Intermediate support markers when stringer span exceeds 8 ft
  - **Materials list** — stringers, treads, and stringer-cut dimensions (tread seat, riser seat, notch depth, throat) in the upper-left whitespace
  - **Step detail inset** — zoomed single-step view inscribed in the lower-right whitespace triangle (incircle positioning)
- **Results summary** — riser, tread, 2R+T (with comfort rating), stringer length/angle, stair angle (with ideal/warn/bad rating), support count/spacing, inline comfort gauge bar
- **Board join markers** — when selected lumber is shorter than the stringer, perpendicular join lines and per-segment dimension callouts are drawn along the stringer
- **Single-instance enforcement** — only one window can run at a time; re-launching brings the existing window to front
- **Settings persistence** — all inputs (dimensions, constraints, construction details) saved and restored on next launch
- **Reset button** — one click back to IBC/IRC defaults (Ctrl+R shortcut)

---

## IBC/IRC Defaults

| Parameter     | Min    | Max    | Ideal  |
|---------------|--------|--------|--------|
| Riser Height  | 4.00"  | 7.75"  | 7.00"  |
| Tread Depth   | 10.00" | 11.00" | 11.00" |
| 2R + T        | —      | —      | 24–25" |
| Stair Angle   | 25°    | 40°    | 30°–35°|

---

## Step Count Convention

- **N** = number of risers
- **N − 1** = number of treads
- `riser = total_rise / N`
- `tread = total_run / (N − 1)`

---

## Requirements

- Python 3.10+ (3.14 recommended)
- tkinter (included with standard Python on Windows)

No third-party packages required.

---

## Running

```bash
python main.py
```

---

## Project Structure

```
Stair-Tool/
├── main.py                  # Entry point
├── app.py                   # App controller (root window, wires panels)
├── models.py                # StairModel + StepConfig (pure logic)
├── constants.py             # IBC/IRC defaults, canvas sizes, colors
├── stairs.ico               # App icon
├── launch.bat               # Windows launcher script
├── panels/
│   ├── input_panel.py       # Left panel: sliders + constraints + step count + construction inputs
│   └── results_panel.py     # Right panel: canvas diagram + results summary
├── widgets/
│   ├── labeled_slider.py    # LabeledSlider: Scale + Entry two-way binding
│   └── constraint_row.py    # ConstraintRow: min/max entry pair
└── docs/
    └── screenshot.png
```
