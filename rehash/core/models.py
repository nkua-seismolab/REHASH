"""Boundary dataclasses exchanged between the client and core modules."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PolarityObservation:
    """One station's P first motion (and optional S/P ratio) for the inversion."""

    network: str
    station: str
    location: str
    channel: str
    latitude: float
    longitude: float
    elevation: float  # metres
    polarity: float  # +1 up, -1 down; fractional values carry lower weight
    sp_ratio: float | None = None


@dataclass
class EventTask:
    """Everything the core needs to compute one focal mechanism."""

    event_id: str
    origin_id: str
    origin_time: str  # ISO 8601
    latitude: float
    longitude: float
    depth_km: float
    observations: list[PolarityObservation] = field(default_factory=list)


@dataclass
class FMResult:
    """Preferred focal mechanism of one event. Angles in degrees, ratios as 0-1 fractions."""

    event_id: str
    origin_id: str
    strike: float | None = None
    dip: float | None = None
    rake: float | None = None
    # auxiliary plane, computed from the preferred plane (SKHASH emits only one)
    strike2: float | None = None
    dip2: float | None = None
    rake2: float | None = None
    azimuthal_gap: float | None = None
    station_polarity_count: int | None = None
    polarity_misfit: float | None = None
    station_distribution_ratio: float | None = None
    # quality metrics without a SeisComP datamodel field, published as comments
    quality: str | None = None
    fault_plane_uncertainty: float | None = None
    aux_plane_uncertainty: float | None = None
    takeoff_gap: float | None = None
    probability: float | None = None
    sp_misfit: float | None = None
    multiple_solutions: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None
