"""Priority-flood depression storage.

Rainfall is turned into one volume of runoff and ponded in depressions.
The grid edge is an open boundary. Each cell drains 4-connected toward
that boundary. Depressions hold water up to the lowest elevation at which
they spill toward the edge; anything above that leaves the domain.

The hyetograph is collapsed to its total depth. This module does not route
a time-varying flood wave.
"""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass

from floodcast.errors import DomainError

# North, south, west, east. The order is only a tie break.
_NEIGHBORS = ((-1, 0), (1, 0), (0, -1), (0, 1))
_VOLUME_EPS = 1e-7


@dataclass(frozen=True, slots=True)
class DepressionFill:
    """Ponded depths plus the volumes that explain them.

    ``depth_m`` is zero on dry and nodata cells. When a depression spills,
    cells on the path from its pit to the outlet are raised to
    ``wet_threshold_m`` if they would otherwise be dry, so the exit shows
    up on a wet-dry mask. That trace is not extra stored water:
    ``retained_volume_m3`` counts only the water held in depressions.
    """

    depth_m: tuple[tuple[float, ...], ...]
    retained_volume_m3: float
    overflow_volume_m3: float
    spilled: bool
    spill_elevation_m: float | None
    water_surface_m: float | None
    overflow_path: tuple[tuple[int, int], ...]


def fill_depressions(
    elevations_m: tuple[tuple[float, ...], ...],
    *,
    cell_area_m2: float,
    net_rain_m: float,
    nodata: float | None,
    wet_threshold_m: float,
) -> DepressionFill:
    """Pond ``net_rain_m`` of uniform runoff on one elevation grid."""
    if cell_area_m2 <= 0:
        raise DomainError("cell_area_m2 must be > 0")
    if net_rain_m < 0:
        raise DomainError("net_rain_m must be >= 0")
    if wet_threshold_m <= 0:
        raise DomainError("wet_threshold_m must be > 0")

    nrows, ncols = _grid_shape(elevations_m)
    valid = [
        [
            nodata is None or elevations_m[row][col] != nodata
            for col in range(ncols)
        ]
        for row in range(nrows)
    ]
    if not any(cell for row in valid for cell in row):
        raise DomainError("DEM has no valid elevation cells")

    spill, parent = _priority_flood(elevations_m, valid)
    lakes, lake_at = _lakes(elevations_m, valid, spill, parent)
    depths, retained, overflow, spilled, lake_state = _route(
        elevations_m,
        valid,
        parent,
        lakes,
        lake_at,
        cell_area_m2=cell_area_m2,
        net_rain_m=net_rain_m,
    )
    surface_m, spill_m = _dominant_stage(depths, lake_at, lake_state)
    path = _overflow_paths(parent, lake_state)
    if path:
        _paint_overflow(depths, path, wet_threshold_m)
    return DepressionFill(
        depth_m=tuple(tuple(row) for row in depths),
        retained_volume_m3=retained,
        overflow_volume_m3=overflow,
        spilled=spilled,
        spill_elevation_m=spill_m,
        water_surface_m=surface_m,
        overflow_path=path,
    )


def _grid_shape(elevations: tuple[tuple[float, ...], ...]) -> tuple[int, int]:
    if not elevations or not elevations[0]:
        raise DomainError("elevations must be a non-empty grid")
    ncols = len(elevations[0])
    if any(len(row) != ncols for row in elevations):
        raise DomainError("elevations must be a rectangular grid")
    return len(elevations), ncols


