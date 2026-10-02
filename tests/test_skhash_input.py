"""Tests for rehash.core.skhash_input."""

import csv

from rehash.config import SKHashConfig
from rehash.core import skhash_input
from rehash.core.models import EventTask, PolarityObservation


def make_task(with_sp=True):
    observations = [
        PolarityObservation(
            network="NT",
            station="STA1",
            location="",
            channel="HHZ",
            latitude=38.1,
            longitude=22.1,
            elevation=100.0,
            polarity=1.0,
            sp_ratio=2.5 if with_sp else None,
        ),
        PolarityObservation(
            network="NT",
            station="STA2",
            location="00",
            channel="HHZ",
            latitude=38.2,
            longitude=22.2,
            elevation=250.0,
            polarity=-1.0,
        ),
    ]
    return EventTask(
        event_id="evt/2026abc",
        origin_id="org/1",
        origin_time="2026-01-02T03:04:05.60",
        latitude=38.15,
        longitude=22.15,
        depth_km=9.5,
        observations=observations,
    )


def read_csv(path):
    with open(path, newline="") as fid:
        return list(csv.DictReader(fid))


def test_writes_all_files(tmp_path):
    config = SKHashConfig(velocity_models=["vm.txt"])
    control = skhash_input.write_inputs(make_task(), tmp_path, config)
    assert control.is_file()
    for name in (
        skhash_input.CATALOG_FILE,
        skhash_input.STATION_FILE,
        skhash_input.POLARITY_FILE,
        skhash_input.AMPLITUDE_FILE,
    ):
        assert (tmp_path / name).is_file()


def test_catalog_row(tmp_path):
    skhash_input.write_inputs(make_task(), tmp_path, SKHashConfig())
    rows = read_csv(tmp_path / skhash_input.CATALOG_FILE)
    assert rows == [
        {
            "event_id": "evt/2026abc",
            "time": "2026-01-02T03:04:05.60",
            "latitude": "38.15",
            "longitude": "22.15",
            "depth": "9.5",
        }
    ]


def test_blank_location_mapped(tmp_path):
    skhash_input.write_inputs(make_task(), tmp_path, SKHashConfig())
    rows = read_csv(tmp_path / skhash_input.POLARITY_FILE)
    assert rows[0]["location"] == "--"
    assert rows[1]["location"] == "00"
    assert rows[0]["p_polarity"] == "1.0"
    assert rows[1]["p_polarity"] == "-1.0"


def test_amplitude_file_only_with_ratios(tmp_path):
    skhash_input.write_inputs(make_task(with_sp=False), tmp_path, SKHashConfig())
    assert not (tmp_path / skhash_input.AMPLITUDE_FILE).exists()
    control = (tmp_path / skhash_input.CONTROL_FILE).read_text()
    assert "$ampfile" not in control


def test_control_file_content(tmp_path):
    config = SKHashConfig(velocity_models=["vm1.txt", "vm2.txt"], npolmin=10)
    skhash_input.write_inputs(make_task(), tmp_path, config)
    control = (tmp_path / skhash_input.CONTROL_FILE).read_text()
    assert "$input_format\nSKHASH\n" in control
    assert "$npolmin\n10\n" in control
    assert "$num_cpus\n1\n" in control
    assert "$use_fortran\nTrue\n" in control
    # both velocity models, resolved to absolute paths
    assert control.count("vm1.txt") == 1 and control.count("vm2.txt") == 1
    # plots must be impossible to enable
    assert "plot" not in control
