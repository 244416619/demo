"""Depression-filling inundation model.

This is a volume-conserving demo, not a 2D hydraulic solver. ``predict``
turns a ``Scenario`` into a depth raster and a ``ScenarioResult``.
"""

from floodcast.engine.predict import (
    InundationParameters,
    InundationPrediction,
    predict,
    predict_scenario,
)

__all__ = [
    "InundationParameters",
    "InundationPrediction",
    "predict",
    "predict_scenario",
]
