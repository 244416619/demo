"""Run the depression-fill model on a scenario."""

from __future__ import annotations

from dataclasses import dataclass

from floodcast.domain.checks import require_non_negative, require_positive
from floodcast.domain.inundation import InundationRaster, WetDryMask
from floodcast.domain.scenario import Scenario, ScenarioResult
from floodcast.engine.fill import fill_depressions
from floodcast.errors import DomainError
from floodcast.fixtures import DEFAULT_SCENARIO_ID, load_scenario


@dataclass(frozen=True, slots=True)
class InundationParameters:
    """Knobs for the demo inundation model.

    ``infiltration_mm`` is an initial loss subtracted from the rainfall
    total. It is not a time-varying infiltration rate. ``wet_threshold_m``
    is the depth at which a cell counts as wet, and the depth painted on
    an overflow path that would otherwise be dry.
    """

    infiltration_mm: float = 0.0
    wet_threshold_m: float = 0.01

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "infiltration_mm",
            require_non_negative(self.infiltration_mm, "infiltration_mm"),
        )
        object.__setattr__(
            self,
            "wet_threshold_m",
            require_positive(self.wet_threshold_m, "wet_threshold_m"),
        )


@dataclass(frozen=True, slots=True)
class InundationPrediction:
    """Depth grid and the summary for one finished scenario.

    ``retained_volume_m3`` is water held in depressions. ``overflow_volume_m3``
    is water that left the grid, including rain that fell on slopes already
    draining out of the domain. ``spilled`` is narrower: a depression reached
    its spill elevation and passed extra water downstream. ``overflow_path``
    is empty unless ``spilled`` is true. It runs from the pit to the outlet.
    """

    inundation: InundationRaster
    result: ScenarioResult
    parameters: InundationParameters
    retained_volume_m3: float
    overflow_volume_m3: float
    spilled: bool
    spill_elevation_m: float | None
    water_surface_m: float | None
    overflow_path: tuple[tuple[int, int], ...]

    def wet_mask(self) -> WetDryMask:
        return self.inundation.wet_mask()


def predict(
    scenario: Scenario,
    parameters: InundationParameters | None = None,
) -> InundationPrediction:
    """Estimate inundation for ``scenario``.

    The result is a static ponding map. It is not a rated hydrograph and
    not a 2D shallow-water solution.
    """
    if not isinstance(scenario, Scenario):
        raise TypeError("scenario must be a Scenario")
    if parameters is None:
        parameters = InundationParameters()
    elif not isinstance(parameters, InundationParameters):
        raise TypeError("parameters must be an InundationParameters")

    net_mm = scenario.rainfall.total_depth_mm - parameters.infiltration_mm
    if net_mm < 0:
        net_mm = 0.0
    filled = fill_depressions(
        scenario.dem.elevations_m,
        cell_area_m2=scenario.dem.spec.cell_area_m2,
        net_rain_m=net_mm / 1000.0,
        nodata=scenario.dem.nodata,
        wet_threshold_m=parameters.wet_threshold_m,
    )
    inundation = InundationRaster(
        spec=scenario.dem.spec,
        depth_m=filled.depth_m,
        wet_threshold_m=parameters.wet_threshold_m,
    )
    return InundationPrediction(
        inundation=inundation,
        result=ScenarioResult.from_inundation(scenario, inundation),
        parameters=parameters,
        retained_volume_m3=filled.retained_volume_m3,
        overflow_volume_m3=filled.overflow_volume_m3,
        spilled=filled.spilled,
        spill_elevation_m=filled.spill_elevation_m,
        water_surface_m=filled.water_surface_m,
        overflow_path=filled.overflow_path,
    )


def predict_scenario(
    scenario_id: str = DEFAULT_SCENARIO_ID,
    parameters: InundationParameters | None = None,
) -> InundationPrediction:
    """Load a bundled scenario and predict its inundation."""
    if not isinstance(scenario_id, str):
        raise DomainError("scenario_id must be a string")
    return predict(load_scenario(scenario_id), parameters)
