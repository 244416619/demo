"""Digital elevation model on a regular grid."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from floodcast.domain.checks import (
    require_exact_keys,
    require_finite,
    require_float_grid,
    require_object,
    require_slug,
    require_text,
)
from floodcast.domain.grid import GridSpec
from floodcast.errors import DomainError


@dataclass(frozen=True, slots=True)
class DigitalElevationModel:
    """Land-surface elevation sampled on ``spec``.

    ``elevations_m`` is row-major, north to south, in meters above
    ``vertical_datum``. ``nodata`` marks cells with no elevation. This unit
    only stores the grid; it does not fill sinks or route water.
    """

    id: str
    spec: GridSpec
    elevations_m: tuple[tuple[float, ...], ...]
    description: str = ""
    vertical_datum: str = "local meters"
    nodata: float | None = None

    def __post_init__(self) -> None:
        slug = require_slug(self.id, "dem id")
        if not isinstance(self.spec, GridSpec):
            raise TypeError("spec must be a GridSpec")
        elevations = require_float_grid(
            self.elevations_m,
            nrows=self.spec.nrows,
            ncols=self.spec.ncols,
            field="elevations_m",
            coerce=require_finite,
        )
        description = require_text(self.description, "description")
        vertical_datum = require_text(self.vertical_datum, "vertical_datum").strip()
        if not vertical_datum:
            raise DomainError("vertical_datum must be a non-empty string")
        nodata = None if self.nodata is None else require_finite(self.nodata, "nodata")
        object.__setattr__(self, "id", slug)
        object.__setattr__(self, "elevations_m", elevations)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "vertical_datum", vertical_datum)
        object.__setattr__(self, "nodata", nodata)

    def elevation_at(self, row: int, col: int) -> float:
        self.spec.check_index(row, col)
        return self.elevations_m[row][col]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "vertical_datum": self.vertical_datum,
            "nodata": self.nodata,
            "spec": self.spec.to_dict(),
            "elevations_m": [list(row) for row in self.elevations_m],
        }

    @classmethod
    def from_dict(cls, data: object) -> DigitalElevationModel:
        payload = require_object(data, "dem")
        require_exact_keys(
            payload,
            required=("id", "description", "spec", "elevations_m"),
            optional=("vertical_datum", "nodata"),
            field="dem",
        )
        kwargs: dict[str, Any] = {
            "id": payload["id"],
            "description": payload["description"],
            "spec": GridSpec.from_dict(payload["spec"]),
            "elevations_m": payload["elevations_m"],
        }
        if "vertical_datum" in payload:
            kwargs["vertical_datum"] = payload["vertical_datum"]
        if "nodata" in payload and payload["nodata"] is not None:
            kwargs["nodata"] = payload["nodata"]
        return cls(**kwargs)
