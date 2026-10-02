"""Configuration loading and validation for REHASH (config.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from math import isfinite
from pathlib import Path
from types import UnionType
from typing import get_args, get_origin, get_type_hints

import yaml


class ConfigError(Exception):
    """Raised when config.yaml is missing, malformed or fails validation."""


@dataclass
class SeisCompConfig:
    """Options consumed by the scclient module."""

    host: str | None = None
    database: str | None = None
    wait_time: int = 300
    reprocess: bool = False


@dataclass
class SKHashConfig:
    """SKHASH invocation options. Input/output paths are pipeline-managed
    (ephemeral per-event work dir) and deliberately not configurable."""

    executable: str = "SKHASH"
    # 1D velocity model file(s) used by SKHASH to compute takeoff angles
    velocity_models: list[str] = field(default_factory=lambda: ["velocity_models/CRL.forhash.txt"])
    timeout: float = 120.0  # seconds per event before the subprocess is killed
    npolmin: int = 8
    nmc: int = 30
    maxout: int = 500
    badfrac: float = 0.2
    badmin: int = 1
    qbadfrac: float = 0.2
    qbadmin: int = 1
    max_agap: float = 270.0
    max_pgap: float = 90.0
    dang: float = 5.0
    delmax: float = 100.0
    cangle: float = 45.0
    prob_max: float = 0.2
    iterative_avg: bool = True
    require_location_match: bool = False
    use_fortran: bool = True
    recompute_lookup_table: bool = True


@dataclass
class OutputConfig:
    """Per-event SKHASH input/output files on a mounted volume."""

    directory: str = "output"
    # false: run SKHASH in an ephemeral work dir and keep nothing
    save_files: bool = True


@dataclass
class LoggingConfig:
    level: str = "DEBUG"
    file: str | None = None


@dataclass
class Config:
    seiscomp: SeisCompConfig = field(default_factory=SeisCompConfig)
    skhash: SKHashConfig = field(default_factory=SKHashConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def _matches_type(value, annotation) -> bool:
    if get_origin(annotation) is UnionType:
        return any(_matches_type(value, option) for option in get_args(annotation))
    if get_origin(annotation) is list:
        return isinstance(value, list) and all(
            _matches_type(item, get_args(annotation)[0]) for item in value
        )
    if annotation is float:
        return type(value) in (int, float) and isfinite(value)
    return type(value) is annotation


def _build_section(cls, name: str, data: dict):
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ConfigError(f"Unknown keys in '{name}' section: {sorted(unknown)}")
    hints = get_type_hints(cls)
    for key, value in data.items():
        if not _matches_type(value, hints[key]):
            raise ConfigError(f"{name}.{key} has an invalid type or non-finite value")
    return cls(**data)


def _validate(config: Config) -> None:
    if config.logging.level.upper() not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        raise ConfigError("logging.level must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
    if config.seiscomp.wait_time < 0:
        raise ConfigError("seiscomp.wait_time must be >= 0")
    if not config.skhash.velocity_models:
        raise ConfigError("skhash.velocity_models must list at least one file")
    if config.skhash.npolmin < 1:
        raise ConfigError("skhash.npolmin must be >= 1")
    if config.skhash.timeout <= 0:
        raise ConfigError("skhash.timeout must be > 0")
    if config.output.save_files and not config.output.directory:
        raise ConfigError("output.directory must be a non-empty path")


def load_config(path: str | Path) -> Config:
    """Load and validate a config.yaml file. Missing sections/keys use defaults."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")

    try:
        with open(path) as fid:
            raw = yaml.safe_load(fid)
    except yaml.YAMLError:
        raise ConfigError(f"Invalid YAML in {path}") from None
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError(f"Top level of {path} must be a mapping")

    sections = {f.name: f.default_factory for f in fields(Config)}
    unknown = set(raw) - set(sections)
    if unknown:
        raise ConfigError(f"Unknown top-level sections: {sorted(unknown)}")

    kwargs = {}
    for f in fields(Config):
        data = raw.get(f.name, {})
        if not isinstance(data, dict):
            raise ConfigError(f"Section '{f.name}' must be a mapping")
        section_cls = f.default_factory
        kwargs[f.name] = _build_section(section_cls, f.name, data)

    config = Config(**kwargs)
    _validate(config)
    return config
