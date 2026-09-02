"""User alerts after a shiny hit. v1 is a stub."""

from __future__ import annotations

from pathlib import Path


def notify_shiny(
    *,
    attempt: int,
    sv: int,
    total_s: float,
    save_path: Path,
) -> None:
    """Alert after the shiny summary is written.

    TODO: Discord webhook, macOS notification, or another channel (not v1).
    """
    pass
