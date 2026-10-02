"""Per-event orchestration: write SKHASH inputs, run SKHASH, parse the output."""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from rehash.config import Config, ConfigError
from rehash.core import skhash_input, skhash_output, skhash_runner
from rehash.core.models import EventTask, FMResult

logger = logging.getLogger(__name__)

_EVCODE_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def sanitize_event_id(event_id: str) -> str:
    """Filesystem-safe event code derived from the SeisComP public ID."""
    return _EVCODE_UNSAFE.sub("_", event_id)


class FMProcessor:
    """Runs the SKHASH pipeline for one event at a time.

    Errors are contained per event: process() and process_batch() always
    return FMResults, carrying an error message instead of raising.
    """

    def __init__(self, config: Config):
        self.config = config.skhash
        self.output = config.output
        for path in self.config.velocity_models:
            if not Path(path).is_file():
                raise ConfigError(f"Velocity model file not found: {path}")
        if self.output.save_files:
            Path(self.output.directory).mkdir(parents=True, exist_ok=True)
        skhash_runner.check_available(self.config)

    def process(self, task: EventTask) -> FMResult:
        t0 = time.perf_counter()
        if self.output.save_files:
            work_dir = (
                Path(self.output.directory)
                / sanitize_event_id(task.event_id)
                / datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            )
            work_dir.mkdir(parents=True, exist_ok=True)
        else:
            work_dir = Path(tempfile.mkdtemp(prefix="rehash-"))
        try:
            control = skhash_input.write_inputs(task, work_dir, self.config)
            skhash_runner.run(control, self.config)
            result = skhash_output.parse_output(work_dir / skhash_input.OUTPUT_FILE, task)
        except Exception as exc:
            logger.warning("Event %s failed: %s", task.event_id, exc)
            return FMResult(event_id=task.event_id, origin_id=task.origin_id, error=str(exc))
        finally:
            if not self.output.save_files:
                shutil.rmtree(work_dir, ignore_errors=True)
        logger.info(
            "Event %s: SKHASH finished in %.1fs (%s)",
            task.event_id,
            time.perf_counter() - t0,
            "ok" if result.ok else result.error,
        )
        return result

    def process_batch(self, tasks: list[EventTask]) -> dict[str, FMResult]:
        return {task.event_id: self.process(task) for task in tasks}
