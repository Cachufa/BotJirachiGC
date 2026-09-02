"""Keep one Dolphin process: boot Channel with Port 2 empty; GBA later without relaunch."""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

from botjirachi.inputs import InputError, left_click_at, right_click_at, tap_key
from botjirachi.paths import HuntPaths
from botjirachi.restore import restore_ruby_save

SIDEVICE_NONE = 0
SIDEVICE_GC_CONTROLLER = 6
SIDEVICE_GBA_INTEGRATED = 13
DEFAULT_RESTART_EVERY = 50

_MENU_OPTIONS = ("Opciones", "Options")
_MENU_EMULATION = ("Emulación", "Emulation")
_ITEM_CONTROLLERS = ("Ajustes de mandos", "Controller Settings")
_ITEM_STOP = ("Detener", "Stop")
_ITEM_PLAY = ("Jugar", "Play")
_ITEM_RESET = ("Reiniciar", "Reset")
_TOOLBAR_CONTROLLERS = ("Mandos", "Controllers")
_CLOSE = ("Cerrar", "Close")
_GC_GROUP = ("Mandos de GameCube", "GameCube Controllers")
_NONE_LABELS = ("Ninguno", "None")
# Qt GBA context menu is not in the macOS Accessibility tree. After a
# right-click, drive it with Down/Return. Separators are skipped; disabled
# items (e.g. Scan e-Reader on Ruby) still count. Order in GBAWidget.cpp:
# Connected, Load ROM, Unload ROM, Scan e-Reader, Reset, …
_GBA_MENU_LOAD_ROM_DOWNS = 2
_GBA_MENU_RESET_DOWNS = 5


class DolphinError(Exception):
    """Dolphin is missing, dead, or macOS Accessibility could not drive its UI."""


# macOS virtual key codes (ANSI). Used at System Events level, not inside
# `tell process` — nested key down is ignored and only focus happens.
_AS_KEY_CODES = {
    "a": 0,
    "s": 1,
    "d": 2,
    "f": 3,
    "h": 4,
    "g": 5,
    "z": 6,
    "x": 7,
    "c": 8,
    "v": 9,
    "b": 11,
    "q": 12,
    "w": 13,
    "e": 14,
    "r": 15,
    "y": 16,
    "t": 17,
    "1": 18,
    "2": 19,
    "3": 20,
    "4": 21,
    "6": 22,
    "5": 23,
    "9": 25,
    "7": 26,
    "8": 28,
    "0": 29,
    "o": 31,
    "u": 32,
    "[": 33,
    "i": 34,
    "p": 35,
    "enter": 36,
    "return": 36,
    "l": 37,
    "j": 38,
    "k": 40,
    "n": 45,
    "m": 46,
    "tab": 48,
    "space": 49,
    "backspace": 51,
    "esc": 53,
    "shift": 56,
    "ctrl": 59,
    "up": 126,
    "down": 125,
    "left": 123,
    "right": 124,
}


def _applescript_key(key: str, hold_s: float) -> str:
    """HID tap at System Events (must not be nested in `tell process`)."""
    hold = max(float(hold_s), 0.12)
    lookup = key.lower() if key.isalpha() else key
    code = _AS_KEY_CODES.get(lookup)
    if code is None:
        raise DolphinError(f"Cannot send key {key!r} to Dolphin")
    return (
        f"key down (key code {code})\n"
        f"        delay {hold:.3f}\n"
        f"        key up (key code {code})"
    )


def _applescript(source: str) -> str:
    result = subprocess.run(
        ["osascript"],
        input=source,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "osascript failed").strip()
        if "no se permite" in err.lower() or "not allowed" in err.lower():
            raise DolphinError(
                "Grant Accessibility permission to Terminal (or Python) "
                "so the bot can drive Dolphin menus."
            )
        raise DolphinError(err)
    return result.stdout.strip()


def _as_string_list(values: tuple[str, ...]) -> str:
    inner = ", ".join('"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"' for v in values)
    return "{" + inner + "}"


