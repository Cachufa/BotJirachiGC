"""When-shiny path: stop, keep the save, log attempt + summary, notify stub."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from botjirachi.huntlog import HuntLog, total_hunt_seconds, utc_now
from botjirachi.notify import notify_shiny


def handle_shiny(
    hunt_log: HuntLog,
    *,
    attempt: int,
    duration_s: float,
    sv: int,
    save_path: Path,
    when: datetime | None = None,
) -> int:
    """Log the shiny attempt and hunt summary, then return exit code 0.

    Does not restore or overwrite the working Ruby save. Callers must not
    call restore after this returns.
    """
    stamp = when if when is not None else utc_now()
    hunt_log.write_attempt(
        attempt=attempt,
        duration_s=duration_s,
        sv=sv,
        result="shiny",
        when=stamp,
    )
    started = hunt_log.hunt_started() or stamp
    total_s = total_hunt_seconds(started, stamp)
    hunt_log.write_shiny_summary(
        attempts=attempt,
        total_s=total_s,
        sv=sv,
        save=save_path,
        when=stamp,
    )
    notify_shiny(
        attempt=attempt,
        sv=sv,
        total_s=total_s,
        save_path=save_path,
    )
    return 0
