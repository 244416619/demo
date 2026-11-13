"""Loaders for the bundled synthetic DEM, rainfall, and scenarios."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any

from floodcast.domain import (
    DigitalElevationModel,
    RainfallSeries,
    Scenario,
    ScenarioDocument,
)
from floodcast.domain.checks import require_slug
from floodcast.errors import DomainError, FixtureNotFound

DEFAULT_DEM_ID = "depression_bowl"
DEFAULT_RAINFALL_ID = "design_storm"
DEFAULT_SCENARIO_ID = "bowl_design_storm"

_CATALOG_KEYS = ("description", "dems", "rainfall", "scenarios")


@dataclass(frozen=True, slots=True)
class FixtureCatalog:
    """Sample ids shipped with the package, in catalog order."""

    dem_ids: tuple[str, ...]
    rainfall_ids: tuple[str, ...]
    scenario_ids: tuple[str, ...]


def _root() -> Traversable:
    return files("floodcast.fixtures").joinpath("data")


def _reject_unsafe_name(filename: str) -> None:
    if (
        not isinstance(filename, str)
        or not filename
        or filename != filename.strip()
        or "/" in filename
        or "\\" in filename
        or ".." in filename
    ):
        raise DomainError(f"unsafe fixture name: {filename!r}")


def _read_text(filename: str) -> str:
    _reject_unsafe_name(filename)
    path = _root().joinpath(filename)
    if not path.is_file():
        raise FixtureNotFound(f"bundled file {filename!r} is missing")
    return path.read_text(encoding="utf-8")


def _read_json(filename: str) -> dict[str, Any]:
    data = json.loads(_read_text(filename))
    if not isinstance(data, dict):
        raise DomainError(f"{filename} must contain a JSON object")
    return data


def _id_map(raw: dict[str, Any], key: str) -> dict[str, str]:
    section = raw.get(key)
    if not isinstance(section, dict) or not section:
        raise DomainError(f"catalog.{key} must be a non-empty object")
    mapping: dict[str, str] = {}
    for fixture_id, filename in section.items():
        require_slug(fixture_id, f"catalog.{key} id")
        if not isinstance(filename, str) or not filename.endswith(".json"):
            raise DomainError(f"catalog.{key}.{fixture_id} must name a .json file")
        _reject_unsafe_name(filename)
        mapping[fixture_id] = filename
    return mapping


def _catalog_maps() -> dict[str, dict[str, str]]:
    raw = _read_json("catalog.json")
    unknown = sorted(set(raw) - set(_CATALOG_KEYS))
    if unknown:
        raise DomainError("catalog.json has unknown keys: " + ", ".join(unknown))
    description = raw.get("description")
    if not isinstance(description, str) or not description.strip():
        raise DomainError("catalog.description must be a non-empty string")
    return {
        "dem": _id_map(raw, "dems"),
        "rainfall": _id_map(raw, "rainfall"),
        "scenario": _id_map(raw, "scenarios"),
    }


def load_catalog() -> FixtureCatalog:
    """Return bundled ids. Each listed file must be present in the package."""
    maps = _catalog_maps()
    for mapping in maps.values():
        for filename in mapping.values():
            _read_text(filename)
    return FixtureCatalog(
        dem_ids=tuple(maps["dem"]),
        rainfall_ids=tuple(maps["rainfall"]),
        scenario_ids=tuple(maps["scenario"]),
    )


def _filename(kind: str, fixture_id: str) -> str:
    mapping = _catalog_maps()[kind]
    try:
        return mapping[fixture_id]
    except KeyError:
        known = ", ".join(mapping)
        raise FixtureNotFound(
            f"unknown {kind} fixture {fixture_id!r}; known: {known}"
        ) from None


def _require_declared_id(kind: str, requested: str, actual: str) -> None:
    if actual != requested:
        raise DomainError(
            f"{kind} file for {requested!r} declares id {actual!r}"
        )


def load_dem(dem_id: str = DEFAULT_DEM_ID) -> DigitalElevationModel:
    dem = DigitalElevationModel.from_dict(_read_json(_filename("dem", dem_id)))
    _require_declared_id("dem", dem_id, dem.id)
    return dem


def load_rainfall(rainfall_id: str = DEFAULT_RAINFALL_ID) -> RainfallSeries:
    series = RainfallSeries.from_dict(_read_json(_filename("rainfall", rainfall_id)))
    _require_declared_id("rainfall", rainfall_id, series.id)
    return series


def load_scenario(scenario_id: str = DEFAULT_SCENARIO_ID) -> Scenario:
    """Join a scenario document to its DEM and rainfall series."""
    document = ScenarioDocument.from_dict(
        _read_json(_filename("scenario", scenario_id))
    )
    _require_declared_id("scenario", scenario_id, document.scenario_id)
    return Scenario(
        scenario_id=document.scenario_id,
        name=document.name,
        dem=load_dem(document.dem_id),
        rainfall=load_rainfall(document.rainfall_id),
        description=document.description,
    )


def read_fixture_notes() -> str:
    """Return the bundled explanation of the synthetic sample data."""
    return _read_text("README.md")