def dolphin_pids() -> list[int]:
    result = subprocess.run(
        ["pgrep", "-x", "Dolphin"],
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise DolphinError(f"pgrep failed: {result.stderr.strip()}")
    return [int(line) for line in result.stdout.split() if line.strip()]


def is_main_window(title: str) -> bool:
    return title.startswith("Dolphin") and " | " not in title


def is_channel_window(title: str) -> bool:
    lower = title.lower()
    return "pokemon channel" in lower or "gpap01" in lower


def is_gba_window(title: str) -> bool:
    return title.upper().startswith("GBA")


def is_gba_port2_window(title: str) -> bool:
    return title.upper().startswith("GBA2")


def gba_rom_name(title: str) -> str | None:
    """Game title from a GBA window, or None if no ROM is loaded."""
    if not is_gba_window(title):
        return None
    parts = [p.strip() for p in title.split("|")]
    if len(parts) < 3:
        return None
    game = parts[1]
    lower = game.lower()
    if lower.startswith("volume") or lower in {"muted", "silenciado"}:
        return None
    return game


def delete_ini_key(path: Path, section: str, key: str) -> None:
    """Remove one key from a Dolphin/Qt ini if it exists."""
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    in_section = False
    out: list[str] = []
    removed = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == f"[{section}]"
            out.append(line)
            continue
        if in_section and stripped.split("=", 1)[0].strip() == key:
            removed = True
            continue
        out.append(line)
    if removed:
        path.write_text(newline.join(out) + newline, encoding="utf-8")


def _label_is_gba_integrated(name: str) -> bool:
    lower = name.lower()
    return "gba" in lower and (
        "integrad" in lower or "emulat" in lower or "integrated" in lower
    )


def _label_is_none(name: str) -> bool:
    return name.strip() in _NONE_LABELS or name.strip().lower() in {"none", "ninguno"}


def set_ini_key(path: Path, section: str, key: str, value: str) -> None:
    """Change one key in a Dolphin ini without rewriting unrelated keys."""
    if not path.is_file():
        raise DolphinError(f"Dolphin config is missing: {path}")
    text = path.read_text(encoding="utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    in_section = False
    found_section = False
    replaced = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section and not replaced:
                out.append(f"{key} = {value}")
                replaced = True
            in_section = stripped == f"[{section}]"
            found_section = found_section or in_section
        elif in_section and stripped.split("=", 1)[0].strip() == key:
            out.append(f"{key} = {value}")
            replaced = True
            continue
        out.append(line)
    if in_section and not replaced:
        out.append(f"{key} = {value}")
        replaced = True
    if not found_section:
        if out and out[-1] != "":
            out.append("")
        out.append(f"[{section}]")
        out.append(f"{key} = {value}")
        replaced = True
    if not replaced:
        raise DolphinError(f"Could not set [{section}] {key} in {path}")
    path.write_text(newline.join(out) + newline, encoding="utf-8")


class DolphinSession:
    def __init__(
        self,
        paths: HuntPaths,
        *,
        restart_every: int = DEFAULT_RESTART_EVERY,
    ) -> None:
        self.paths = paths
        self.restart_every = restart_every
        self.process: subprocess.Popen[bytes] | None = None
        self.attempts_on_process = 0
        self._background_input_on = False

    def is_running(self) -> bool:
        if self.process is not None and self.process.poll() is None:
            return True
        return bool(dolphin_pids())

    def window_titles(self) -> list[str]:
        if not dolphin_pids():
            return []
        raw = _applescript(
            """
            tell application "System Events"
              if not (exists process "Dolphin") then return ""
              tell process "Dolphin"
                set out to ""
                repeat with w in windows
                  try
                    set nm to name of w as text
                    if nm is not "" then set out to out & nm & linefeed
                  end try
                end repeat
                return out
              end tell
            end tell
            """
        )
        return [line for line in raw.splitlines() if line.strip()]

    def has_gba_window(self) -> bool:
        return any(is_gba_window(t) for t in self.window_titles())

    def has_channel_window(self) -> bool:
        return any(is_channel_window(t) for t in self.window_titles())

    def gba_rom_loaded(self) -> bool:
        return any(gba_rom_name(t) for t in self.window_titles())

    def window_frames(self) -> list[tuple[str, int, int, int, int]]:
        """(title, x, y, width, height) for named Dolphin windows."""
        if not dolphin_pids():
            return []
        raw = _applescript(
            """
            tell application "System Events"
              if not (exists process "Dolphin") then return ""
              tell process "Dolphin"
                set out to ""
                repeat with w in windows
                  try
                    set nm to name of w as text
                    if nm is not "" then
                      set pos to position of w
                      set sz to size of w
                      set out to out & nm & tab & (item 1 of pos as text)
                      set out to out & tab & (item 2 of pos as text)
                      set out to out & tab & (item 1 of sz as text)
                      set out to out & tab & (item 2 of sz as text) & linefeed
                    end if
                  end try
                end repeat
                return out
              end tell
            end tell
            """
        )
        frames: list[tuple[str, int, int, int, int]] = []
        for line in raw.splitlines():
            parts = line.split("\t")
            if len(parts) != 5:
                continue
            title, xs, ys, ws, hs = parts
            try:
                frames.append(
                    (
                        title,
                        int(float(xs)),
                        int(float(ys)),
                        int(float(ws)),
                        int(float(hs)),
                    )
                )
            except ValueError:
                continue
        return frames

    def focus_channel_window(self) -> str:
        return self._focus_matching(is_channel_window, "Channel")

    def focus_gba_window(self) -> str:
        return self._focus_matching(is_gba_port2_window, "GBA2", fallback=is_gba_window)

    def tap_key_on_channel(
        self,
        key: str,
        hold_s: float = 0.15,
        times: int = 1,
        between_s: float | None = None,
    ) -> None:
        """Focus Channel and send HID keys while osascript keeps Dolphin frontmost."""
        self._dismiss_settings_windows()
        self._tap_key_on_matching(
            is_channel_window, "Channel", key, hold_s, times=times, between_s=between_s
        )

    def tap_key_on_gba(self, key: str, hold_s: float = 0.15, times: int = 1) -> None:
        self._dismiss_settings_windows()
        self._ensure_background_input()
        self._uncover_gba_window()
        self._tap_key_on_matching(
            is_gba_port2_window, "GBA2", key, hold_s, fallback=is_gba_window, times=times
        )

    def hold_keys_on_channel(self, keys: list[str], hold_s: float = 0.45) -> None:
        """Hold Channel pad keys (analog stick for the title cursor)."""
        self._dismiss_settings_windows()
        self._hold_keys_on_matching(is_channel_window, "Channel", keys, hold_s)

    def hold_keys_on_gba(self, keys: list[str], hold_s: float = 0.45) -> None:
        """Hold several GBA keys at once (e.g. Ruby A+B+Select+Start)."""
        self._dismiss_settings_windows()
        self._ensure_background_input()
        self._uncover_gba_window()
        self._hold_keys_on_matching(
            is_gba_port2_window, "GBA2", keys, hold_s, fallback=is_gba_window
        )

    def load_ruby_rom(self, timeout_s: float = 20) -> None:
        """Set Rom2, turn on GBA port 2, Reset; Load ROM file dialog as fallback."""
        self._write_rom2()
        if not self.has_gba_window():
            self.set_port2_gba()
        else:
            self._wait_gba(present=True, timeout_s=8)
        if not self.gba_rom_loaded():
            self._load_rom_via_context_menu()
        self._wait_gba_rom(timeout_s)
        self.reset_gba()
        self._wait_gba_rom(timeout_s)

    def reset_gba(self) -> None:
        """Right-click GBA window → Reset (soft-reset the loaded ROM)."""
        self._gba_context_menu(_GBA_MENU_RESET_DOWNS)
        time.sleep(0.4)
        if not self.gba_rom_loaded():
            raise DolphinError(
                "GBA Reset unloaded the ROM (wrong context-menu item). "
                f"Windows: {self.window_titles()}"
            )

    def start(self) -> None:
        """Launch Dolphin and boot Channel with Port 2 empty."""
        if self.is_running():
            raise DolphinError(
                "Dolphin is already running; refuse to start a second process. "
                "Use ensure_channel_booted() to reuse it."
            )
        self._write_port2_ini(SIDEVICE_NONE)
        # Rom2 path has spaces; --config=Dolphin.GBA.Rom2=… splits on them.
        # Write Dolphin.ini instead so GBA auto-loads when Port 2 is enabled.
        self._write_rom2()
        # GBA keys only reach Ruby if Background Input is on (GBA is not the
        # Channel Metal window). Controllers → Common → Funcionar en segundo plano.
        set_ini_key(self.paths.dolphin_ini, "Input", "BackgroundInput", "True")
        # Saved GBA window flags/geometry can place the window off-screen.
        self._reset_gba_widget_geometry()
        # Do not pass SIDevice via --config: that layer wins over the Controllers
        # UI, so Port 2 cannot switch to GBA later and Channel goes black.
        cmd = [
            str(self.paths.dolphin_binary),
            "--exec",
            str(self.paths.channel_iso),
            "--config=Dolphin.Interface.ConfirmStop=False",
        ]
        self.process = subprocess.Popen(
            cmd,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.attempts_on_process = 0

    def kill(self) -> None:
        """Hard restart recovery. Does not restore saves."""
        pids = set(dolphin_pids())
        if self.process is not None and self.process.poll() is None:
            pids.add(self.process.pid)
        for pid in pids:
            subprocess.run(["kill", str(pid)], check=False)
        deadline = time.time() + 5
        while time.time() < deadline and dolphin_pids():
            time.sleep(0.1)
        still = dolphin_pids()
        for pid in still:
            subprocess.run(["kill", "-9", str(pid)], check=False)
        self.process = None
        self.attempts_on_process = 0

    def set_port2_none(self) -> None:
        self._set_port2("none")
        self._wait_gba(present=False, timeout_s=8)

    def set_port2_gba(self) -> None:
        """Enable GBA (Integrated) on Port 2 without relaunching Dolphin."""
        try:
            self._set_port2("gba")
            self._wait_gba(present=True, timeout_s=12)
        except DolphinError as exc:
            self._unstick_after_gba_fail()
            raise DolphinError(
                f"{exc} Port 2 was set back to None so Channel does not stay black."
            ) from exc

    def stop_emulation(self) -> None:
        self._focus_main_window()
        if not self._click_toolbar(_ITEM_STOP):
            self._click_menu(_MENU_EMULATION, _ITEM_STOP)
        deadline = time.time() + 8
        while time.time() < deadline:
            if not self.has_channel_window() and not self.has_gba_window():
                return
            time.sleep(0.2)
        raise DolphinError("Timed out waiting for emulation to stop")

    def play(self) -> None:
        self._focus_main_window()
        if not self._click_toolbar(_ITEM_PLAY):
            self._click_menu(_MENU_EMULATION, _ITEM_PLAY)

    def reset_emulation(self) -> None:
        """Soft-reset Channel in the same process (title screen)."""
        self._focus_main_window()
        self._click_menu(_MENU_EMULATION, _ITEM_RESET)

    def wait_channel_without_gba(self, timeout_s: float = 30) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            titles = self.window_titles()
            gba = any(is_gba_window(t) for t in titles)
            channel = any(is_channel_window(t) for t in titles)
            if gba:
                raise DolphinError(
                    "GBA window opened with Channel; Port 2 is not empty: "
                    + ", ".join(titles)
                )
            if channel:
                return
            if not self.is_running():
                raise DolphinError("Dolphin exited while waiting for Channel")
            time.sleep(0.25)
        raise DolphinError(
            f"Timed out waiting for Channel window (no GBA). Windows: {self.window_titles()}"
        )

    def ensure_channel_booted(self) -> None:
        """Start or reuse Dolphin so Channel is running with Port 2 empty."""
        if not self.is_running():
            self.start()
            self.wait_channel_without_gba()
            return
        self._dismiss_file_dialogs()
        if self._has_file_dialog() or not self._menu_bar_ready():
            self.kill()
            self.start()
            self.wait_channel_without_gba()
            return
        if self.has_gba_window():
            self.set_port2_none()
        if self.has_channel_window():
            if self.has_gba_window():
                raise DolphinError("GBA window still present after setting Port 2 to None")
            # Do not Reset a healthy Channel. Reset during a half-applied GBA
            # port is what left the ISO on a black screen.
            return
        self.kill()
        self.start()
        self.wait_channel_without_gba()

    def prepare_attempt(self) -> None:
        """Port 2 None, restore Ruby save, stop emulation, boot Channel again."""
        self.attempts_on_process += 1
        if (
            self.restart_every > 0
            and self.attempts_on_process >= self.restart_every
        ) or not self.is_running():
            self.kill()
            restore_ruby_save(self.paths)
            self.start()
            self.wait_channel_without_gba()
            self.attempts_on_process = 1
            return
        if self.has_gba_window() or self.has_channel_window():
            try:
                self.set_port2_none()
            except DolphinError:
                self.kill()
                restore_ruby_save(self.paths)
                self.start()
                self.wait_channel_without_gba()
                self.attempts_on_process = 1
                return
        restore_ruby_save(self.paths)
        if self.has_channel_window():
            # Game list is empty when booted via --exec, so Stop+Play opens Open…
            self.reset_emulation()
            time.sleep(1.5)
            self.wait_channel_without_gba()
            return
        self.kill()
        restore_ruby_save(self.paths)
        self.start()
        self.wait_channel_without_gba()
        self.attempts_on_process = 1

    def _write_port2_ini(self, sidevice: int) -> None:
        set_ini_key(self.paths.dolphin_ini, "Core", "SIDevice0", str(SIDEVICE_GC_CONTROLLER))
        set_ini_key(self.paths.dolphin_ini, "Core", "SIDevice1", str(sidevice))

    def _write_rom2(self) -> None:
        set_ini_key(self.paths.dolphin_ini, "GBA", "Rom2", str(self.paths.ruby_gba))

    def _reset_gba_widget_geometry(self) -> None:
        qt_ini = self.paths.dolphin_user_dir / "Config" / "Qt.ini"
        for key in ("flags1", "flags2", "geometry1", "geometry2"):
            delete_ini_key(qt_ini, "gbawidget", key)

    def _focus_matching(
        self,
        matcher,
        label: str,
        fallback=None,
    ) -> str:
        frames = self.window_frames()
        chosen = next((f for f in frames if matcher(f[0])), None)
        if chosen is None and fallback is not None:
            chosen = next((f for f in frames if fallback(f[0])), None)
        if chosen is None:
            titles = [f[0] for f in frames]
            raise DolphinError(f"{label} window not found. Windows: {titles}")
        title, x, y, w, h = chosen
        self._raise_and_click(title, x, y, w, h)
        return title

    def _ensure_background_input(self) -> None:
        """Turn on Controllers → Common → Background Input if it is off."""
        if self._background_input_on:
            return
        set_ini_key(self.paths.dolphin_ini, "Input", "BackgroundInput", "True")
        self._focus_main_window()
        if not self._click_toolbar(_TOOLBAR_CONTROLLERS):
            self._click_menu(_MENU_OPTIONS, _ITEM_CONTROLLERS)
        time.sleep(0.55)
        raw = _applescript(
            """
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                repeat with w in windows
                  set nm to ""
                  try
                    set nm to name of w as text
                  end try
                  if nm is "Ajustes" or nm is "Settings" then
                    set box to missing value
                    try
                      set box to checkbox "Funcionar en segundo plano" of group "Común" of group 1 of w
                    end try
                    if box is missing value then
                      try
                        set box to checkbox "Background Input" of group "Common" of group 1 of w
                      end try
                    end if
                    if box is missing value then return "missing"
                    set v to value of box as integer
                    if v is 0 then click box
                    return "on"
                  end if
                end repeat
                return "no-window"
              end tell
            end tell
            """
        )
        self._dismiss_settings_windows()
        if raw.strip() not in {"on"}:
            raise DolphinError(
                "Could not enable Background Input (GBA keys need it). "
                f"result={raw!r} windows={self.window_titles()}"
            )
        self._background_input_on = True

    def _uncover_gba_window(self) -> None:
        """Park GBA2 left of Channel so HID clicks hit Ruby, not the GC window."""
        frames = self.window_frames()
        gba = next((f for f in frames if is_gba_port2_window(f[0])), None)
        if gba is None:
            gba = next((f for f in frames if is_gba_window(f[0])), None)
        if gba is None:
            return
        title, x, y, w, h = gba
        channel = next((f for f in frames if is_channel_window(f[0])), None)
        dest_x, dest_y = 24, 80
        if channel is not None:
            # Sit fully to the left of Channel when there is room.
            ch_x = channel[1]
            if ch_x > w + 40:
                dest_x = 24
            else:
                dest_x = max(ch_x - w - 24, 24)
        if abs(x - dest_x) < 12 and abs(y - dest_y) < 12:
            return
        escaped = title.replace("\\", "\\\\").replace('"', '\\"')
        _applescript(
            f"""
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                repeat with w in windows
                  try
                    if (name of w as text) is "{escaped}" then
                      set position of w to {{{dest_x}, {dest_y}}}
                      set index of w to 1
                      perform action "AXRaise" of w
                      exit repeat
                    end if
                  end try
                end repeat
              end tell
            end tell
            """
        )
        time.sleep(0.25)

    def _tap_key_on_matching(
        self,
        matcher,
        label: str,
        key: str,
        hold_s: float,
        fallback=None,
        times: int = 1,
        between_s: float | None = None,
    ) -> None:
        frames = self.window_frames()
        chosen = next((f for f in frames if matcher(f[0])), None)
        if chosen is None and fallback is not None:
            chosen = next((f for f in frames if fallback(f[0])), None)
        if chosen is None:
            titles = [f[0] for f in frames]
            raise DolphinError(f"{label} window not found. Windows: {titles}")
        title, x, y, w, h = chosen
        escaped = title.replace("\\", "\\\\").replace('"', '\\"')
        # Content of the window (GBA is 240x160 plus chrome; Channel overlaps it).
        cx = x + max(w // 2, 8)
        cy = y + max(28 + (h - 28) // 2, 40)
        hold = max(float(hold_s), 0.12)
        taps = max(int(times), 1)
        between = 0.16 if between_s is None else max(float(between_s), 0.05)
        hid_len = 0.72 + taps * (hold + between)
        as_delay = max(1.6, hid_len + 0.35)
        # Accessibility click does not make the Qt GBA widget the key window.
        # Keep Dolphin frontmost with a blocking osascript delay; HID click+keys
        # fire meanwhile so Terminal cannot steal them.
        hid_error: list[BaseException] = []

        def send_hid() -> None:
            try:
                time.sleep(0.5)
                left_click_at(cx, cy)
                time.sleep(0.22)
                for _ in range(taps):
                    tap_key(key, hold_s=hold)
                    time.sleep(between)
            except BaseException as exc:
                hid_error.append(exc)

        worker = threading.Thread(target=send_hid, daemon=True)
        worker.start()
        _applescript(
            f"""
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                delay 0.1
                repeat with w in windows
                  try
                    if (name of w as text) is "{escaped}" then
                      perform action "AXRaise" of w
                      set index of w to 1
                      exit repeat
                    end if
                  end try
                end repeat
                delay 0.2
              end tell
              delay {as_delay:.3f}
            end tell
            """
        )
        worker.join(timeout=as_delay + 2.0)
        self._raise_hid_error(hid_error)

    def _hold_keys_on_matching(
        self,
        matcher,
        label: str,
        keys: list[str],
        hold_s: float,
        fallback=None,
    ) -> None:
        from botjirachi.inputs import press_key, release_key

        frames = self.window_frames()
        chosen = next((f for f in frames if matcher(f[0])), None)
        if chosen is None and fallback is not None:
            chosen = next((f for f in frames if fallback(f[0])), None)
        if chosen is None:
            titles = [f[0] for f in frames]
            raise DolphinError(f"{label} window not found. Windows: {titles}")
        title, x, y, w, h = chosen
        escaped = title.replace("\\", "\\\\").replace('"', '\\"')
        cx = x + max(w // 2, 8)
        cy = y + max(28 + (h - 28) // 2, 40)
        hold = max(float(hold_s), 0.05)
        key_list = list(keys)
        hid_lead = 0.72
        as_delay = max(1.6, hid_lead + hold + 0.4)

        hid_error: list[BaseException] = []

        def send_hid() -> None:
            try:
                time.sleep(0.5)
                left_click_at(cx, cy)
                time.sleep(0.22)
                for key in key_list:
                    press_key(key)
                time.sleep(hold)
                for key in reversed(key_list):
                    release_key(key)
            except BaseException as exc:
                hid_error.append(exc)

        worker = threading.Thread(target=send_hid, daemon=True)
        worker.start()
        _applescript(
            f"""
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                delay 0.1
                repeat with w in windows
                  try
                    if (name of w as text) is "{escaped}" then
                      perform action "AXRaise" of w
                      set index of w to 1
                      exit repeat
                    end if
                  end try
                end repeat
                delay 0.2
              end tell
              delay {as_delay:.3f}
            end tell
            """
        )
        worker.join(timeout=as_delay + 2.0)
        self._raise_hid_error(hid_error)

    def _raise_hid_error(self, hid_error: list[BaseException]) -> None:
        if not hid_error:
            return
        exc = hid_error[0]
        raise DolphinError(str(exc)) from exc

    def _raise_and_click(self, title: str, x: int, y: int, w: int, h: int) -> None:
        escaped = title.replace("\\", "\\\\").replace('"', '\\"')
        cx = x + max(w // 2, 8)
        cy = y + max(h // 2, 12)
        _applescript(
            f"""
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                delay 0.08
                repeat with w in windows
                  try
                    if (name of w as text) is "{escaped}" then
                      perform action "AXRaise" of w
                      exit repeat
                    end if
                  end try
                end repeat
                delay 0.08
                click at {{{cx}, {cy}}}
              end tell
            end tell
            """
        )
        time.sleep(0.12)

    def _gba_frame(self) -> tuple[str, int, int, int, int]:
        frames = self.window_frames()
        chosen = next((f for f in frames if is_gba_port2_window(f[0])), None)
        if chosen is None:
            chosen = next((f for f in frames if is_gba_window(f[0])), None)
        if chosen is None:
            raise DolphinError(
                f"GBA window not found. Windows: {[f[0] for f in frames]}"
            )
        return chosen

    def _gba_context_menu(self, downs: int) -> None:
        title, x, y, w, h = self._gba_frame()
        self._raise_and_click(title, x, y, w, h)
        try:
            right_click_at(x + max(w // 2, 8), y + max(h // 2, 12))
        except InputError as exc:
            raise DolphinError(str(exc)) from exc
        down_block = "\n                ".join(
            ["key code 125\n                delay 0.05"] * max(int(downs), 0)
        )
        _applescript(
            f"""
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                delay 0.25
                {down_block}
                key code 36
              end tell
            end tell
            """
        )
        time.sleep(0.25)

    def _load_rom_via_context_menu(self) -> None:
        self._gba_context_menu(_GBA_MENU_LOAD_ROM_DOWNS)
        self._wait_file_dialog(timeout_s=6)
        self._confirm_open_dialog(self.paths.ruby_gba)

    def _wait_file_dialog(self, timeout_s: float) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self._has_file_dialog():
                return
            time.sleep(0.15)
        raise DolphinError(
            "Timed out waiting for the GBA Load ROM file dialog. "
            f"Windows: {self.window_titles()}"
        )

    def _confirm_open_dialog(self, path: Path) -> None:
        posix = str(path)
        escaped = posix.replace("\\", "\\\\").replace('"', '\\"')
        _applescript(
            f"""
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                delay 0.25
                keystroke "g" using {{command down, shift down}}
                delay 0.4
                keystroke "{escaped}"
                delay 0.15
                key code 36
                delay 0.55
                key code 36
              end tell
            end tell
            """
        )
        time.sleep(0.4)

    def _wait_gba_rom(self, timeout_s: float) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.gba_rom_loaded():
                return
            if not self.is_running():
                raise DolphinError("Dolphin exited while waiting for Ruby ROM")
            time.sleep(0.25)
        raise DolphinError(
            "Timed out waiting for Ruby ROM in the GBA window. "
            f"Windows: {self.window_titles()}"
        )

    def _wait_gba(self, *, present: bool, timeout_s: float) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.has_gba_window() is present:
                return
            time.sleep(0.2)
        state = "appear" if present else "close"
        raise DolphinError(
            f"Timed out waiting for GBA window to {state}. Windows: {self.window_titles()}"
        )

    def _has_file_dialog(self) -> bool:
        for title in self.window_titles():
            lower = title.lower()
            if is_channel_window(title) or is_gba_window(title) or is_main_window(title):
                continue
            if "seleccionar" in lower or lower in {"open", "open file"} or lower.startswith("open "):
                return True
        return False

    def _menu_bar_ready(self) -> bool:
        options = _as_string_list(_MENU_OPTIONS)
        emulation = _as_string_list(_MENU_EMULATION)
        try:
            raw = _applescript(
                f"""
                tell application "System Events"
                  if not (exists process "Dolphin") then return "no"
                  tell process "Dolphin"
                    set frontmost to true
                    delay 0.15
                    repeat with w in windows
                      try
                        set nm to name of w as text
                        if nm starts with "Dolphin" and nm does not contain " | " then
                          perform action "AXRaise" of w
                          set pos to position of w
                          set sz to size of w
                          -- Right side of the title bar: left-side clicks hit Open.
                          set x to (item 1 of pos) + (item 1 of sz) - 40
                          set y to (item 2 of pos) + 6
                          click at {{x, y}}
                        end if
                      end try
                    end repeat
                    delay 0.2
                    repeat with mbi in menu bar items of menu bar 1
                      set n to ""
                      try
                        set n to name of mbi as text
                      end try
                      if n is in {options} or n is in {emulation} then return "yes"
                    end repeat
                    return "no"
                  end tell
                end tell
                """
            )
        except DolphinError:
            return False
        return raw.strip() == "yes"

    def _dismiss_file_dialogs(self) -> None:
        if not self._has_file_dialog():
            return
        _applescript(
            """
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                key code 53
                delay 0.2
                keystroke "." using command down
              end tell
            end tell
            """
        )
        time.sleep(0.3)

    def _focus_main_window(self) -> None:
        if not self._menu_bar_ready():
            raise DolphinError(
                "Dolphin menu bar not available. Focus the main Dolphin window "
                "(not the game render window)."
            )

    def _click_toolbar(self, button_names: tuple[str, ...]) -> bool:
        names = _as_string_list(button_names)
        raw = _applescript(
            f"""
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                delay 0.1
                repeat with w in windows
                  try
                    set nm to name of w as text
                    if nm starts with "Dolphin" and nm does not contain " | " then
                      repeat with b in buttons of w
                        set bn to ""
                        try
                          set bn to name of b as text
                        end try
                        if bn is in {names} then
                          click b
                          return "yes"
                        end if
                      end repeat
                    end if
                  end try
                end repeat
                return "no"
              end tell
            end tell
            """
        )
        return raw.strip() == "yes"

    def _click_menu(self, menu_names: tuple[str, ...], item_names: tuple[str, ...]) -> None:
        menus = _as_string_list(menu_names)
        items = _as_string_list(item_names)
        _applescript(
            f"""
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                delay 0.15
                set bar to menu bar 1
                set clicked to false
                repeat with mbi in menu bar items of bar
                  set mname to ""
                  try
                    set mname to name of mbi as text
                  end try
                  if mname is in {menus} then
                    repeat with mi in menu items of menu 1 of mbi
                      set iname to ""
                      try
                        set iname to name of mi as text
                      end try
                      if iname is in {items} then
                        click mi
                        set clicked to true
                        exit repeat
                      end if
                    end repeat
                  end if
                  if clicked then exit repeat
                end repeat
                if clicked is false then error "Menu item not found"
              end tell
            end tell
            """
        )

    def _set_port2(self, kind: str) -> None:
        if not self.is_running():
            raise DolphinError("Dolphin is not running")
        # Do not write SIDevice to the ini first: the combo then already shows
        # GBA without firing ChangeDevice, Channel goes black, no GBA window.
        # Popup rows are AXStaticText; AXPress is a no-op. Return activates
        # Cerrar. Click the row at its coordinates, then Cerrar by name.
        self._dismiss_settings_windows()
        self._focus_main_window()
        if not self._click_toolbar(_TOOLBAR_CONTROLLERS):
            self._click_menu(_MENU_OPTIONS, _ITEM_CONTROLLERS)
        time.sleep(0.6)
        shown = self._port2_combo_name()
        if kind == "gba" and _label_is_gba_integrated(shown) and self.has_gba_window():
            self._close_controller_settings()
            self._write_port2_ini(SIDEVICE_GBA_INTEGRATED)
            return
        if kind == "none" and _label_is_none(shown) and not self.has_gba_window():
            self._close_controller_settings()
            self._write_port2_ini(SIDEVICE_NONE)
            return
        if kind == "gba" and _label_is_gba_integrated(shown):
            self._click_port2_option("none")
            time.sleep(0.35)
        elif kind == "none" and _label_is_none(shown):
            self._click_port2_option("gba")
            time.sleep(0.35)
        after = self._click_port2_option(kind)
        if kind == "gba" and not _label_is_gba_integrated(after):
            raise DolphinError(
                f"Port 2 combo did not switch to GBA (Integrated); it is {after!r}"
            )
        if kind == "none" and not _label_is_none(after):
            raise DolphinError(
                f"Port 2 combo did not switch to None; it is {after!r}"
            )
        self._close_controller_settings()
        self._write_port2_ini(
            SIDEVICE_NONE if kind == "none" else SIDEVICE_GBA_INTEGRATED
        )
        time.sleep(0.4)

    def _port2_combo_name(self) -> str:
        gc_groups = _as_string_list(_GC_GROUP)
        return _applescript(
            f"""
            tell application "System Events"
              tell process "Dolphin"
                set gcNames to {gc_groups}
                repeat with cand in windows
                  repeat with i from 1 to count of gcNames
                    set gname to item i of gcNames as text
                    try
                      if exists group gname of group 1 of cand then
                        set gcGroup to group gname of group 1 of cand
                        return name of (item 2 of combo boxes of gcGroup) as text
                      end if
                    end try
                  end repeat
                end repeat
                return ""
              end tell
            end tell
            """
        )

    def _click_port2_option(self, kind: str) -> str:
        """Open Port 2 combo and pynput-click the matching row.

        osascript click/AXPress does not commit Qt popup rows. Return activates
        Cerrar. A real left-click at the row coordinates does commit.
        """
        gc_groups = _as_string_list(_GC_GROUP)
        none_labels = _as_string_list(_NONE_LABELS)
        raw = _applescript(
            f"""
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                delay 0.08
                set gcNames to {gc_groups}
                set gcGroup to missing value
                repeat with cand in windows
                  repeat with i from 1 to count of gcNames
                    set gname to item i of gcNames as text
                    try
                      if exists group gname of group 1 of cand then
                        set gcGroup to group gname of group 1 of cand
                        exit repeat
                      end if
                    end try
                  end repeat
                  if gcGroup is not missing value then exit repeat
                end repeat
                if gcGroup is missing value then error "GameCube controller group not found"
                click (item 2 of combo boxes of gcGroup)
                delay 0.6
                set titles to {{}}
                repeat with ww in windows
                  set nm to ""
                  try
                    set nm to name of ww as text
                  end try
                  if nm is "" then
                    try
                      repeat with e in UI elements of list 1 of ww
                        set t to ""
                        try
                          set t to title of e as text
                        end try
                        if t is not "" then set end of titles to t
                        set match to false
                        if "{kind}" is "gba" then
                          if t contains "GBA" and (t contains "integrad" or t contains "emulat" or t contains "Integrat") then set match to true
                        else
                          if t is in {none_labels} then set match to true
                        end if
                        if match then
                          set p to position of e
                          set ss to size of e
                          set cx to ((item 1 of p) + (item 1 of ss) / 2) as integer
                          set cy to ((item 2 of p) + (item 2 of ss) / 2) as integer
                          return (cx as text) & tab & (cy as text) & tab & t
                        end if
                      end repeat
                    end try
                  end if
                end repeat
                if (count of titles) is 0 then error "Port 2 popup did not open"
                error "Port 2 item not found (" & "{kind}" & "): " & titles
              end tell
            end tell
            """
        )
        parts = raw.split("\t")
        if len(parts) != 3:
            raise DolphinError(f"Port 2 popup click target malformed: {raw!r}")
        try:
            left_click_at(int(parts[0]), int(parts[1]))
        except InputError as exc:
            raise DolphinError(str(exc)) from exc
        time.sleep(0.45)
        return self._port2_combo_name()

    def _close_controller_settings(self) -> None:
        self._dismiss_settings_windows()

    def _unstick_after_gba_fail(self) -> None:
        """Half-applied GBA blacks Channel. Revert Port 2 to None; do not kill Dolphin."""
        try:
            self._dismiss_settings_windows()
        except DolphinError:
            pass
        try:
            self._set_port2("none")
        except DolphinError:
            self._write_port2_ini(SIDEVICE_NONE)
        try:
            self._dismiss_settings_windows()
        except DolphinError:
            pass

    def _dismiss_settings_windows(self) -> None:
        close_labels = _as_string_list(_CLOSE)
        for _ in range(4):
            titles = [t.lower() for t in self.window_titles()]
            leftover = any(
                "ajustes" in t or "controller" in t or t in {"settings"}
                for t in titles
            )
            if not leftover:
                return
            _applescript(
                f"""
                tell application "System Events"
                  tell process "Dolphin"
                    set frontmost to true
                    set closeNames to {close_labels}
                    set closed to false
                    repeat with w in windows
                      set nm to ""
                      try
                        set nm to name of w as text
                      end try
                      if nm is "Ajustes" or nm is "Settings" or nm contains "Controller" then
                        try
                          repeat with g in groups of w
                            repeat with i from 1 to count of closeNames
                              set bname to item i of closeNames as text
                              try
                                click button bname of g
                                set closed to true
                                exit repeat
                              end try
                            end repeat
                            if closed then exit repeat
                          end repeat
                        end try
                      end if
                      if closed then exit repeat
                    end repeat
                    if closed is false then key code 53
                  end tell
                end tell
                """
            )
            time.sleep(0.25)