def _priority_flood(
    elevations: tuple[tuple[float, ...], ...],
    valid: list[list[bool]],
) -> tuple[list[list[float | None]], list[list[tuple[int, int] | None]]]:
    """Spill elevation and a single downstream step for every valid cell.

    Boundary cells can drain off the map. At the same spill elevation an
    in-domain step wins the tie, so rain on a high rim that slopes inward
    flows into the bowl instead of leaving immediately. Cells walled off by
    nodata are left unvisited; the caller treats them as closed basins.
    """
    nrows = len(valid)
    ncols = len(valid[0])
    spill: list[list[float | None]] = [[None] * ncols for _ in range(nrows)]
    parent: list[list[tuple[int, int] | None]] = [
        [None] * ncols for _ in range(nrows)
    ]
    visited = [[False] * ncols for _ in range(nrows)]
    queue: list[tuple[float, int, int, int, int, int, int]] = []
    sequence = 0
    for row in range(nrows):
        for col in range(ncols):
            if not valid[row][col]:
                continue
            if row in (0, nrows - 1) or col in (0, ncols - 1):
                heapq.heappush(
                    queue,
                    (float(elevations[row][col]), 1, sequence, row, col, -1, -1),
                )
                sequence += 1

    while queue:
        level, _tie, _sequence, row, col, parent_row, parent_col = heapq.heappop(
            queue
        )
        if visited[row][col]:
            continue
        visited[row][col] = True
        spill[row][col] = max(float(elevations[row][col]), level)
        if parent_row >= 0:
            parent[row][col] = (parent_row, parent_col)
        for d_row, d_col in _NEIGHBORS:
            next_row = row + d_row
            next_col = col + d_col
            if not _inside(next_row, next_col, nrows, ncols):
                continue
            if not valid[next_row][next_col] or visited[next_row][next_col]:
                continue
            next_level = max(float(elevations[next_row][next_col]), spill[row][col])
            heapq.heappush(
                queue,
                (next_level, 0, sequence, next_row, next_col, row, col),
            )
            sequence += 1
    return spill, parent


@dataclass
class _Lake:
    cells: tuple[tuple[int, int], ...]
    spill_m: float | None
    pit: tuple[int, int]
    downstream: int | None = None
    inflow_m3: float = 0.0
    stored_m3: float = 0.0
    excess_m3: float = 0.0
    surface_m: float | None = None
    spilled: bool = False


def _lakes(
    elevations: tuple[tuple[float, ...], ...],
    valid: list[list[bool]],
    spill: list[list[float | None]],
    parent: list[list[tuple[int, int] | None]],
) -> tuple[list[_Lake], dict[tuple[int, int], int]]:
    nrows = len(valid)
    ncols = len(valid[0])
    seen = [[False] * ncols for _ in range(nrows)]
    lakes: list[_Lake] = []
    lake_at: dict[tuple[int, int], int] = {}

    def add(cells: list[tuple[int, int]], spill_m: float | None) -> None:
        index = len(lakes)
        for cell in cells:
            lake_at[cell] = index
        pit = min(cells, key=lambda cell: (elevations[cell[0]][cell[1]], cell))
        lakes.append(_Lake(cells=tuple(cells), spill_m=spill_m, pit=pit))

    for row in range(nrows):
        for col in range(ncols):
            if seen[row][col] or not valid[row][col]:
                continue
            cell_spill = spill[row][col]
            if cell_spill is None or not cell_spill > elevations[row][col]:
                continue
            seen[row][col] = True
            stack = [(row, col)]
            cells: list[tuple[int, int]] = []
            while stack:
                current_row, current_col = stack.pop()
                cells.append((current_row, current_col))
                for d_row, d_col in _NEIGHBORS:
                    next_row = current_row + d_row
                    next_col = current_col + d_col
                    if not _inside(next_row, next_col, nrows, ncols):
                        continue
                    if seen[next_row][next_col] or not valid[next_row][next_col]:
                        continue
                    neighbor_spill = spill[next_row][next_col]
                    if (
                        neighbor_spill == cell_spill
                        and neighbor_spill > elevations[next_row][next_col]
                    ):
                        seen[next_row][next_col] = True
                        stack.append((next_row, next_col))
            add(cells, cell_spill)

    for row in range(nrows):
        for col in range(ncols):
            if seen[row][col] or not valid[row][col] or spill[row][col] is not None:
                continue
            seen[row][col] = True
            stack = [(row, col)]
            cells = []
            while stack:
                current_row, current_col = stack.pop()
                cells.append((current_row, current_col))
                for d_row, d_col in _NEIGHBORS:
                    next_row = current_row + d_row
                    next_col = current_col + d_col
                    if not _inside(next_row, next_col, nrows, ncols):
                        continue
                    if seen[next_row][next_col] or not valid[next_row][next_col]:
                        continue
                    if spill[next_row][next_col] is None:
                        seen[next_row][next_col] = True
                        stack.append((next_row, next_col))
            add(cells, None)

    for index, lake in enumerate(lakes):
        lake.downstream = _first_lake(lake.pit, parent, lake_at, origin=index)
    return lakes, lake_at


