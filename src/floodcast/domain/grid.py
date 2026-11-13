"""Regular raster grid used by the DEM and the inundation result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from floodcast.domain.checks import (
    require_exact_keys,
    require_finite,
    require_nonempty_str,
    require_object,
    require_positive,
    require_positive_int,
)
from floodcast.errors import DomainError


@dataclass(frozen=True, slots=True)
class GridSpec:
    """North-up regular grid in a local metric plane.

    ``origin_x_m`` is the left edge of column 0. ``origin_y_m`` is the top
    edge of row 0. Row index increases southward, so this lines up with a
    raster overlay rather than a south-up geographic axis.

    The sample data uses ``crs="LOCAL"``. It is a demo meter grid, not a
    surveyed CRS and not longitude/latitude.
    """

    ncols: int
    nrows: int
    cell_size_m: float
    origin_x_m: float = 0.0
    origin_y_m: float = 0.0
    crs: str = "LOCAL"

    def __post_init__(self) -> None:
        ncols = require_positive_int(self.ncols, "ncols")
        nrows = require_positive_int(self.nrows, "nrows")
        cell_size_m = require_positive(self.cell_size_m, "cell_size_m")
        origin_x_m = require_finite(self.origin_x_m, "origin_x_m")
        origin_y_m = require_finite(self.origin_y_m, "origin_y_m")
        crs = require_nonempty_str(self.crs, "crs").strip()
        if not crs:
            raise DomainError("crs must be a non-empty string")
        object.__setattr__(self, "ncols", ncols)
        object.__setattr__(self, "nrows", nrows)
        object.__setattr__(self, "cell_size_m", cell_size_m)
        object.__setattr__(self, "origin_x_m", origin_x_m)
        object.__setattr__(self, "origin_y_m", origin_y_m)
        object.__setattr__(self, "crs", crs)

    @property
    def cell_area_m2(self) -> float:
        return self.cell_size_m * self.cell_size_m

    @property
    def width_m(self) -> float:
        return self.ncols * self.cell_size_m

    @property
    def height_m(self) -> float:
        return self.nrows * self.cell_size_m

    def check_index(self, row: int, col: int) -> None:
        if isinstance(row, bool) or not isinstance(row, int) or not 0 <= row < self.nrows:
            raise DomainError(f"row {row} is outside 0..{self.nrows - 1}")
        if isinstance(col, bool) or not isinstance(col, int) or not 0 <= col < self.ncols:
            raise DomainError(f"col {col} is outside 0..{self.ncols - 1}")

    def cell_center(self, row: int, col: int) -> tuple[float, float]:
        """Return the cell center as ``(x_m, y_m)`` in this grid's plane."""
        self.check_index(row, col)
        x_m = self.origin_x_m + (col + 0.5) * self.cell_size_m
        y_m = self.origin_y_m - (row + 0.5) * self.cell_size_m
        return (x_m, y_m)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ncols": self.ncols,
            "nrows": self.nrows,
            "cell_size_m": self.cell_size_m,
            "origin_x_m": self.origin_x_m,
            "origin_y_m": self.origin_y_m,
            "crs": self.crs,
        }

    @classmethod
    def from_dict(cls, data: object) -> GridSpec:
        payload = require_object(data, "grid spec")
        require_exact_keys(
            payload,
            required=(
                "ncols",
                "nrows",
                "cell_size_m",
                "origin_x_m",
                "origin_y_m",
                "crs",
            ),
            field="grid spec",
        )
        return cls(
            ncols=payload["ncols"],
            nrows=payload["nrows"],
            cell_size_m=payload["cell_size_m"],
            origin_x_m=payload["origin_x_m"],
            origin_y_m=payload["origin_y_m"],
            crs=payload["crs"],
        )
