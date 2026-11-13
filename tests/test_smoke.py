"""Import and packaging smoke tests."""

from importlib.metadata import version
from pathlib import Path

import floodcast
from floodcast import (
    DigitalElevationModel,
    InundationRaster,
    RainfallSeries,
    Scenario,
    ScenarioResult,
    WetDryMask,
    load_scenario,
)


def test_package_imports_and_version_matches_metadata():
    assert floodcast.__version__ == version("floodcast") == "0.1.0"
    assert DigitalElevationModel.__name__ == "DigitalElevationModel"
    assert RainfallSeries.__name__ == "RainfallSeries"
    assert InundationRaster.__name__ == "InundationRaster"
    assert WetDryMask.__name__ == "WetDryMask"
    assert Scenario.__name__ == "Scenario"
    assert ScenarioResult.__name__ == "ScenarioResult"


def test_default_scenario_imports_through_package_root():
    scenario = load_scenario()
    assert scenario.scenario_id == "bowl_design_storm"
    assert isinstance(scenario.dem, DigitalElevationModel)
    assert isinstance(scenario.rainfall, RainfallSeries)


def test_readme_describes_later_units():
    readme = Path(__file__).resolve().parents[1] / "README.md"
    text = readme.read_text(encoding="utf-8")
    for expected in (
        "演示",
        "不是经过率定",
        "pytest",
        "FastAPI",
        "Vite",
        "Leaflet",
        "floodcast/engine",
        "predict_scenario",
        "LOCAL",
        "bowl_design_storm",
    ):
        assert expected in text
