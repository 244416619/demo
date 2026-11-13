"""演示级洪水淹没预测：领域模型、合成样例和洼地蓄水演算。

给定 DEM 和一场空间均匀的降雨，``predict`` 估计静水淹没水深。
这不是率定过的二维水动力模型。HTTP API 和地图界面属于后续单元。
"""

from importlib.metadata import PackageNotFoundError, version

from floodcast.domain import (
    DigitalElevationModel,
    GridSpec,
    InundationRaster,
    RainfallInterval,
    RainfallSeries,
    Scenario,
    ScenarioDocument,
    ScenarioResult,
    WetDryMask,
)
from floodcast.engine import (
    InundationParameters,
    InundationPrediction,
    predict,
    predict_scenario,
)
from floodcast.errors import DomainError, FixtureNotFound
from floodcast.fixtures import (
    DEFAULT_DEM_ID,
    DEFAULT_RAINFALL_ID,
    DEFAULT_SCENARIO_ID,
    FixtureCatalog,
    load_catalog,
    load_dem,
    load_rainfall,
    load_scenario,
    read_fixture_notes,
)

try:
    __version__ = version("floodcast")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "DEFAULT_DEM_ID",
    "DEFAULT_RAINFALL_ID",
    "DEFAULT_SCENARIO_ID",
    "DigitalElevationModel",
    "DomainError",
    "FixtureCatalog",
    "FixtureNotFound",
    "GridSpec",
    "InundationParameters",
    "InundationPrediction",
    "InundationRaster",
    "RainfallInterval",
    "RainfallSeries",
    "Scenario",
    "ScenarioDocument",
    "ScenarioResult",
    "WetDryMask",
    "load_catalog",
    "load_dem",
    "load_rainfall",
    "load_scenario",
    "predict",
    "predict_scenario",
    "read_fixture_notes",
]
