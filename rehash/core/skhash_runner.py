"""Runs the SKHASH command line tool on a prepared control file."""

from __future__ import annotations

import logging
import subprocess

from rehash.config import SKHashConfig

logger = logging.getLogger(__name__)


class SKHashError(RuntimeError):
    """SKHASH could not be executed or exited with an error."""


def check_available(config: SKHashConfig) -> None:
    """Fail fast at worker start-up if the SKHASH CLI is unusable."""
    try:
        subprocess.run(
            [config.executable, "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
    except FileNotFoundError:
        raise SKHashError(f"SKHASH executable not found: {config.executable}") from None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise SKHashError(f"SKHASH self-check failed: {exc}") from None
    logger.info("SKHASH executable verified: %s", config.executable)


def run(control_file, config: SKHashConfig) -> str:
    """Run SKHASH; returns its stdout. Raises SKHashError on failure."""
    cmd = [config.executable, str(control_file)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=config.timeout)
    except FileNotFoundError:
        raise SKHashError(f"SKHASH executable not found: {config.executable}") from None
    except subprocess.TimeoutExpired:
        raise SKHashError(f"SKHASH timed out after {config.timeout:.0f}s") from None

    if proc.returncode != 0:
        tail = "; ".join((proc.stderr or proc.stdout).strip().splitlines()[-5:])
        raise SKHashError(f"SKHASH exited with code {proc.returncode}: {tail}")
    logger.debug("SKHASH stdout:\n%s", proc.stdout)
    return proc.stdout
