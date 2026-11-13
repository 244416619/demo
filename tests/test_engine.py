"""Depression-fill predictions on the bundled bowl and on small hand-made DEMs."""

import pytest

from floodcast import (
    DigitalElevationModel,
    DomainError,
    FixtureNotFound,
    GridSpec,
    InundationParameters,
    RainfallInterval,
    RainfallSeries,
    Scenario,
    ScenarioResult,
    load_dem,
    load_rainfall,
    load_scenario,
    predict,
    predict_scenario,
)


def _scenario(
    elevations,
    depth_mm,
    *,
    nodata=None,
    cell_size=25.0,
    hours=1.0,
    scenario_id="case",
    rain_id="rain",
    dem_id="dem",
):
    nrows = len(elevations)
    ncols = len(elevations[0])
    dem = DigitalElevationModel(
        id=dem_id,
        spec=GridSpec(ncols=ncols, nrows=nrows, cell_size_m=cell_size),
        elevations_m=elevations,
        description="hand-made dem",
        nodata=nodata,
    )
    rainfall = RainfallSeries(
        id=rain_id,
        intervals=(RainfallInterval(0.0, hours, depth_mm),),
        description="hand-made rain",
    )
    return Scenario(
        scenario_id=scenario_id,
        name="hand-made",
        dem=dem,
        rainfall=rainfall,
        description="hand-made scenario",
    )


def _bowl_with_rain(depth_mm, *, scenario_id="custom_bowl", rain_id="custom_rain"):
    return _scenario(
        load_dem().elevations_m,
        depth_mm,
        cell_size=25.0,
        scenario_id=scenario_id,
        rain_id=rain_id,
        dem_id="depression_bowl",
    )


def _wet_cells(prediction):
    mask = prediction.wet_mask().wet
    return {
        (row, col)
        for row, cells in enumerate(mask)
        for col, wet in enumerate(cells)
        if wet
    }


def _border_and_interior(elevations):
    nrows = len(elevations)
    ncols = len(elevations[0])
    border = []
    interior = []
    for row in range(nrows):
        for col in range(ncols):
            item = (elevations[row][col], row, col)
            if row in (0, nrows - 1) or col in (0, ncols - 1):
                border.append(item)
            else:
                interior.append(item)
    return border, interior


def test_default_scenario_floods_the_bowl_and_leaves_high_ground_dry():
    scenario = load_scenario()
    prediction = predict(scenario)
    dem = scenario.dem

    assert prediction.result.scenario_id == "bowl_design_storm"
    assert prediction.result == ScenarioResult.from_inundation(
        scenario, prediction.inundation
    )
    assert prediction.inundation.spec == dem.spec
    assert prediction.result.cell_count == 64
    assert prediction.result.rainfall_total_mm == 50.0
    assert prediction.result.duration_hours == 3.0
    assert prediction.spilled is False
    assert prediction.overflow_path == ()
    assert prediction.spill_elevation_m == pytest.approx(16.0)
    assert prediction.water_surface_m == pytest.approx(5.6)
    assert prediction.inundation.max_depth_m == pytest.approx(1.6)
    assert prediction.inundation.depth_at(3, 3) == pytest.approx(1.6)
    assert prediction.inundation.depth_at(3, 4) == pytest.approx(0.6)
    assert prediction.inundation.depth_at(4, 3) == pytest.approx(0.6)
    assert prediction.result.wet_cell_count == 3
    assert prediction.result.inundated_area_m2 == 1875.0

    ranked = sorted(
        (dem.elevation_at(row, col), row, col)
        for row in range(dem.spec.nrows)
        for col in range(dem.spec.ncols)
    )
    lowest_three = {(row, col) for _elev, row, col in ranked[:3]}
    assert _wet_cells(prediction) == lowest_three == {(3, 3), (3, 4), (4, 3)}

    for row in range(dem.spec.nrows):
        for col in range(dem.spec.ncols):
            if dem.elevation_at(row, col) >= 8:
                assert prediction.inundation.depth_at(row, col) == 0.0

    border, interior = _border_and_interior(dem.elevations_m)
    _elev, pit_row, pit_col = min(interior)
    _elev, outlet_row, outlet_col = min(border)
    assert (pit_row, pit_col) == (3, 3)
    assert prediction.inundation.depth_at(pit_row, pit_col) == prediction.inundation.max_depth_m
    assert (outlet_row, outlet_col) == (7, 7)
    assert prediction.inundation.depth_at(outlet_row, outlet_col) == 0.0

    ponded = sum(
        prediction.inundation.depth_at(row, col)
        for row in range(8)
        for col in range(8)
    )
    assert ponded * dem.spec.cell_area_m2 == pytest.approx(prediction.retained_volume_m3)
    assert prediction.retained_volume_m3 == pytest.approx(1750.0)
    assert prediction.overflow_volume_m3 == pytest.approx(250.0)
    assert (
        prediction.retained_volume_m3 + prediction.overflow_volume_m3
        == pytest.approx(50.0 / 1000.0 * 64 * dem.spec.cell_area_m2)
    )


