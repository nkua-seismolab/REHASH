"""Tests for rehash.core.skhash_output."""

from pytest import approx

from rehash.core import skhash_output
from rehash.core.models import EventTask

HEADER = (
    "event_id,strike,dip,rake,quality,fault_plane_uncertainty,aux_plane_uncertainty,"
    "num_p_pol,num_sp_ratios,azimuthal_gap,takeoff_gap,polarity_misfit,prob_mech,"
    "sta_distribution_ratio,sp_misfit,mult_solution_flag,time,origin_lat,origin_lon,"
    "origin_depth_km,horz_uncert_km,vert_uncert_km"
)
ROW = (
    "ev1,238.8,37.3,-70.0,B,14.7,14.5,16,18,84.1,21.5,15.1,100.0,65.8,-56.1,False,"
    "2026-01-02 03:04:05,38.15,22.15,9.5,1.0,1.0"
)
ROW_ALT = (
    "ev1,22.6,70.6,150.7,D,46.4,39.8,16,18,84.1,21.5,24.4,21.7,69.4,-23.1,True,"
    "2026-01-02 03:04:05,38.15,22.15,9.5,1.0,1.0"
)

TASK = EventTask(
    event_id="ev1",
    origin_id="org1",
    origin_time="2026-01-02T03:04:05.60",
    latitude=38.15,
    longitude=22.15,
    depth_km=9.5,
)


def write(tmp_path, *lines):
    path = tmp_path / "mechanisms.csv"
    path.write_text("\n".join(lines) + "\n")
    return path


def test_single_solution(tmp_path):
    result = skhash_output.parse_output(write(tmp_path, HEADER, ROW), TASK)
    assert result.ok
    assert result.strike == 238.8
    assert result.dip == 37.3
    assert result.rake == -70.0
    assert result.quality == "B"
    assert result.azimuthal_gap == 84.1
    assert result.takeoff_gap == 21.5
    assert result.station_polarity_count == 16
    # percentages converted to fractions
    assert result.polarity_misfit == approx(0.151)
    assert result.probability == approx(1.0)
    assert result.station_distribution_ratio == approx(0.658)
    assert result.sp_misfit == -56.1
    assert result.fault_plane_uncertainty == 14.7
    assert result.aux_plane_uncertainty == 14.5
    assert result.multiple_solutions is False


def test_aux_plane_computed(tmp_path):
    result = skhash_output.parse_output(write(tmp_path, HEADER, ROW), TASK)
    assert result.strike2 == approx(34.21)
    assert result.dip2 == approx(55.29)
    assert result.rake2 == approx(-104.6)
    # published values carry at most 2 decimals
    for value in (result.strike2, result.dip2, result.rake2):
        assert value == round(value, 2)
    assert 0 <= result.strike2 < 360
    assert 0 <= result.dip2 <= 90


def test_aux_plane_missing_when_no_solution(tmp_path):
    row = ROW.replace("238.8", "", 1)
    result = skhash_output.parse_output(write(tmp_path, HEADER, row), TASK)
    assert result.strike is None
    assert result.strike2 is None
    assert result.dip2 is None
    assert result.rake2 is None


def test_multiple_solutions_prefers_most_probable(tmp_path):
    result = skhash_output.parse_output(write(tmp_path, HEADER, ROW_ALT, ROW), TASK)
    assert result.ok
    assert result.strike == 238.8  # prob 100.0 beats 21.7
    assert result.multiple_solutions is True


def test_missing_file(tmp_path):
    result = skhash_output.parse_output(tmp_path / "missing.csv", TASK)
    assert not result.ok
    assert "no output" in result.error


def test_no_matching_event(tmp_path):
    other = ROW.replace("ev1", "other", 1)
    result = skhash_output.parse_output(write(tmp_path, HEADER, other), TASK)
    assert not result.ok
    assert "no mechanism" in result.error
