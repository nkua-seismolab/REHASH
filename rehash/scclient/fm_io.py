"""Conversion between core focal mechanism results and SeisComP objects.

Free of package-internal imports; result objects are duck-typed.
"""

from __future__ import annotations

import json
import logging
import math

from seiscomp import client, core, datamodel

logger = logging.getLogger(__name__)

# pick polarity enum -> HASH-style numeric first motion
POLARITY_VALUES = {
    datamodel.POSITIVE: 1.0,
    datamodel.NEGATIVE: -1.0,
}


def polarity_value(pick) -> float | None:
    """Numeric first motion of a pick (+1 up, -1 down), None if unset/undecidable."""
    try:
        return POLARITY_VALUES.get(pick.polarity())
    except Exception:
        return None


def sp_ratio_from_comments(pick) -> float | None:
    """Read a finite positive S/P ratio from the REPOL JSON comment."""
    for index in range(pick.commentCount()):
        comment = pick.comment(index)
        if comment.id() != f"{pick.publicID()}/comment/repol":
            continue
        try:
            payload = json.loads(comment.text())
            value = payload.get("sp_ratio") if isinstance(payload, dict) else None
            if value is None or isinstance(value, bool):
                return None
            ratio = float(value)
            if math.isfinite(ratio) and ratio > 0:
                return ratio
        except (ValueError, TypeError, OverflowError):
            logger.warning("Pick %s: invalid REPOL S/P comment", pick.publicID())
        return None
    return None


def station_coords(network: str, station: str, time) -> tuple[float, float, float] | None:
    """(latitude, longitude, elevation_m) from the loaded inventory, or None."""
    try:
        sta = client.Inventory.Instance().getStation(network, station, time)
        return (sta.latitude(), sta.longitude(), sta.elevation())
    except Exception:
        return None


def _real_quantity(value: float) -> datamodel.RealQuantity:
    return datamodel.RealQuantity(float(value))


def build_focal_mechanism(origin_id: str, result, author: str) -> datamodel.FocalMechanism:
    """Build a FocalMechanism from an FMResult-like object (see core models)."""
    fm = datamodel.FocalMechanism.Create()
    fm.setTriggeringOriginID(origin_id)

    np1 = datamodel.NodalPlane()
    np1.setStrike(_real_quantity(result.strike))
    np1.setDip(_real_quantity(result.dip))
    np1.setRake(_real_quantity(result.rake))
    planes = datamodel.NodalPlanes()
    planes.setNodalPlane1(np1)
    if result.strike2 is not None and result.dip2 is not None and result.rake2 is not None:
        np2 = datamodel.NodalPlane()
        np2.setStrike(_real_quantity(result.strike2))
        np2.setDip(_real_quantity(result.dip2))
        np2.setRake(_real_quantity(result.rake2))
        planes.setNodalPlane2(np2)
    fm.setNodalPlanes(planes)

    if result.azimuthal_gap is not None:
        fm.setAzimuthalGap(float(result.azimuthal_gap))
    if result.station_polarity_count is not None:
        fm.setStationPolarityCount(int(result.station_polarity_count))
    if result.polarity_misfit is not None:
        fm.setMisfit(float(result.polarity_misfit))
    if result.station_distribution_ratio is not None:
        fm.setStationDistributionRatio(float(result.station_distribution_ratio))

    fm.setMethodID("REHASH")
    fm.setEvaluationMode(datamodel.AUTOMATIC)
    ci = datamodel.CreationInfo()
    ci.setAuthor(author)
    ci.setCreationTime(core.Time.GMT())
    fm.setCreationInfo(ci)
    return fm


def add_quality_comments(fm, result, software: str, version: str) -> None:
    """Attach quality metrics and provenance as a single JSON comment.

    Call only after fm was added to EventParameters: Notifier serialization
    ignores children (Archive::IGNORE_CHILDS), so the comment travels as its
    own notifier and its parent must already exist when it is applied.
    """
    # quality metrics without a datamodel field travel in one flat JSON comment,
    # structured like the REPOL/RESS pick comments (units folded into key names)
    metrics = {
        "quality": result.quality,
        "fault_plane_uncertainty_deg": result.fault_plane_uncertainty,
        "aux_plane_uncertainty_deg": result.aux_plane_uncertainty,
        "takeoff_gap_deg": result.takeoff_gap,
        "probability": result.probability,
        "sp_misfit": result.sp_misfit,
    }
    payload = {
        "provenance": {
            "software": software,
            "version": version,
            "stored_at": core.Time.GMT().iso(),
        },
        **{key: value for key, value in metrics.items() if value is not None},
        "multiple_solutions": result.multiple_solutions,
    }
    comment = datamodel.Comment()
    comment.setId(f"{fm.publicID()}/comment/rehash")
    comment.setText(json.dumps(payload, ensure_ascii=True))
    fm.add(comment)