def test_design_storm_inundates_more_than_light_rain():
    design = predict_scenario("bowl_design_storm")
    light = predict_scenario("bowl_light_rain")

    assert design.result.max_depth_m > light.result.max_depth_m
    assert design.result.inundated_area_m2 > light.result.inundated_area_m2
    assert design.result.wet_cell_count > light.result.wet_cell_count
    assert design.retained_volume_m3 > light.retained_volume_m3
    assert _wet_cells(light) == {(3, 3)}
    assert light.inundation.depth_at(3, 3) == pytest.approx(0.112)
    assert light.inundation.depth_at(0, 0) == 0.0
    assert light.inundation.depth_at(7, 7) == 0.0
    assert light.spilled is False
    assert light.result.rainfall_total_mm == 2.0
    assert light.result.inundated_area_m2 == 625.0


def test_same_rainfall_total_gives_the_same_depth_grid():
    dem = load_dem()
    peaked = Scenario(
        scenario_id="peaked",
        name="peaked",
        dem=dem,
        rainfall=RainfallSeries(
            id="one_burst",
            intervals=(RainfallInterval(0.0, 1.0, 50.0),),
            description="same total, one interval",
        ),
        description="same total",
    )
    bundled = predict(load_scenario("bowl_design_storm"))
    assert predict(peaked).inundation.depth_m == bundled.inundation.depth_m
    assert load_rainfall("design_storm").total_depth_mm == 50.0


def test_overflow_follows_the_southeast_outlet():
    full = predict(_bowl_with_rain(3000.0, scenario_id="full", rain_id="full_rain"))
    fuller = predict(_bowl_with_rain(4000.0, scenario_id="fuller", rain_id="fuller_rain"))

    assert full.spilled is True
    assert fuller.spilled is True
    assert full.inundation.depth_at(3, 3) == pytest.approx(12.0)
    assert full.inundation.depth_at(3, 3) == pytest.approx(fuller.inundation.depth_at(3, 3))
    assert full.retained_volume_m3 == pytest.approx(fuller.retained_volume_m3)
    assert fuller.overflow_volume_m3 > full.overflow_volume_m3
    assert full.spill_elevation_m == pytest.approx(16.0)
    assert full.water_surface_m == pytest.approx(16.0)

    assert full.overflow_path[0] == (3, 3)
    assert full.overflow_path[-1] == (7, 7)
    assert full.overflow_path == (
        (3, 3),
        (3, 4),
        (3, 5),
        (3, 6),
        (4, 6),
        (5, 6),
        (6, 6),
        (6, 7),
        (7, 7),
    )
    for (row, col), (next_row, next_col) in zip(
        full.overflow_path, full.overflow_path[1:]
    ):
        assert abs(row - next_row) + abs(col - next_col) == 1
    assert full.inundation.depth_at(7, 7) == pytest.approx(0.01)
    assert full.wet_mask().wet[7][7] is True
    assert full.inundation.depth_at(0, 0) == 0.0
    assert (0, 0) not in full.overflow_path
    assert full.inundation.max_depth_m == pytest.approx(12.0)


def test_infiltration_reduces_depth_and_can_stop_runoff():
    dry = predict_scenario(parameters=InundationParameters(infiltration_mm=50))
    assert dry.inundation.max_depth_m == 0.0
    assert dry.retained_volume_m3 == 0.0
    assert dry.overflow_volume_m3 == 0.0
    assert dry.result.rainfall_total_mm == 50.0
    assert dry.result.wet_cell_count == 0

    matched = predict_scenario(parameters=InundationParameters(infiltration_mm=48))
    light = predict_scenario("bowl_light_rain")
    assert matched.inundation.depth_m == light.inundation.depth_m

    with pytest.raises(DomainError):
        InundationParameters(infiltration_mm=-1)
    with pytest.raises(DomainError):
        InundationParameters(wet_threshold_m=0)


def test_flat_ground_exports_rain_without_ponding():
    prediction = predict(_scenario(((4.0, 4.0), (4.0, 4.0)), 30.0, cell_size=10.0))
    assert prediction.inundation.max_depth_m == 0.0
    assert prediction.retained_volume_m3 == 0.0
    assert prediction.overflow_volume_m3 == pytest.approx(0.03 * 4 * 100.0)
    assert prediction.spilled is False
    assert prediction.overflow_path == ()
    assert prediction.water_surface_m is None


