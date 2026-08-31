"""Default and resolved filesystem paths for the hunt."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CHANNEL_ISO_NAME = "Pokemon Channel (Europe) (En,Fr,De,Es,It) (v1.00).iso"
RUBY_GBA_NAME = "Pokemon - Edicion Rubi (Spain).gba"
RUBY_SAV_NAME = "Pokemon - Edicion Rubi (Spain).sav"
RUBY_SAV_PORT2_NAME = "Pokemon - Edicion Rubi (Spain)-2.sav"

DEFAULT_DOLPHIN_APP = Path("/Applications/Dolphin.app")
DEFAULT_DOLPHIN_BINARY = DEFAULT_DOLPHIN_APP / "Contents" / "MacOS" / "Dolphin"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_dolphin_user_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "Dolphin"


def default_gba_bios() -> Path:
    return default_dolphin_user_dir() / "GBA" / "gba_bios.bin"


def resolve_path(path: Path) -> Path:
    return path.expanduser().resolve()


def dolphin_executable(path: Path) -> Path:
    """Accept either the .app bundle or the inner MacOS binary."""
    path = resolve_path(path)
    if path.suffix == ".app":
        return path / "Contents" / "MacOS" / "Dolphin"
    return path


@dataclass(frozen=True)
class HuntPaths:
    repo_root: Path
    channel_iso: Path
    ruby_gba: Path
    ruby_sav: Path
    gba_bios: Path
    dolphin_binary: Path
    dolphin_user_dir: Path

    @classmethod
    def defaults(
        cls,
        *,
        channel_iso: Path | None = None,
        ruby_gba: Path | None = None,
        ruby_sav: Path | None = None,
        gba_bios: Path | None = None,
        dolphin_binary: Path | None = None,
        dolphin_user_dir: Path | None = None,
    ) -> HuntPaths:
        root = repo_root()
        resources = root / "resources"
        user_dir = resolve_path(dolphin_user_dir or default_dolphin_user_dir())
        return cls(
            repo_root=root,
            channel_iso=resolve_path(channel_iso or resources / CHANNEL_ISO_NAME),
            ruby_gba=resolve_path(ruby_gba or resources / RUBY_GBA_NAME),
            ruby_sav=resolve_path(ruby_sav or resources / RUBY_SAV_NAME),
            gba_bios=resolve_path(gba_bios or default_gba_bios()),
            dolphin_binary=dolphin_executable(dolphin_binary or DEFAULT_DOLPHIN_BINARY),
            dolphin_user_dir=user_dir,
        )

    @property
    def resources_dir(self) -> Path:
        return (self.repo_root / "resources").resolve()

    @property
    def dolphin_ini(self) -> Path:
        return self.dolphin_user_dir / "Config" / "Dolphin.ini"

    @property
    def gcpad_ini(self) -> Path:
        return self.dolphin_user_dir / "Config" / "GCPadNew.ini"

    @property
    def gba_ini(self) -> Path:
        return self.dolphin_user_dir / "Config" / "GBA.ini"

    @property
    def gba_saves_dir(self) -> Path:
        return self.dolphin_user_dir / "GBA" / "Saves"

    @property
    def dolphin_ruby_sav(self) -> Path:
        return self.gba_saves_dir / RUBY_SAV_NAME

    @property
    def dolphin_ruby_sav_port2(self) -> Path:
        return self.gba_saves_dir / RUBY_SAV_PORT2_NAME

    def missing(self) -> list[tuple[str, Path]]:
        required = (
            ("Channel ISO", self.channel_iso),
            ("Ruby GBA ROM", self.ruby_gba),
            ("Ruby save (original)", self.ruby_sav),
            ("GBA BIOS", self.gba_bios),
            ("Dolphin binary", self.dolphin_binary),
        )
        missing: list[tuple[str, Path]] = []
        for label, path in required:
            if not path.is_file():
                missing.append((label, path))
        return missing
