"""Copy the original Ruby save into Dolphin GBA slots. Never write into resources/."""

from __future__ import annotations

import shutil
from pathlib import Path

from botjirachi.paths import HuntPaths


class RestoreError(Exception):
    """Source missing, or a destination would mutate resources/."""


def restore_ruby_save(paths: HuntPaths) -> tuple[Path, Path]:
    """Copy `paths.ruby_sav` onto both Dolphin GBA save names.

    Returns the two destination paths. Does not parse the save. Callers must
    skip this on a shiny hit so the working `.sav` is left intact.
    """
    source = paths.ruby_sav
    if not source.is_file():
        raise RestoreError(f"Original Ruby save is missing: {source}")

    destinations = (paths.dolphin_ruby_sav, paths.dolphin_ruby_sav_port2)
    for dest in destinations:
        _copy_outside_resources(source, dest, paths.resources_dir)
    return destinations


def _copy_outside_resources(source: Path, dest: Path, resources: Path) -> None:
    dest_resolved = dest.expanduser().resolve()
    source_resolved = source.resolve()
    if dest_resolved == source_resolved:
        raise RestoreError(
            f"Refusing to overwrite the original Ruby save: {dest_resolved}"
        )
    if dest_resolved.is_relative_to(resources):
        raise RestoreError(
            f"Refusing to write Ruby save into resources/: {dest_resolved}"
        )
    dest_resolved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest_resolved)
