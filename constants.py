# IBC/IRC defaults (all values in inches)
DEFAULT_MIN_RISE  = 4.0
DEFAULT_MAX_RISE  = 7.75
DEFAULT_MIN_TREAD = 10.0
DEFAULT_MAX_TREAD = 11.0
IDEAL_RISE        = 7.0
IDEAL_TREAD       = 11.0

# Slider ranges for total rise and run
RISE_MIN_IN = 24.0    # 2 ft
RISE_MAX_IN = 180.0   # 15 ft
RUN_MIN_IN  = 36.0    # 3 ft
RUN_MAX_IN  = 240.0   # 20 ft

# Canvas
CANVAS_WIDTH  = 600
CANVAS_HEIGHT = 450
CANVAS_MARGIN = 50

# Colors
DIAGRAM_BG    = "#FAFAFA"
STEP_FILL     = "#D0E8FF"
STEP_OUTLINE  = "#2060A0"
LABEL_COLOR   = "#C03000"
GROUND_COLOR  = "#888888"
OPTIMAL_COLOR = "#007700"
INVALID_COLOR = "#CC0000"

# Construction defaults
DEFAULT_STRINGER_COUNT = 3       # typical residential: 3 stringers
DEFAULT_STAIR_WIDTH    = 36.0    # inches (IBC min 36")
DEFAULT_TREAD_BOARD_WIDTH = 5.5  # nominal 1×6 actual width (inches)
DEFAULT_TREAD_BOARD_GAP = 0.25   # gap between tread boards (inches)
DEFAULT_NOSING_OVERHANG = 0.75   # acceptable nosing overhang past last board (inches)
DEFAULT_STRINGER_LUMBER_FT = 0   # 0 = auto (pick shortest standard length)

# Standard dimensional lumber lengths (feet)
STRINGER_LUMBER_OPTIONS = [0, 8, 10, 12, 14, 16, 18, 20]  # 0 = auto

# Common tread board widths (actual dimensions, inches)
TREAD_BOARD_OPTIONS = {
    "1x6 (5.5\")":  5.5,
    "1x8 (7.25\")": 7.25,
    "1x10 (9.25\")": 9.25,
    "1x12 (11.25\")": 11.25,
    "2x6 (5.5\")":  5.5,
    "2x8 (7.25\")": 7.25,
    "2x10 (9.25\")": 9.25,
    "2x12 (11.25\")": 11.25,
    "5/4x6 (5.5\")": 5.5,
}

# Persistence
SETTINGS_FILE = "stair_settings.json"

# Ergonomic comfort (2R + T formula, all in inches)
# Ideal range: 24"–25". Outside 22"–27" is uncomfortable.
COMFORT_IDEAL_LO = 24.0
COMFORT_IDEAL_HI = 25.0
COMFORT_WARN_LO  = 22.0   # below → too steep
COMFORT_WARN_HI  = 27.0   # above → too shallow/long stride

# Stair angle (degrees from horizontal)
# IBC residential: rise 4"–7.75" over tread 10"–11" → ~20°–38°
# Ergonomic ideal: 30°–35°.  Outside 25°–40° is uncomfortable.
ANGLE_IDEAL_LO = 30.0
ANGLE_IDEAL_HI = 35.0
ANGLE_WARN_LO  = 25.0   # below → too shallow (long stride, trip risk)
ANGLE_WARN_HI  = 40.0   # above → too steep (fatigue, fall risk)
