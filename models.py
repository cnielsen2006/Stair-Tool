import math
from dataclasses import dataclass
from typing import List, Optional

from constants import (
    DEFAULT_MIN_RISE, DEFAULT_MAX_RISE,
    DEFAULT_MIN_TREAD, DEFAULT_MAX_TREAD,
    IDEAL_RISE, IDEAL_TREAD,
)

# IBC R507.9.1: stringer max unsupported span is 13'-1" (157") for 2x lumber
# Practical recommendation: support every 6–8 ft (72–96") for residential
STRINGER_MAX_SPAN_IN = 96.0   # 8 ft — comfortable residential support spacing


@dataclass
class StepConfig:
    n_steps: int          # number of risers
    riser_height: float   # inches
    tread_depth: float    # inches
    score: float          # lower is better
    is_valid: bool
    rule_of_thumb: float  # 2*rise + tread (ideal: 24-25)
    stringer_length: float = 0.0      # diagonal length of stringer (inches)
    support_count: int    = 0         # number of intermediate supports needed
    support_spacing: float = 0.0      # spacing between supports (inches)


class StairModel:
    def __init__(
        self,
        total_rise: float,
        total_run: float,
        min_rise: float = DEFAULT_MIN_RISE,
        max_rise: float = DEFAULT_MAX_RISE,
        min_tread: float = DEFAULT_MIN_TREAD,
        max_tread: float = DEFAULT_MAX_TREAD,
    ):
        self.total_rise = total_rise
        self.total_run  = total_run
        self.min_rise   = min_rise
        self.max_rise   = max_rise
        self.min_tread  = min_tread
        self.max_tread  = max_tread

    def _score(self, riser: float, tread: float) -> float:
        rise_range  = max(self.max_rise  - self.min_rise,  0.01)
        tread_range = max(self.max_tread - self.min_tread, 0.01)
        dr = (riser - IDEAL_RISE)  / rise_range
        dt = (tread - IDEAL_TREAD) / tread_range
        return dr ** 2 + dt ** 2

    def compute_configs(self) -> List[StepConfig]:
        """
        Compute StepConfig for every plausible N.
        Convention: N risers, N-1 treads.
          riser = total_rise / N
          tread = total_run  / (N-1)
        """
        if self.total_rise <= 0 or self.total_run <= 0:
            return []

        # Valid N from rise constraint
        n_min_rise = math.ceil(self.total_rise / self.max_rise)
        n_max_rise = math.floor(self.total_rise / self.min_rise)

        # Valid N from tread constraint (N-1 treads)
        n_min_tread = math.ceil(self.total_run / self.max_tread) + 1
        n_max_tread = math.floor(self.total_run / self.min_tread) + 1

        n_min_valid = max(n_min_rise, n_min_tread, 2)
        n_max_valid = min(n_max_rise, n_max_tread)

        # Expand search range to show nearby out-of-range configs too
        n_lo = max(2, min(n_min_rise, n_min_tread) - 1)
        n_hi = max(n_max_rise, n_max_tread) + 1

        configs = []
        for n in range(n_lo, n_hi + 1):
            riser = self.total_rise / n
            tread = self.total_run / (n - 1)
            valid = (
                self.min_rise  <= riser <= self.max_rise and
                self.min_tread <= tread <= self.max_tread
            )
            s   = self._score(riser, tread)
            rot = 2 * riser + tread

            # Stringer diagonal: hypotenuse of total_rise × total_run triangle
            stringer_len = math.sqrt(self.total_rise ** 2 + self.total_run ** 2)

            # Intermediate supports: how many posts/hangers needed between top and bottom
            # bearing points, keeping each span ≤ STRINGER_MAX_SPAN_IN
            n_supports = max(0, math.ceil(stringer_len / STRINGER_MAX_SPAN_IN) - 1)
            if n_supports > 0:
                spacing = stringer_len / (n_supports + 1)
            else:
                spacing = stringer_len  # no intermediate support needed

            configs.append(StepConfig(n, riser, tread, s, valid, rot,
                                      stringer_len, n_supports, spacing))

        return configs

    def valid_configs(self) -> List[StepConfig]:
        return [c for c in self.compute_configs() if c.is_valid]

    def optimal_config(self) -> Optional[StepConfig]:
        valids = self.valid_configs()
        if not valids:
            return None
        return min(valids, key=lambda c: c.score)

    def valid_n_range(self) -> tuple[int, int] | tuple[None, None]:
        valids = self.valid_configs()
        if not valids:
            return None, None
        ns = [c.n_steps for c in valids]
        return min(ns), max(ns)
