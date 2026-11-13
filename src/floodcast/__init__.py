"""演示级洪水淹没预测的领域模型与合成样例。

本包描述 DEM、降雨过程、淹没水深栅格和场景结果元数据。
它不根据降雨计算水深。演算引擎、HTTP API 和地图界面属于后续单元。
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
    "read_fixture_notes",
]
