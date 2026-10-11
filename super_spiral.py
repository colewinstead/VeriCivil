"""Unmodified clothoid geometry, evaluated by bounded adaptive Simpson integration.

Coordinates are easting/northing; curvature is signed positive counterclockwise.
This is geometry evaluation, not horizontal alignment design.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


def _integral(function, end: float, tolerance: float) -> float:
    def recurse(a, b, fa, fm, fb, whole, tol, depth):
        middle = (a + b) / 2
        left_mid, right_mid = (a + middle) / 2, (middle + b) / 2
        fl, fr = function(left_mid), function(right_mid)
        left = (middle - a) * (fa + 4 * fl + fm) / 6
        right = (b - middle) * (fm + 4 * fr + fb) / 6
        delta = left + right - whole
        if abs(delta) <= 15 * tol:
            return left + right + delta / 15
        if depth == 0:
            raise ValueError(
                "Clothoid integration did not converge; geometry is unsupported."
            )
        return recurse(a, middle, fa, fl, fm, left, tol / 2, depth - 1) + recurse(
            middle, b, fm, fr, fb, right, tol / 2, depth - 1
        )

    if end == 0:
        return 0.0
    a, m, b = function(0), function(end / 2), function(end)
    return recurse(0, end, a, m, b, end * (a + 4 * m + b) / 6, tolerance, 24)


@dataclass(frozen=True)
class SpiralSegment:
    start: tuple[float, float]
    end: tuple[float, float]
    length: float
    heading: float
    start_curvature: float
    end_curvature: float
    rotation: str

    def angle(self, distance: float) -> float:
        return (
            self.heading
            + self.start_curvature * distance
            + (self.end_curvature - self.start_curvature)
            * distance**2
            / (2 * self.length)
        )

    def xy(self, distance: float) -> tuple[float, float]:
        if not 0 <= distance <= self.length + 1e-8:
            raise ValueError("Distance outside clothoid limits.")
        distance = min(distance, self.length)
        # Partition by angle to avoid Simpson aliasing on long clothoids.
        count = max(
            1,
            math.ceil(
                max(abs(self.start_curvature), abs(self.end_curvature))
                * distance
                / 0.25
            ),
        )
        if count > 10000:
            raise ValueError(
                "Clothoid exceeds the verified numerical evaluation scope."
            )
        step = distance / count

        def integrate(function):
            return math.fsum(
                _integral(
                    lambda s: function(self.angle(i * step + s)), step, 1e-7 / count
                )
                for i in range(count)
            )

        return self.start[0] + integrate(math.cos), self.start[1] + integrate(math.sin)

    def tangent(self, distance: float) -> tuple[float, float]:
        if not 0 <= distance <= self.length + 1e-8:
            raise ValueError("Distance outside clothoid limits.")
        angle = self.angle(distance)
        return math.cos(angle), math.sin(angle)
