"""Spatially uniform rainfall time series (a hyetograph)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from floodcast.domain.checks import (
    require_exact_keys,
    require_non_negative,
    require_object,
    require_slug,
    require_text,
)
from floodcast.errors import DomainError

_UNIFORM = "uniform"


@dataclass(frozen=True, slots=True)
class RainfallInterval:
    """Rainfall depth over a half-open time window ``[start_hours, end_hours)``.

    Depth is millimeters of water, uniform over the whole domain. Time is
    hours from the start of the scenario.
    """

    start_hours: float
    end_hours: float
    depth_mm: float

    def __post_init__(self) -> None:
        start = require_non_negative(self.start_hours, "start_hours")
        end = require_non_negative(self.end_hours, "end_hours")
        depth = require_non_negative(self.depth_mm, "depth_mm")
        if end <= start:
            raise DomainError("rainfall interval end_hours must be > start_hours")
        object.__setattr__(self, "start_hours", start)
        object.__setattr__(self, "end_hours", end)
        object.__setattr__(self, "depth_mm", depth)

    @property
    def duration_hours(self) -> float:
        return self.end_hours - self.start_hours

    @property
    def intensity_mm_per_hour(self) -> float:
        return self.depth_mm / self.duration_hours

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_hours": self.start_hours,
            "end_hours": self.end_hours,
            "depth_mm": self.depth_mm,
        }

    @classmethod
    def from_dict(cls, data: object) -> RainfallInterval:
        payload = require_object(data, "rainfall interval")
        require_exact_keys(
            payload,
            required=("start_hours", "end_hours", "depth_mm"),
            field="rainfall interval",
        )
        return cls(
            start_hours=payload["start_hours"],
            end_hours=payload["end_hours"],
            depth_mm=payload["depth_mm"],
        )


@dataclass(frozen=True, slots=True)
class RainfallSeries:
    """Ordered hyetograph for one scenario.

    Intervals must be sorted and must not overlap. Gaps are dry spells and
    are allowed. ``distribution`` is ``uniform`` in this unit: one series
    applies to every DEM cell. A later unit can add spatial rainfall by
    extending this field; other values are rejected here so they are not
    silently ignored.
    """

    id: str
    intervals: tuple[RainfallInterval, ...]
    description: str = ""
    distribution: str = _UNIFORM

    def __post_init__(self) -> None:
        slug = require_slug(self.id, "rainfall id")
        description = require_text(self.description, "description")
        distribution = require_text(self.distribution, "distribution")
        if distribution != _UNIFORM:
            raise DomainError(
                "only spatially uniform rainfall is accepted in this unit "
                "(distribution='uniform')"
            )
        if isinstance(self.intervals, (str, bytes)) or not isinstance(
            self.intervals, Sequence
        ):
            raise DomainError("intervals must be a non-empty sequence")
        intervals = tuple(self.intervals)
        if not intervals:
            raise DomainError("rainfall series needs at least one interval")
        previous_end: float | None = None
        stored: list[RainfallInterval] = []
        for index, interval in enumerate(intervals):
            if not isinstance(interval, RainfallInterval):
                raise DomainError(
                    f"intervals[{index}] must be a RainfallInterval"
                )
            if previous_end is not None and interval.start_hours < previous_end:
                raise DomainError(
                    "rainfall intervals overlap or are out of order"
                )
            stored.append(interval)
            previous_end = interval.end_hours
        object.__setattr__(self, "id", slug)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "distribution", distribution)
        object.__setattr__(self, "intervals", tuple(stored))

    @property
    def total_depth_mm(self) -> float:
        return sum(interval.depth_mm for interval in self.intervals)

    @property
    def duration_hours(self) -> float:
        """Hours from the first interval start to the last interval end.

        Dry gaps inside the series are included. Time before the first
        interval is not.
        """
        return self.intervals[-1].end_hours - self.intervals[0].start_hours

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "distribution": self.distribution,
            "intervals": [interval.to_dict() for interval in self.intervals],
        }

    @classmethod
    def from_dict(cls, data: object) -> RainfallSeries:
        payload = require_object(data, "rainfall")
        require_exact_keys(
            payload,
            required=("id", "description", "intervals"),
            optional=("distribution",),
            field="rainfall",
        )
        raw_intervals = payload["intervals"]
        if not isinstance(raw_intervals, list) or not raw_intervals:
            raise DomainError("intervals must be a non-empty list")
        kwargs: dict[str, Any] = {
            "id": payload["id"],
            "description": payload["description"],
            "intervals": tuple(
                RainfallInterval.from_dict(item) for item in raw_intervals
            ),
        }
        if "distribution" in payload:
            kwargs["distribution"] = payload["distribution"]
        return cls(**kwargs)
