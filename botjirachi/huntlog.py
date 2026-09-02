"""Append-only attempt log: stdout and `logs/attempts.txt`, same line.

Restarting the process continues `attempt` from the file. Hunt start time is
persisted and is not reset on resume. Resume does not continue an in-game
attempt; only the counter and wall-clock start survive.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from botjirachi.party import SHINY_SV_MAX

ATTEMPTS_NAME = "attempts.txt"
HUNT_STARTED_NAME = "hunt_started.txt"
SHINY_NAME = "shiny.txt"

# One field in the attempt line: `attempt=12` bounded by start/whitespace.
_ATTEMPT_RE = re.compile(r"(?:^|\s)attempt=(\d+)(?:\s|$)")
_RESULT_RE = re.compile(r"(?:^|\s)result=(\S+)(?:\s|$)")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def format_utc(when: datetime) -> str:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: str) -> datetime | None:
    raw = text.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def result_for_sv(sv: int) -> str:
    return "shiny" if sv <= SHINY_SV_MAX else "fail"


def last_attempt_number(text: str) -> int | None:
    """Last `attempt=N` in file order. Headers and malformed lines are ignored."""
    last: int | None = None
    for line in text.splitlines():
        match = _ATTEMPT_RE.search(line)
        if match:
            last = int(match.group(1))
    return last


def last_attempt_result(text: str) -> str | None:
    """`result=` on the last attempt line. Headers and malformed lines are ignored."""
    last: str | None = None
    for line in text.splitlines():
        if not _ATTEMPT_RE.search(line):
            continue
        match = _RESULT_RE.search(line)
        if match:
            last = match.group(1)
    return last


def total_hunt_seconds(started: datetime, when: datetime) -> float:
    """Wall-clock seconds from hunt start to `when`, including session gaps."""
    delta = (
        when.astimezone(timezone.utc) - started.astimezone(timezone.utc)
    ).total_seconds()
    return max(0.0, delta)


def format_attempt_line(
    *,
    when: datetime,
    attempt: int,
    duration_s: float,
    sv: int,
    result: str,
) -> str:
    return (
        f"{format_utc(when)}  attempt={attempt}  "
        f"duration_s={duration_s:.1f}  sv={sv}  result={result}"
    )


def format_shiny_summary(
    *,
    when: datetime,
    attempts: int,
    total_s: float,
    sv: int,
    save: Path,
) -> str:
    return (
        f"SHINY  {format_utc(when)}  attempts={attempts}  "
        f"total_s={total_s:.1f}  sv={sv}  save={save}"
    )


class HuntLog:
    """Dual-write attempt logger. Never truncates `attempts.txt`."""

    def __init__(self, log_dir: Path, *, stdout: TextIO | None = None) -> None:
        self.log_dir = log_dir
        self.attempts_path = log_dir / ATTEMPTS_NAME
        self.hunt_started_path = log_dir / HUNT_STARTED_NAME
        self.shiny_path = log_dir / SHINY_NAME
        self._stdout = sys.stdout if stdout is None else stdout

    def prepare(self) -> tuple[datetime, int]:
        """Create `logs/`, persist hunt start if missing, return (started, next)."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        started = self.ensure_hunt_started()
        return started, self.next_attempt_number()

    def ensure_hunt_started(self, *, now: datetime | None = None) -> datetime:
        """Keep the first hunt start across process restarts."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if self.hunt_started_path.is_file():
            existing = parse_utc(self.hunt_started_path.read_text(encoding="utf-8"))
            if existing is not None:
                return existing
        started = now if now is not None else utc_now()
        self.hunt_started_path.write_text(
            format_utc(started) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return started

    def hunt_started(self) -> datetime | None:
        if not self.hunt_started_path.is_file():
            return None
        return parse_utc(self.hunt_started_path.read_text(encoding="utf-8"))

    def next_attempt_number(self) -> int:
        last = self._last_attempt_from_file()
        return 1 if last is None else last + 1

    def last_logged_result(self) -> str | None:
        text = self._attempts_text()
        return None if text is None else last_attempt_result(text)

    def write_run_header(self, started: datetime, next_attempt: int) -> None:
        """Stdout-only. Do not log secrets or dump paths here."""
        print(
            f"Hunt: started={format_utc(started)}  "
            f"next_attempt={next_attempt}  log={self.attempts_path}",
            file=self._stdout,
            flush=True,
        )

    def write_attempt(
        self,
        *,
        attempt: int,
        duration_s: float,
        sv: int,
        result: str | None = None,
        when: datetime | None = None,
    ) -> str:
        """Print and append the same attempt line. Never truncates the file."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        line = format_attempt_line(
            when=when if when is not None else utc_now(),
            attempt=attempt,
            duration_s=duration_s,
            sv=sv,
            result=result if result is not None else result_for_sv(sv),
        )
        print(line, file=self._stdout, flush=True)
        with self.attempts_path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
            fh.flush()
        return line

    def write_shiny_summary(
        self,
        *,
        attempts: int,
        total_s: float,
        sv: int,
        save: Path,
        when: datetime | None = None,
    ) -> str:
        """Print and append the same SHINY summary. Never truncates the file."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        line = format_shiny_summary(
            when=when if when is not None else utc_now(),
            attempts=attempts,
            total_s=total_s,
            sv=sv,
            save=save,
        )
        print(line, file=self._stdout, flush=True)
        with self.shiny_path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
            fh.flush()
        return line

    def _attempts_text(self) -> str | None:
        if not self.attempts_path.is_file():
            return None
        try:
            return self.attempts_path.read_text(encoding="utf-8")
        except OSError:
            return None

    def _last_attempt_from_file(self) -> int | None:
        text = self._attempts_text()
        return None if text is None else last_attempt_number(text)
