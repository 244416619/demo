"""Domain shapes: validation and summaries over data the caller already has."""

import pytest

from floodcast import (
    DigitalElevationModel,
    DomainError,
    GridSpec,
    InundationRaster,
    RainfallInterval,
    RainfallSeries,
    Scenario,
    ScenarioDocument,
    ScenarioResult,
    WetDryMask,
)


def _spec(**overrides) -> GridSpec:
    values = {"ncols": 2, "nrows": 2, "cell_size_m": 10.0}
    values.update(overrides)
    return GridSpec(**values)


def _scenario() -> Scenario:
    spec = _spec()
    dem = DigitalElevationModel(
        id="tiny",
        spec=spec,
        elevations_m=((5.0, 5.0), (5.0, 1.0)),
        description="test bowl",
    )
    rainfall = RainfallSeries(
        id="tiny_rain",
        intervals=(RainfallInterval(0.0, 1.0, 10.0),),
        description="test rain",
    )
    return Scenario(
        scenario_id="tiny_case",
        name="tiny",
        dem=dem,
        rainfall=rainfall,
        description="joined by hand",
    )


def test_grid_cell_center_uses_north_up_origin():
    spec = GridSpec(
        ncols=8,
        nrows=8,
        cell_size_m=25.0,
        origin_x_m=0.0,
        origin_y_m=200.0,
        crs="LOCAL",
    )
    assert spec.cell_center(0, 0) == (12.5, 187.5)
    assert spec.cell_center(7, 7) == (187.5, 12.5)
    assert spec.cell_area_m2 == 625.0
    assert spec.width_m == spec.height_m == 200.0


def test_grid_rejects_bad_shape_and_index():
    with pytest.raises(DomainError):
        _spec(ncols=0)
    with pytest.raises(DomainError):
        _spec(cell_size_m=-1)
    spec = _spec()
    with pytest.raises(DomainError):
        spec.cell_center(2, 0)
    with pytest.raises(DomainError):
        spec.check_index(True, 0)  # type: ignore[arg-type]


def test_dem_rejects_non_rectangular_elevations():
    with pytest.raises(DomainError):
        DigitalElevationModel(
            id="broken",
            spec=_spec(),
            elevations_m=((1.0, 2.0), (3.0,)),
        )


def test_dem_round_trip_preserves_nodata():
    dem = DigitalElevationModel(
        id="with_hole",
        spec=_spec(),
        elevations_m=((1.0, -9999.0), (2.0, 3.0)),
        nodata=-9999.0,
        description="one missing cell",
    )
    restored = DigitalElevationModel.from_dict(dem.to_dict())
    assert restored == dem
    assert restored.elevation_at(0, 1) == -9999.0
    assert isinstance(restored.elevations_m[0][0], float)


def test_rainfall_totals_gaps_and_rejects_overlap():
    series = RainfallSeries(
        id="gap",
        intervals=(
            RainfallInterval(0.0, 1.0, 2.0),
            RainfallInterval(2.0, 3.0, 0.0),
            RainfallInterval(4.0, 5.0, 3.0),
        ),
    )
    assert series.total_depth_mm == 5.0
    assert series.duration_hours == 5.0
    assert series.intervals[0].intensity_mm_per_hour == 2.0
    restored = RainfallSeries.from_dict(series.to_dict())
    assert restored == series

    with pytest.raises(DomainError, match="overlap"):
        RainfallSeries(
            id="bad",
            intervals=(
                RainfallInterval(0.0, 1.0, 1.0),
                RainfallInterval(0.5, 1.5, 1.0),
            ),
        )
    with pytest.raises(DomainError, match="uniform"):
        RainfallSeries(
            id="gridded",
            intervals=(RainfallInterval(0.0, 1.0, 1.0),),
            distribution="gridded",
        )


def test_wet_mask_uses_threshold_and_summarizes_area():
    raster = InundationRaster(
        spec=_spec(),
        depth_m=((0.0, 0.009), (0.01, 1.5)),
        wet_threshold_m=0.01,
    )
    mask = raster.wet_mask()
    assert mask.wet == ((False, False), (True, True))
    assert raster.max_depth_m == 1.5
    assert raster.wet_cell_count == 2
    assert raster.inundated_area_m2 == 200.0
    assert WetDryMask.from_dict(mask.to_dict()) == mask
    assert InundationRaster.from_dict(raster.to_dict()) == raster

    with pytest.raises(DomainError):
        InundationRaster(spec=_spec(), depth_m=((0.0, -0.1), (0.0, 0.0)))


def test_scenario_result_reduces_an_existing_raster():
    scenario = _scenario()
    raster = InundationRaster(
        spec=scenario.dem.spec,
        depth_m=((0.0, 0.2), (0.0, 1.5)),
    )
    result = ScenarioResult.from_inundation(scenario, raster)
    assert result == ScenarioResult.from_dict(result.to_dict())
    assert result.max_depth_m == 1.5
    assert result.inundated_area_m2 == 200.0
    assert result.wet_cell_count == 2
    assert result.cell_count == 4
    assert result.inundated_fraction == 0.5
    assert result.rainfall_total_mm == 10.0
    assert result.duration_hours == 1.0
    assert result.dem_id == "tiny"
    assert result.rainfall_id == "tiny_rain"

    document = ScenarioDocument.from_dict(scenario.to_dict())
    assert document.dem_id == "tiny"
    assert document.rainfall_id == "tiny_rain"


def test_result_rejects_a_different_grid_and_impossible_counts():
    scenario = _scenario()
    other = InundationRaster(
        spec=_spec(cell_size_m=20.0),
        depth_m=((0.0, 0.0), (0.0, 1.0)),
    )
    with pytest.raises(DomainError, match="grid spec"):
        ScenarioResult.from_inundation(scenario, other)
    with pytest.raises(DomainError, match="wet_cell_count"):
        ScenarioResult(
            scenario_id="tiny_case",
            dem_id="tiny",
            rainfall_id="tiny_rain",
            max_depth_m=1.0,
            inundated_area_m2=10.0,
            wet_cell_count=5,
            cell_count=4,
            rainfall_total_mm=1.0,
            duration_hours=1.0,
        )
