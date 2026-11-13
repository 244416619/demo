"""Shared checks for domain constructors and JSON documents."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from typing import Any

from floodcast.errors import DomainError

_SLUG = re.compile(r"[a-z][a-z0-9_]*\Z")


def require_object(data: object, field: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise DomainError(f"{field} must be a JSON object")
    return data


def require_exact_keys(
    data: dict[str, Any],
    *,
    required: tuple[str, ...],
    optional: tuple[str, ...] = (),
    field: str,
) -> None:
    missing = [key for key in required if key not in data]
    allowed = set(required) | set(optional)
    unknown = sorted(set(data) - allowed)
    if missing or unknown:
        parts: list[str] = []
        if missing:
            parts.append("missing " + ", ".join(missing))
        if unknown:
            parts.append("unknown " + ", ".join(unknown))
        raise DomainError(f"{field}: " + "; ".join(parts))


def require_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise DomainError(f"{field} must be a string")
    return value


def require_nonempty_str(value: object, field: str) -> str:
    text = require_text(value, field)
    if not text.strip():
        raise DomainError(f"{field} must be a non-empty string")
    return text


def require_slug(value: object, field: str) -> str:
    text = require_nonempty_str(value, field)
    if _SLUG.fullmatch(text) is None:
        raise DomainError(
            f"{field} must be a lowercase slug (letters, digits, underscore)"
        )
    return text


def require_finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DomainError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise DomainError(f"{field} must be a finite number")
    return number


def require_positive(value: object, field: str) -> float:
    number = require_finite(value, field)
    if number <= 0:
        raise DomainError(f"{field} must be > 0")
    return number


def require_non_negative(value: object, field: str) -> float:
    number = require_finite(value, field)
    if number < 0:
        raise DomainError(f"{field} must be >= 0")
    return number


def require_positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DomainError(f"{field} must be a positive integer")
    return value


def require_non_negative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DomainError(f"{field} must be a non-negative integer")
    return value


def require_float_grid(
    rows: object,
    *,
    nrows: int,
    ncols: int,
    field: str,
    coerce,
) -> tuple[tuple[float, ...], ...]:
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise DomainError(f"{field} must be a matrix of numbers")
    if len(rows) != nrows:
        raise DomainError(f"{field} has {len(rows)} rows, expected {nrows}")
    converted: list[tuple[float, ...]] = []
    for row_index, row in enumerate(rows):
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence):
            raise DomainError(f"{field} row {row_index} must be a list of numbers")
        if len(row) != ncols:
            raise DomainError(
                f"{field} row {row_index} has {len(row)} columns, expected {ncols}"
            )
        converted.append(
            tuple(
                coerce(value, f"{field}[{row_index}][{col_index}]")
                for col_index, value in enumerate(row)
            )
        )
    return tuple(converted)


def require_bool_grid(
    rows: object,
    *,
    nrows: int,
    ncols: int,
    field: str,
) -> tuple[tuple[bool, ...], ...]:
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise DomainError(f"{field} must be a boolean matrix")
    if len(rows) != nrows:
        raise DomainError(f"{field} has {len(rows)} rows, expected {nrows}")
    converted: list[tuple[bool, ...]] = []
    for row_index, row in enumerate(rows):
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence):
            raise DomainError(f"{field} row {row_index} must be a list of booleans")
        if len(row) != ncols:
            raise DomainError(
                f"{field} row {row_index} has {len(row)} columns, expected {ncols}"
            )
        values: list[bool] = []
        for col_index, value in enumerate(row):
            if not isinstance(value, bool):
                raise DomainError(
                    f"{field}[{row_index}][{col_index}] must be a boolean"
                )
            values.append(value)
        converted.append(tuple(values))
    return tuple(converted)