def test_upstream_depression_keeps_its_own_rain():
    elevations = (
        (8, 8, 8, 8, 8),
        (8, 3, 6, 1, 4),
        (8, 8, 8, 8, 8),
    )
    prediction = predict(_scenario(elevations, 20.0, cell_size=10.0))
    assert prediction.inundation.depth_at(1, 1) > 0.0
    assert prediction.inundation.depth_at(1, 3) > 0.0
    assert prediction.inundation.depth_at(1, 2) == 0.0
    assert prediction.spilled is False


def test_separate_outlets_stop_rising_once_they_spill():
    elevations = (
        (9, 9, 9, 9, 9, 9, 9),
        (9, 4, 7, 9, 7, 4, 9),
        (6, 1, 4, 9, 4, 2, 5),
        (9, 4, 7, 9, 7, 4, 9),
        (9, 9, 9, 9, 9, 9, 9),
    )
    partial = predict(
        _scenario(
            elevations, 500.0, cell_size=10.0, scenario_id="split_partial", rain_id="split_partial"
        )
    )
    full = predict(
        _scenario(elevations, 2000.0, cell_size=10.0, scenario_id="split_full", rain_id="split_full")
    )
    fuller = predict(
        _scenario(
            elevations, 5000.0, cell_size=10.0, scenario_id="split_fuller", rain_id="split_fuller"
        )
    )

    # The east pit has already reached its own sill while the west pit is still filling.
    assert partial.spilled is True
    assert partial.inundation.depth_at(2, 5) == pytest.approx(3.0)
    assert partial.inundation.depth_at(2, 1) == pytest.approx(3.5)
    assert partial.overflow_path == ((2, 5), (2, 6))
    assert partial.inundation.depth_at(2, 3) == 0.0

    assert full.spilled is True
    assert fuller.spilled is True
    assert full.inundation.depth_at(2, 1) == pytest.approx(5.0)
    assert full.inundation.depth_at(2, 5) == pytest.approx(3.0)
    assert full.inundation.depth_at(2, 1) == pytest.approx(fuller.inundation.depth_at(2, 1))
    assert full.inundation.depth_at(2, 5) == pytest.approx(fuller.inundation.depth_at(2, 5))
    assert full.inundation.depth_at(2, 1) > partial.inundation.depth_at(2, 1)
    assert full.inundation.depth_at(2, 3) == 0.0
    assert (2, 0) in full.overflow_path
    assert (2, 6) in full.overflow_path
    assert full.retained_volume_m3 == pytest.approx(fuller.retained_volume_m3)
    assert fuller.overflow_volume_m3 > full.overflow_volume_m3 > partial.overflow_volume_m3


def test_nodata_cells_stay_dry_and_an_empty_dem_is_rejected():
    prediction = predict(
        _scenario(
            ((5, 5, 5), (5, 0, 5), (5, -9999, 5)),
            200.0,
            nodata=-9999.0,
            cell_size=1.0,
        )
    )
    assert prediction.inundation.depth_at(2, 1) == 0.0
    assert prediction.wet_mask().wet[2][1] is False
    assert prediction.inundation.depth_at(1, 1) > 0.0
    assert (2, 1) not in _wet_cells(prediction)

    empty = _scenario(((-1, -1), (-1, -1)), 10.0, nodata=-1.0, cell_size=1.0)
    with pytest.raises(DomainError, match="no valid"):
        predict(empty)


def test_nodata_walled_pit_holds_water_with_no_outlet():
    prediction = predict(
        _scenario(
            ((-1, -1, -1), (-1, 0, -1), (-1, -1, -1)),
            500.0,
            nodata=-1.0,
            cell_size=1.0,
            scenario_id="closed_pit",
            rain_id="closed_rain",
        )
    )
    assert prediction.inundation.depth_at(1, 1) == pytest.approx(0.5)
    assert prediction.retained_volume_m3 == pytest.approx(0.5)
    assert prediction.overflow_volume_m3 == 0.0
    assert prediction.spilled is False
    assert prediction.spill_elevation_m is None
    assert prediction.water_surface_m == pytest.approx(0.5)
    assert _wet_cells(prediction) == {(1, 1)}


def test_predict_rejects_the_wrong_types_and_unknown_scenarios():
    with pytest.raises(TypeError):
        predict(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        predict(load_scenario(), parameters=object())  # type: ignore[arg-type]
    with pytest.raises(FixtureNotFound):
        predict_scenario("not_a_scenario")