def _route(
    elevations: tuple[tuple[float, ...], ...],
    valid: list[list[bool]],
    parent: list[list[tuple[int, int] | None]],
    lakes: list[_Lake],
    lake_at: dict[tuple[int, int], int],
    *,
    cell_area_m2: float,
    net_rain_m: float,
) -> tuple[list[list[float]], float, float, bool, list[_Lake]]:
    cell_volume = net_rain_m * cell_area_m2
    overflow = 0.0
    nrows = len(valid)
    ncols = len(valid[0])
    for row in range(nrows):
        for col in range(ncols):
            if not valid[row][col]:
                continue
            target = _first_lake((row, col), parent, lake_at, origin=None)
            if target is None:
                overflow += cell_volume
            else:
                lakes[target].inflow_m3 += cell_volume

    order = _upstream_first(lakes)
    for index in order:
        lake = lakes[index]
        capacity = _capacity(elevations, lake, cell_area_m2)
        if capacity is None or lake.inflow_m3 <= capacity + _VOLUME_EPS:
            lake.stored_m3 = (
                lake.inflow_m3
                if capacity is None
                else min(lake.inflow_m3, capacity)
            )
            lake.excess_m3 = 0.0
            lake.spilled = False
        else:
            lake.stored_m3 = capacity
            lake.excess_m3 = lake.inflow_m3 - capacity
            lake.spilled = True
        if lake.excess_m3 <= _VOLUME_EPS:
            lake.excess_m3 = 0.0
            lake.spilled = False
        if lake.downstream is None:
            overflow += lake.excess_m3
        else:
            lakes[lake.downstream].inflow_m3 += lake.excess_m3
        lake.surface_m = _surface(elevations, lake, cell_area_m2)

    depths = [[0.0] * ncols for _ in range(nrows)]
    for lake in lakes:
        if lake.surface_m is None or lake.stored_m3 <= _VOLUME_EPS:
            continue
        for row, col in lake.cells:
            top = lake.surface_m if lake.spill_m is None else min(
                lake.surface_m, lake.spill_m
            )
            depths[row][col] = max(0.0, top - float(elevations[row][col]))
    retained = sum(lake.stored_m3 for lake in lakes)
    spilled = any(lake.spilled for lake in lakes)
    return depths, retained, overflow, spilled, lakes


def _capacity(
    elevations: tuple[tuple[float, ...], ...],
    lake: _Lake,
    cell_area_m2: float,
) -> float | None:
    if lake.spill_m is None:
        return None
    return sum(
        (lake.spill_m - float(elevations[row][col])) * cell_area_m2
        for row, col in lake.cells
    )


def _surface(
    elevations: tuple[tuple[float, ...], ...],
    lake: _Lake,
    cell_area_m2: float,
) -> float | None:
    if lake.stored_m3 <= _VOLUME_EPS:
        return None
    if lake.spill_m is not None:
        capacity = _capacity(elevations, lake, cell_area_m2)
        assert capacity is not None
        if lake.stored_m3 >= capacity - _VOLUME_EPS:
            return lake.spill_m
        low = min(float(elevations[row][col]) for row, col in lake.cells)
        high = lake.spill_m
    else:
        low = min(float(elevations[row][col]) for row, col in lake.cells)
        high = max(float(elevations[row][col]) for row, col in lake.cells)
        at_high = _volume_at(elevations, lake.cells, high, None, cell_area_m2)
        if lake.stored_m3 >= at_high:
            count = len(lake.cells)
            return high + (lake.stored_m3 - at_high) / (count * cell_area_m2)
    for _ in range(64):
        mid = (low + high) / 2.0
        if _volume_at(elevations, lake.cells, mid, lake.spill_m, cell_area_m2) < (
            lake.stored_m3
        ):
            low = mid
        else:
            high = mid
    return high


