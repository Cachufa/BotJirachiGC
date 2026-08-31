"""macOS keyboard/mouse to Dolphin: mapped pads, window focus, Accessibility."""

from __future__ import annotations

import ctypes
import ctypes.util
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from botjirachi.dolphin import DolphinSession

HOLD_S = 0.08
GAP_S = 0.05
# Ruby title (verified both A's registered). Safe, not minimal; tune down later.
GBA_AFTER_RESET_S = 7.0
GBA_BETWEEN_A_S = 7.0

# GCPad1 (Channel) and GBA2 (Ruby) as in GCPadNew.ini / GBA.ini.
CHANNEL_DEFAULTS = {
    "A": "x",
    "B": "z",
    "Start": "enter",
    "X": "c",
    "Y": "s",
    "Z": "d",
    "L": "q",
    "R": "w",
    "Up": "up",
    "Down": "down",
    "Left": "left",
    "Right": "right",
}
GBA2_DEFAULTS = {
    "A": "1",
    "B": "2",
    "Start": "6",
    "Select": "5",
    "L": "3",
    "R": "4",
    "Up": "0",
    "Down": "p",
    "Left": "o",
    "Right": "[",
}

_DOLPHIN_KEY_ALIASES = {
    "return": "enter",
    "enter": "enter",
    "up arrow": "up",
    "down arrow": "down",
    "left arrow": "left",
    "right arrow": "right",
    "backspace": "backspace",
    "shift": "shift",
    "ctrl": "ctrl",
    "control": "ctrl",
}

_PAD_INI_KEYS = {
    "A": ("Buttons/A",),
    "B": ("Buttons/B",),
    "X": ("Buttons/X",),
    "Y": ("Buttons/Y",),
    "Z": ("Buttons/Z",),
    "Start": ("Buttons/Start", "Buttons/START"),
    "Select": ("Buttons/Select", "Buttons/SELECT"),
    "L": ("Buttons/L",),
    "R": ("Buttons/R",),
    "Up": ("D-Pad/Up",),
    "Down": ("D-Pad/Down",),
    "Left": ("D-Pad/Left",),
    "Right": ("D-Pad/Right",),
}


class InputError(Exception):
    """Keyboard/mouse events could not be sent, or Accessibility is missing."""


def accessibility_trusted() -> bool:
    """True if this process may drive other apps (menus, keys, mouse)."""
    lib_name = ctypes.util.find_library("ApplicationServices")
    if not lib_name:
        return False
    lib = ctypes.cdll.LoadLibrary(lib_name)
    try:
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        lib.AXIsProcessTrusted.argtypes = []
        return bool(lib.AXIsProcessTrusted())
    except AttributeError:
        return False


def require_accessibility() -> None:
    if accessibility_trusted():
        return
    raise InputError(
        "Grant Accessibility permission so the bot can send keys to Dolphin. "
        "System Settings → Privacy & Security → Accessibility → enable the "
        "app that runs this command (Terminal, iTerm, Python, or Grok)."
    )


def _keyboard():
    try:
        from pynput.keyboard import Controller, Key
    except ImportError as exc:
        raise InputError(
            "pynput is required to send keyboard events. Install it with: "
            "pip3 install pynput"
        ) from exc
    return Controller(), Key


def _mouse():
    try:
        from pynput.mouse import Button, Controller
    except ImportError as exc:
        raise InputError(
            "pynput is required to send mouse events. Install it with: "
            "pip3 install pynput"
        ) from exc
    return Controller(), Button


def parse_dolphin_key(raw: str) -> str:
    """Map a Dolphin binding (`X`, `Return`, `1`) to a PadDriver key name."""
    text = raw.strip().strip("`").strip()
    if not text:
        raise InputError(f"Empty Dolphin key binding: {raw!r}")
    alias = _DOLPHIN_KEY_ALIASES.get(text.lower())
    if alias:
        return alias
    if len(text) == 1:
        return text.lower() if text.isalpha() else text
    raise InputError(f"Unsupported Dolphin key binding: {raw!r}")


def _ini_section(path: Path, section: str) -> dict[str, str]:
    if not path.is_file():
        return {}
    current: str | None = None
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1]
            continue
        if current != section or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def pad_map_from_ini(
    path: Path,
    section: str,
    defaults: dict[str, str],
) -> dict[str, str]:
    """Read button → key names from a Dolphin pad ini, falling back to defaults."""
    data = _ini_section(path, section)
    mapped = dict(defaults)
    for button, keys in _PAD_INI_KEYS.items():
        if button not in defaults and button not in mapped:
            continue
        for ini_key in keys:
            if ini_key in data:
                mapped[button] = parse_dolphin_key(data[ini_key])
                break
    return mapped


