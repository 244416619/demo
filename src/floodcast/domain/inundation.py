"""Inundation depth raster and the wet-dry mask derived from it.

Thresholding a depth grid classifies cells that are already wet. It does
not turn rainfall and a DEM into flood depth. That calculation belongs to
a later unit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from floodcast.domain.checks import (
    require_bool_grid,
    require_exact_keys,
    require_float_grid,
    require_non_negative,
    require_object,
    require_positive,
)
from floodcast.domain.grid import GridSpec
from floodcast.errors import DomainError


@dataclass(frozen=True, slots=True)
class WetDryMask:
    """Boolean mask aligned to a grid. True means the cell is inundated."""

    spec: GridSpec
    wet: tuple[tuple[bool, ...], ...]
    threshold_m: float

    def __post_init__(self) -> None:
        if not isinstance(self.spec, GridSpec):
            raise TypeError("spec must be a GridSpec")
        wet = require_bool_grid(
            self.wet,
            nrows=self.spec.nrows,
            ncols=self.spec.ncols,
            field="wet",
        )
        threshold_m = require_positive(self.threshold_m, "threshold_m")
        object.__setattr__(self, "wet", wet)
        object.__setattr__(self, "threshold_m", threshold_m)

    @property
    def wet_cell_count(self) -> int:
        return sum(1 for row in self.wet for cell in row if cell)

    @property
    def inundated_area_m2(self) -> float:
        return self.wet_cell_count * self.spec.cell_area_m2

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "threshold_m": self.threshold_m,
            "wet": [list(row) for row in self.wet],
        }

    @classmethod
    def from_dict(cls, data: object) -> WetDryMask:
        payload = require_object(data, "wet-dry mask")
        require_exact_keys(
            payload,
            required=("spec", "threshold_m", "wet"),
            field="wet-dry mask",
        )
        return cls(
            spec=GridSpec.from_dict(payload["spec"]),
            threshold_m=payload["threshold_m"],
            wet=payload["wet"],
        )


@dataclass(frozen=True, slots=True)
class InundationRaster:
    """Water depth above the land surface, in meters, on ``spec``.

    Zero is dry. A cell is wet when its depth is at least
    ``wet_threshold_m`` (default 1 cm). Depth is an input to this type,
    not something this type computes from rainfall.
    """

    spec: GridSpec
    depth_m: tuple[tuple[float, ...], ...]
    wet_threshold_m: float = 0.01

    def __post_init__(self) -> None:
        if not isinstance(self.spec, GridSpec):
            raise TypeError("spec must be a GridSpec")
        depth_m = require_float_grid(
            self.depth_m,
            nrows=self.spec.nrows,
            ncols=self.spec.ncols,
            field="depth_m",
            coerce=require_non_negative,
        )
        wet_threshold_m = require_positive(self.wet_threshold_m, "wet_threshold_m")
        object.__setattr__(self, "depth_m", depth_m)
        object.__setattr__(self, "wet_threshold_m", wet_threshold_m)

    def depth_at(self, row: int, col: int) -> float:
        self.spec.check_index(row, col)
        return self.depth_m[row][col]

    @property
    def max_depth_m(self) -> float:
        return max(value for row in self.depth_m for value in row)

    @property
    def wet_cell_count(self) -> int:
        return self.wet_mask().wet_cell_count

    @property
    def inundated_area_m2(self) -> float:
        return self.wet_cell_count * self.spec.cell_area_m2

    def wet_mask(self) -> WetDryMask:
        """Classify an existing depth grid. This is not a flood forecast."""
        threshold = self.wet_threshold_m
        wet = tuple(
            tuple(value >= threshold for value in row) for row in self.depth_m
        )
        return WetDryMask(spec=self.spec, wet=wet, threshold_m=threshold)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "wet_threshold_m": self.wet_threshold_m,
            "depth_m": [list(row) for row in self.depth_m],
        }

    @classmethod
    def from_dict(cls, data: object) -> InundationRaster:
        payload = require_object(data, "inundation raster")
        require_exact_keys(
            payload,
            required=("spec", "depth_m"),
            optional=("wet_threshold_m",),
            field="inundation raster",
        )
        kwargs: dict[str, Any] = {
            "spec": GridSpec.from_dict(payload["spec"]),
            "depth_m": payload["depth_m"],
        }
        if "wet_threshold_m" in payload:
            kwargs["wet_threshold_m"] = payload["wet_threshold_m"]
        return cls(**kwargs)


def assert_same_grid(left: GridSpec, right: GridSpec, message: str) -> None:
    if left != right:
        raise DomainError(message)
