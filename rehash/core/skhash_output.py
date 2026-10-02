"""Parses the SKHASH mechanism output file into an FMResult."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from obspy.imaging.beachball import aux_plane

from rehash.core.models import EventTask, FMResult

logger = logging.getLogger(__name__)


def _float(row: dict, key: str) -> float | None:
    value = row.get(key, "")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percent(row: dict, key: str) -> float | None:
    # SKHASH reports these as percentages; SeisComP expects 0-1 fractions
    value = _float(row, key)
    return round(value / 100.0, 4) if value is not None else None


def _aux_plane(strike, dip, rake) -> tuple[float | None, float | None, float | None]:
    if strike is None or dip is None or rake is None:
        return None, None, None
    strike2, dip2, rake2 = aux_plane(strike, dip, rake)
    return round(strike2 % 360, 2), round(dip2, 2), round(rake2, 2)


def _deg2(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def parse_output(path: Path, task: EventTask) -> FMResult:
    """Read outfile1 and return the preferred (most probable) mechanism."""
    if not path.is_file():
        return FMResult(
            event_id=task.event_id,
            origin_id=task.origin_id,
            error="SKHASH produced no output (event rejected by quality criteria?)",
        )
    with open(path, newline="") as fid:
        rows = [row for row in csv.DictReader(fid) if row.get("event_id") == task.event_id]
    if not rows:
        return FMResult(
            event_id=task.event_id,
            origin_id=task.origin_id,
            error="SKHASH output contains no mechanism for this event",
        )

    preferred = max(rows, key=lambda row: _float(row, "prob_mech") or 0.0)
    n_pol = _float(preferred, "num_p_pol")
    strike = _deg2(_float(preferred, "strike"))
    dip = _deg2(_float(preferred, "dip"))
    rake = _deg2(_float(preferred, "rake"))
    strike2, dip2, rake2 = _aux_plane(strike, dip, rake)
    return FMResult(
        event_id=task.event_id,
        origin_id=task.origin_id,
        strike=strike,
        dip=dip,
        rake=rake,
        strike2=strike2,
        dip2=dip2,
        rake2=rake2,
        azimuthal_gap=_float(preferred, "azimuthal_gap"),
        station_polarity_count=int(n_pol) if n_pol is not None else None,
        polarity_misfit=_percent(preferred, "polarity_misfit"),
        station_distribution_ratio=_percent(preferred, "sta_distribution_ratio"),
        quality=preferred.get("quality") or None,
        fault_plane_uncertainty=_float(preferred, "fault_plane_uncertainty"),
        aux_plane_uncertainty=_float(preferred, "aux_plane_uncertainty"),
        takeoff_gap=_float(preferred, "takeoff_gap"),
        probability=_percent(preferred, "prob_mech"),
        sp_misfit=_float(preferred, "sp_misfit"),
        multiple_solutions=len(rows) > 1 or preferred.get("mult_solution_flag") == "True",
    )
