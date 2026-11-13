"""Domain types for a demo flood-inundation model.

These modules describe inputs and outputs. They do not predict inundation.
"""

from floodcast.domain.dem import DigitalElevationModel
from floodcast.domain.grid import GridSpec
from floodcast.domain.inundation import InundationRaster, WetDryMask
from floodcast.domain.rainfall import RainfallInterval, RainfallSeries
from floodcast.domain.scenario import Scenario, ScenarioDocument, ScenarioResult

__all__ = [
    "DigitalElevationModel",
    "GridSpec",
    "InundationRaster",
    "RainfallInterval",
    "RainfallSeries",
    "Scenario",
    "ScenarioDocument",
    "ScenarioResult",
    "WetDryMask",
]
