"""Scenario inputs and the metadata a later engine will attach to a run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from floodcast.domain.checks import (
    require_exact_keys,
    require_non_negative,
    require_non_negative_int,
    require_nonempty_str,
    require_object,
    require_positive,
    require_positive_int,
    require_slug,
    require_text,
)
from floodcast.domain.dem import DigitalElevationModel
from floodcast.domain.inundation import InundationRaster, assert_same_grid
from floodcast.domain.rainfall import RainfallSeries
from floodcast.errors import DomainError


@dataclass(frozen=True, slots=True)
class ScenarioDocument:
    """Scenario file shape: ids only, no embedded grids.

    The HTTP API can pass this document around. ``Scenario`` is what you
    get after the DEM and rainfall objects have been joined.
    """

    scenario_id: str
    name: str
    dem_id: str
    rainfall_id: str
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", require_slug(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "name", require_nonempty_str(self.name, "name"))
        object.__setattr__(self, "dem_id", require_slug(self.dem_id, "dem_id"))
        object.__setattr__(
            self, "rainfall_id", require_slug(self.rainfall_id, "rainfall_id")
        )
        object.__setattr__(self, "description", require_text(self.description, "description"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "dem_id": self.dem_id,
            "rainfall_id": self.rainfall_id,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: object) -> ScenarioDocument:
        payload = require_object(data, "scenario")
        require_exact_keys(
            payload,
            required=("scenario_id", "name", "dem_id", "rainfall_id", "description"),
            field="scenario",
        )
        return cls(
            scenario_id=payload["scenario_id"],
            name=payload["name"],
            dem_id=payload["dem_id"],
            rainfall_id=payload["rainfall_id"],
            description=payload["description"],
        )


@dataclass(frozen=True, slots=True)
class Scenario:
    """One what-if: a DEM plus a rainfall series.

    Building a scenario does not run a flood model.
    """

    scenario_id: str
    name: str
    dem: DigitalElevationModel
    rainfall: RainfallSeries
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", require_slug(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "name", require_nonempty_str(self.name, "name"))
        if not isinstance(self.dem, DigitalElevationModel):
            raise TypeError("dem must be a DigitalElevationModel")
        if not isinstance(self.rainfall, RainfallSeries):
            raise TypeError("rainfall must be a RainfallSeries")
        object.__setattr__(self, "description", require_text(self.description, "description"))

    def to_document(self) -> ScenarioDocument:
        return ScenarioDocument(
            scenario_id=self.scenario_id,
            name=self.name,
            dem_id=self.dem.id,
            rainfall_id=self.rainfall.id,
            description=self.description,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.to_document().to_dict()


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Summary metadata for one finished scenario.

    A later prediction unit fills these fields from an ``InundationRaster``.
    ``from_inundation`` only reduces a depth grid that already exists
    (max depth, wet-cell count, area). It does not generate that grid.
    """

    scenario_id: str
    dem_id: str
    rainfall_id: str
    max_depth_m: float
    inundated_area_m2: float
    wet_cell_count: int
    cell_count: int
    rainfall_total_mm: float
    duration_hours: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", require_slug(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "dem_id", require_slug(self.dem_id, "dem_id"))
        object.__setattr__(self, "rainfall_id", require_slug(self.rainfall_id, "rainfall_id"))
        max_depth_m = require_non_negative(self.max_depth_m, "max_depth_m")
        inundated_area_m2 = require_non_negative(
            self.inundated_area_m2, "inundated_area_m2"
        )
        wet_cell_count = require_non_negative_int(self.wet_cell_count, "wet_cell_count")
        cell_count = require_positive_int(self.cell_count, "cell_count")
        if wet_cell_count > cell_count:
            raise DomainError("wet_cell_count cannot exceed cell_count")
        rainfall_total_mm = require_non_negative(
            self.rainfall_total_mm, "rainfall_total_mm"
        )
        duration_hours = require_positive(self.duration_hours, "duration_hours")
        object.__setattr__(self, "max_depth_m", max_depth_m)
        object.__setattr__(self, "inundated_area_m2", inundated_area_m2)
        object.__setattr__(self, "wet_cell_count", wet_cell_count)
        object.__setattr__(self, "cell_count", cell_count)
        object.__setattr__(self, "rainfall_total_mm", rainfall_total_mm)
        object.__setattr__(self, "duration_hours", duration_hours)

    @property
    def inundated_fraction(self) -> float:
        return self.wet_cell_count / self.cell_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "dem_id": self.dem_id,
            "rainfall_id": self.rainfall_id,
            "max_depth_m": self.max_depth_m,
            "inundated_area_m2": self.inundated_area_m2,
            "wet_cell_count": self.wet_cell_count,
            "cell_count": self.cell_count,
            "rainfall_total_mm": self.rainfall_total_mm,
            "duration_hours": self.duration_hours,
        }

    @classmethod
    def from_dict(cls, data: object) -> ScenarioResult:
        payload = require_object(data, "scenario result")
        require_exact_keys(
            payload,
            required=(
                "scenario_id",
                "dem_id",
                "rainfall_id",
                "max_depth_m",
                "inundated_area_m2",
                "wet_cell_count",
                "cell_count",
                "rainfall_total_mm",
                "duration_hours",
            ),
            field="scenario result",
        )
        return cls(
            scenario_id=payload["scenario_id"],
            dem_id=payload["dem_id"],
            rainfall_id=payload["rainfall_id"],
            max_depth_m=payload["max_depth_m"],
            inundated_area_m2=payload["inundated_area_m2"],
            wet_cell_count=payload["wet_cell_count"],
            cell_count=payload["cell_count"],
            rainfall_total_mm=payload["rainfall_total_mm"],
            duration_hours=payload["duration_hours"],
        )

    @classmethod
    def from_inundation(
        cls,
        scenario: Scenario,
        inundation: InundationRaster,
    ) -> ScenarioResult:
        """Copy summary stats off a depth raster onto the scenario's ids.

        The raster must already be on the scenario DEM grid. Nothing here
        estimates depth from elevation or rainfall.
        """
        if not isinstance(scenario, Scenario):
            raise TypeError("scenario must be a Scenario")
        if not isinstance(inundation, InundationRaster):
            raise TypeError("inundation must be an InundationRaster")
        assert_same_grid(
            inundation.spec,
            scenario.dem.spec,
            "inundation grid spec does not match the scenario DEM",
        )
        return cls(
            scenario_id=scenario.scenario_id,
            dem_id=scenario.dem.id,
            rainfall_id=scenario.rainfall.id,
            max_depth_m=inundation.max_depth_m,
            inundated_area_m2=inundation.inundated_area_m2,
            wet_cell_count=inundation.wet_cell_count,
            cell_count=scenario.dem.spec.nrows * scenario.dem.spec.ncols,
            rainfall_total_mm=scenario.rainfall.total_depth_mm,
            duration_hours=scenario.rainfall.duration_hours,
        )