def _volume_at(
    elevations: tuple[tuple[float, ...], ...],
    cells: tuple[tuple[int, int], ...],
    surface: float,
    spill_m: float | None,
    cell_area_m2: float,
) -> float:
    total = 0.0
    for row, col in cells:
        top = surface if spill_m is None else min(surface, spill_m)
        depth = top - float(elevations[row][col])
        if depth > 0:
            total += depth * cell_area_m2
    return total


def _dominant_stage(
    depths: list[list[float]],
    lake_at: dict[tuple[int, int], int],
    lakes: list[_Lake],
) -> tuple[float | None, float | None]:
    """Stage of the lake that holds the deepest water."""
    chosen: int | None = None
    best: tuple[float, int, int] | None = None
    for (row, col), index in lake_at.items():
        depth = depths[row][col]
        if depth <= 0:
            continue
        rank = (depth, -row, -col)
        if best is None or rank > best:
            best = rank
            chosen = index
    if chosen is None:
        return None, None
    lake = lakes[chosen]
    return lake.surface_m, lake.spill_m


def _overflow_paths(
    parent: list[list[tuple[int, int] | None]],
    lakes: list[_Lake],
) -> tuple[tuple[int, int], ...]:
    merged: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for lake in lakes:
        if not lake.spilled:
            continue
        for cell in _path_to_outlet(lake.pit, parent):
            if cell not in seen:
                seen.add(cell)
                merged.append(cell)
    return tuple(merged)


def _paint_overflow(
    depths: list[list[float]],
    path: tuple[tuple[int, int], ...],
    wet_threshold_m: float,
) -> None:
    for row, col in path:
        if depths[row][col] < wet_threshold_m:
            depths[row][col] = wet_threshold_m


def _upstream_first(lakes: list[_Lake]) -> list[int]:
    indegree = [0] * len(lakes)
    for lake in lakes:
        if lake.downstream is not None:
            indegree[lake.downstream] += 1
    pending = deque(index for index, degree in enumerate(indegree) if degree == 0)
    order: list[int] = []
    while pending:
        index = pending.popleft()
        order.append(index)
        downstream = lakes[index].downstream
        if downstream is None:
            continue
        indegree[downstream] -= 1
        if indegree[downstream] == 0:
            pending.append(downstream)
    if len(order) != len(lakes):
        raise RuntimeError("depression drainage contains a cycle")
    return order


def _first_lake(
    start: tuple[int, int],
    parent: list[list[tuple[int, int] | None]],
    lake_at: dict[tuple[int, int], int],
    *,
    origin: int | None,
) -> int | None:
    cell: tuple[int, int] | None = start
    seen: set[tuple[int, int]] = set()
    while cell is not None:
        if cell in seen:
            raise RuntimeError("drainage directions contain a cycle")
        seen.add(cell)
        lake_index = lake_at.get(cell)
        if lake_index is not None and lake_index != origin:
            return lake_index
        cell = parent[cell[0]][cell[1]]
    return None


def _path_to_outlet(
    start: tuple[int, int],
    parent: list[list[tuple[int, int] | None]],
) -> tuple[tuple[int, int], ...]:
    path: list[tuple[int, int]] = []
    cell: tuple[int, int] | None = start
    seen: set[tuple[int, int]] = set()
    while cell is not None:
        if cell in seen:
            raise RuntimeError("drainage directions contain a cycle")
        seen.add(cell)
        path.append(cell)
        cell = parent[cell[0]][cell[1]]
    return tuple(path)


def _inside(row: int, col: int, nrows: int, ncols: int) -> bool:
    return 0 <= row < nrows and 0 <= col < ncols
