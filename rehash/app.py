"""Wires the scclient listener to the core focal mechanism processor.

dispatch runs on the main thread (SeisComP objects), the processor's
process_batch runs in the worker process (core objects only), and
finalize runs on the main thread again.
"""

from __future__ import annotations

import logging

from seiscomp import datamodel

from rehash import __version__ as rehash_version
from rehash.config import Config
from rehash.core.models import EventTask, PolarityObservation
from rehash.scclient import OUTPUT_GROUP, fm_io, pick_io

logger = logging.getLogger(__name__)


def _has_focal_mechanism(event) -> bool:
    try:
        return bool(event.preferredFocalMechanismID())
    except Exception:
        return False


def make_dispatch(config: Config):
    """Build the main-thread callable that turns an event into an EventTask."""

    def dispatch(app, event, origin, picks):
        event_id = event.publicID()
        if _has_focal_mechanism(event) and not config.seiscomp.reprocess:
            logger.info("Event %s already has a focal mechanism, skipping", event_id)
            return [], None

        arrivals = pick_io.arrival_index(origin)
        observations = []
        for pick in picks:
            if not pick_io.is_p_pick(pick, arrivals.get(pick.publicID())):
                continue
            polarity = fm_io.polarity_value(pick)
            if polarity is None:
                continue
            wfid = pick.waveformID()
            coords = fm_io.station_coords(
                wfid.networkCode(), wfid.stationCode(), pick.time().value()
            )
            if coords is None:
                logger.warning(
                    "No station coordinates for %s, skipping pick", pick_io.seed_id(pick)
                )
                continue
            latitude, longitude, elevation = coords
            observations.append(
                PolarityObservation(
                    network=wfid.networkCode(),
                    station=wfid.stationCode(),
                    location=wfid.locationCode(),
                    channel=wfid.channelCode(),
                    latitude=latitude,
                    longitude=longitude,
                    elevation=elevation,
                    polarity=polarity,
                    sp_ratio=fm_io.sp_ratio_from_comments(pick),
                )
            )
        n_sp = sum(1 for obs in observations if obs.sp_ratio is not None)
        logger.info(
            "Event %s: %d polarities (%d with S/P) from %d picks",
            event_id,
            len(observations),
            n_sp,
            len(picks),
        )
        if len(observations) < config.skhash.npolmin:
            logger.info(
                "Event %s: %d polarities < npolmin=%d, skipping",
                event_id,
                len(observations),
                config.skhash.npolmin,
            )
            return [], None

        task = EventTask(
            event_id=event_id,
            origin_id=origin.publicID(),
            origin_time=origin.time().value().toString("%Y-%m-%dT%H:%M:%S.%f"),
            latitude=origin.latitude().value(),
            longitude=origin.longitude().value(),
            depth_km=origin.depth().value(),
            observations=observations,
        )
        # only plain identifiers cross to finalize; no SeisComP objects are held
        return [task], (event_id, origin.publicID())

    return dispatch


def make_finalize(config: Config):
    """Build the main-thread callable that publishes the focal mechanism."""

    def finalize(app, context, results):
        event_id, origin_id = context
        result = results.get(event_id)
        if result is None:
            logger.info("No focal mechanism result for event %s", event_id)
            return
        if not result.ok:
            logger.warning("Event %s: focal mechanism failed: %s", event_id, result.error)
            return

        ep = datamodel.EventParameters()
        datamodel.Notifier.Enable()
        try:
            fm = fm_io.build_focal_mechanism(origin_id, result, author=app.name())
            # parent-first notifier order: the FM must be added to a parent
            # before its comments, or their notifiers reference a missing FM
            ep.add(fm)
            fm_io.add_quality_comments(fm, result, software="REHASH", version=rehash_version)
        finally:
            msg = datamodel.Notifier.GetMessage()
            datamodel.Notifier.Disable()

        logger.info(
            "Event %s: strike=%.1f dip=%.1f rake=%.1f quality=%s prob=%s%s",
            event_id,
            result.strike,
            result.dip,
            result.rake,
            result.quality,
            f"{result.probability:.2f}" if result.probability is not None else "N/A",
            " (multiple solutions)" if result.multiple_solutions else "",
        )
        app.send_message(OUTPUT_GROUP, msg)

    return finalize