# ANSI Mac virtual keys. pynput maps the char "1" to numpad vk 83; Dolphin
# binds `1` as the number-row key (vk 18).
_ANSI_VK = {
    "a": 0x00,
    "s": 0x01,
    "d": 0x02,
    "f": 0x03,
    "h": 0x04,
    "g": 0x05,
    "z": 0x06,
    "x": 0x07,
    "c": 0x08,
    "v": 0x09,
    "b": 0x0B,
    "q": 0x0C,
    "w": 0x0D,
    "e": 0x0E,
    "r": 0x0F,
    "y": 0x10,
    "t": 0x11,
    "1": 0x12,
    "2": 0x13,
    "3": 0x14,
    "4": 0x15,
    "6": 0x16,
    "5": 0x17,
    "9": 0x19,
    "7": 0x1A,
    "8": 0x1C,
    "0": 0x1D,
    "o": 0x1F,
    "u": 0x20,
    "[": 0x21,
    "i": 0x22,
    "p": 0x23,
    "l": 0x25,
    "j": 0x26,
    "k": 0x28,
    "n": 0x2D,
    "m": 0x2E,
}


def _pynput_key(name: str):
    _controller, Key = _keyboard()
    from pynput.keyboard import KeyCode

    special = {
        "enter": Key.enter,
        "return": Key.enter,
        "backspace": Key.backspace,
        "shift": Key.shift,
        "ctrl": Key.ctrl,
        "up": Key.up,
        "down": Key.down,
        "left": Key.left,
        "right": Key.right,
        "esc": Key.esc,
        "space": Key.space,
        "tab": Key.tab,
    }
    if name.lower() in special:
        return special[name.lower()]
    lookup = name.lower() if name.isalpha() else name
    if lookup in _ANSI_VK:
        return KeyCode.from_vk(_ANSI_VK[lookup])
    if len(name) == 1:
        return name
    raise InputError(f"Cannot send key {name!r}")


def press_key(name: str) -> None:
    require_accessibility()
    controller, _Key = _keyboard()
    controller.press(_pynput_key(name))


def release_key(name: str) -> None:
    require_accessibility()
    controller, _Key = _keyboard()
    controller.release(_pynput_key(name))


def tap_key(name: str, hold_s: float = HOLD_S) -> None:
    press_key(name)
    time.sleep(hold_s)
    release_key(name)
    time.sleep(GAP_S)


def left_click_at(x: int, y: int) -> None:
    require_accessibility()
    mouse, Button = _mouse()
    mouse.position = (int(x), int(y))
    time.sleep(0.05)
    mouse.click(Button.left, 1)


def right_click_at(x: int, y: int) -> None:
    require_accessibility()
    mouse, Button = _mouse()
    mouse.position = (int(x), int(y))
    time.sleep(0.05)
    mouse.click(Button.right, 1)


class PadDriver:
    """Focus the Channel or GBA2 window, then tap the mapped pad keys."""

    def __init__(self, session: DolphinSession) -> None:
        self.session = session
        user = session.paths.dolphin_user_dir / "Config"
        self.channel_map = pad_map_from_ini(
            user / "GCPadNew.ini", "GCPad1", CHANNEL_DEFAULTS
        )
        self.gba_map = pad_map_from_ini(
            user / "GBA.ini", "GBA2", GBA2_DEFAULTS
        )

    def tap_channel(self, button: str, hold_s: float = HOLD_S, times: int = 1) -> None:
        self.session.tap_key_on_channel(
            self._channel_key(button), hold_s=hold_s, times=times
        )

    def tap_gba(self, button: str, hold_s: float = HOLD_S, times: int = 1) -> None:
        self.session.tap_key_on_gba(self._gba_key(button), hold_s=hold_s, times=times)

    def soft_reset_gba(self) -> None:
        """Ruby/Gen 3: hold A+B+Select+Start."""
        keys = [
            self._gba_key("A"),
            self._gba_key("B"),
            self._gba_key("Select"),
            self._gba_key("Start"),
        ]
        self.session.hold_keys_on_gba(keys, hold_s=0.5)

    def hold_channel(self, button: str) -> None:
        self.session.tap_key_on_channel(self._channel_key(button), hold_s=0.2)

    def hold_gba(self, button: str) -> None:
        self.session.tap_key_on_gba(self._gba_key(button), hold_s=0.2)

    def release_channel(self, button: str) -> None:
        release_key(self._channel_key(button))

    def release_gba(self, button: str) -> None:
        release_key(self._gba_key(button))

    def _channel_key(self, button: str) -> str:
        try:
            return self.channel_map[button]
        except KeyError as exc:
            raise InputError(f"Channel pad has no button {button!r}") from exc

    def _gba_key(self, button: str) -> str:
        try:
            return self.gba_map[button]
        except KeyError as exc:
            raise InputError(f"GBA2 pad has no button {button!r}") from exc
