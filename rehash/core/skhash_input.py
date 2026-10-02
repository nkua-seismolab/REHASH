"""Writes the SKHASH input files (control file + CSVs) for one event.

All files live in an ephemeral per-event work directory that the operator
never sees; only the velocity model paths come from the configuration.
"""

from __future__ import annotations

import csv
from pathlib import Path

from rehash.config import SKHashConfig
from rehash.core.models import EventTask

CONTROL_FILE = "control.txt"
CATALOG_FILE = "catalog.csv"
STATION_FILE = "stations.csv"
POLARITY_FILE = "polarities.csv"
AMPLITUDE_FILE = "sp_ratios.csv"
OUTPUT_FILE = "mechanisms.csv"

# SKHashConfig fields forwarded verbatim as control-file parameters
_FORWARDED_PARAMS = (
    "npolmin",
    "nmc",
    "maxout",
    "badfrac",
    "badmin",
    "qbadfrac",
    "qbadmin",
    "max_agap",
    "max_pgap",
    "dang",
    "delmax",
    "cangle",
    "prob_max",
    "iterative_avg",
    "require_location_match",
    "use_fortran",
    "recompute_lookup_table",
)


def _location(code: str) -> str:
    return code if code else "--"


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="") as fid:
        writer = csv.writer(fid)
        writer.writerow(header)
        writer.writerows(rows)


def write_inputs(task: EventTask, work_dir: Path, config: SKHashConfig) -> Path:
    """Write all SKHASH inputs into work_dir; returns the control file path."""
    _write_csv(
        work_dir / CATALOG_FILE,
        ["event_id", "time", "latitude", "longitude", "depth"],
        [[task.event_id, task.origin_time, task.latitude, task.longitude, task.depth_km]],
    )

    stations = {}
    for obs in task.observations:
        key = (obs.network, obs.station, _location(obs.location), obs.channel)
        stations[key] = [*key, obs.latitude, obs.longitude, obs.elevation]
    _write_csv(
        work_dir / STATION_FILE,
        ["network", "station", "location", "channel", "latitude", "longitude", "elevation"],
        list(stations.values()),
    )

    _write_csv(
        work_dir / POLARITY_FILE,
        ["event_id", "network", "station", "location", "channel", "p_polarity"],
        [
            [
                task.event_id,
                obs.network,
                obs.station,
                _location(obs.location),
                obs.channel,
                obs.polarity,
            ]
            for obs in task.observations
        ],
    )

    sp_rows = [
        [
            task.event_id,
            obs.network,
            obs.station,
            _location(obs.location),
            obs.channel,
            obs.sp_ratio,
        ]
        for obs in task.observations
        if obs.sp_ratio is not None
    ]
    if sp_rows:
        _write_csv(
            work_dir / AMPLITUDE_FILE,
            ["event_id", "network", "station", "location", "channel", "sp_ratio"],
            sp_rows,
        )

    control = work_dir / CONTROL_FILE
    control.write_text(_control_text(work_dir, bool(sp_rows), config))
    return control


def _control_text(work_dir: Path, with_amplitudes: bool, config: SKHashConfig) -> str:
    params: dict[str, object] = {
        "input_format": "SKHASH",
        "catfile": work_dir / CATALOG_FILE,
        "stfile": work_dir / STATION_FILE,
        "fpfile": work_dir / POLARITY_FILE,
        "outfile1": work_dir / OUTPUT_FILE,
        "vmodel_paths": "\n".join(str(Path(p).resolve()) for p in config.velocity_models),
        "num_cpus": 1,
        "overwrite_output_file": True,
        # plots are intentionally impossible to enable: no outfolder_plots/plot_* keys
    }
    if with_amplitudes:
        params["ampfile"] = work_dir / AMPLITUDE_FILE
    for name in _FORWARDED_PARAMS:
        params[name] = getattr(config, name)
    return "".join(f"${key}\n{value}\n\n" for key, value in params.items())
