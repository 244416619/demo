"""Bundled synthetic DEM, rainfall, and scenario fixtures."""

import pytest

from floodcast import (
    DEFAULT_DEM_ID,
    DEFAULT_RAINFALL_ID,
    DEFAULT_SCENARIO_ID,
    FixtureNotFound,
    load_catalog,
    load_dem,
    load_rainfall,
    load_scenario,
    read_fixture_notes,
)


def _border_and_interior(elevations):
    nrows = len(elevations)
    ncols = len(elevations[0])
    border: list[tuple[int, int, float]] = []
    interior: list[tuple[int, int, float]] = []
    for row in range(nrows):
        for col in range(ncols):
            value = elevations[row][col]
            target = (
                border
                if row in (0, nrows - 1) or col in (0, ncols - 1)
                else interior
            )
            target.append((row, col, value))
    return border, interior


def test_catalog_lists_the_sample_ids():
    catalog = load_catalog()
    assert catalog.dem_ids == (DEFAULT_DEM_ID,)
    assert catalog.rainfall_ids == ("design_storm", "light_rain")
    assert catalog.scenario_ids == ("bowl_design_storm", "bowl_light_rain")
    assert DEFAULT_RAINFALL_ID == "design_storm"
    assert DEFAULT_SCENARIO_ID == "bowl_design_storm"


def test_every_catalog_entry_loads_and_ids_match():
    catalog = load_catalog()
    for dem_id in catalog.dem_ids:
        assert load_dem(dem_id).id == dem_id
    for rainfall_id in catalog.rainfall_ids:
        assert load_rainfall(rainfall_id).id == rainfall_id
    for scenario_id in catalog.scenario_ids:
        scenario = load_scenario(scenario_id)
        assert scenario.scenario_id == scenario_id
        assert scenario.dem.id
        assert scenario.rainfall.id


def test_depression_bowl_is_an_interior_sink_with_a_southeast_outlet():
    dem = load_dem()
    assert dem.spec.nrows == dem.spec.ncols == 8
    assert dem.spec.cell_size_m == 25.0
    assert dem.spec.origin_x_m == 0.0
    assert dem.spec.origin_y_m == 200.0
    assert dem.spec.crs == "LOCAL"
    assert dem.nodata is None
    assert dem.elevation_at(0, 0) == 22.0
    assert dem.elevation_at(3, 3) == 4.0
    assert dem.elevation_at(7, 7) == 14.0

    border, interior = _border_and_interior(dem.elevations_m)
    lowest_interior = min(interior, key=lambda item: item[2])
    lowest_border = min(border, key=lambda item: item[2])
    assert lowest_interior[:2] == (3, 3)
    assert lowest_interior[2] < lowest_border[2]
    assert lowest_border[:2] == (7, 7)
    assert dem.to_dict()["spec"]["ncols"] == 8
    assert load_dem().to_dict()["id"] == "depression_bowl"


def test_rainfall_scenarios_match_the_fixture_notes():
    storm = load_rainfall("design_storm")
    light = load_rainfall("light_rain")
    assert storm.distribution == light.distribution == "uniform"
    assert storm.duration_hours == 3.0
    assert storm.total_depth_mm == 50.0
    peak = max(storm.intervals, key=lambda interval: interval.depth_mm)
    assert (peak.start_hours, peak.end_hours, peak.depth_mm) == (1.0, 1.5, 22.0)
    assert light.duration_hours == 2.0
    assert light.total_depth_mm == 2.0

    design = load_scenario("bowl_design_storm")
    mild = load_scenario("bowl_light_rain")
    assert design.dem.id == mild.dem.id == "depression_bowl"
    assert design.rainfall.id == "design_storm"
    assert mild.rainfall.id == "light_rain"
    assert design.to_dict()["rainfall_id"] == "design_storm"


def test_fixture_notes_describe_the_synthetic_data():
    notes = read_fixture_notes()
    for expected in ("合成", "depression_bowl", "design_storm", "light_rain", "4 m"):
        assert expected in notes


def test_unknown_fixture_id_is_reported():
    with pytest.raises(FixtureNotFound, match="unknown dem"):
        load_dem("not_a_dem")
    with pytest.raises(FixtureNotFound, match="unknown rainfall"):
        load_rainfall("not_a_storm")
