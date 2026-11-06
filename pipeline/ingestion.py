"""Failure handling and publication shared by the official PTR scrapers."""

import logging
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep

import pandas as pd

logger = logging.getLogger(__name__)


class IngestionError(RuntimeError):
    """A source could not be ingested completely; existing outputs must be kept."""


def retry[T](operation: Callable[[], T], description: str) -> T:
    """Try a source operation three times, with bounded exponential backoff."""
    for attempt in range(3):
        try:
            return operation()
        except IngestionError:
            # A nested operation already exhausted its attempts.
            raise
        except Exception as exc:
            if attempt == 2:
                raise IngestionError(f"{description} failed after 3 attempts") from exc
            logger.warning("%s failed: %s; retrying", description, exc)
            sleep(2**attempt)
    raise AssertionError("unreachable")  # pragma: no cover


def publish_csvs(frames: Mapping[Path, pd.DataFrame]) -> None:
    """Stage every CSV before replacing destinations atomically, one file at a time."""
    staged: dict[Path, Path] = {}
    try:
        for destination, frame in frames.items():
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=destination.parent, delete=False
            ) as temporary:
                staged[destination] = Path(temporary.name)
                frame.to_csv(temporary, index=False, date_format="%Y-%m-%d")
                temporary.flush()
                os.fsync(temporary.fileno())
        for destination, temporary_path in staged.items():
            os.replace(temporary_path, destination)
    finally:
        for temporary_path in staged.values():
            temporary_path.unlink(missing_ok=True)
