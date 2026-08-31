"""Keep one Dolphin process: boot Channel with Port 2 empty; GBA later without relaunch."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

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


class DolphinError(Exception):
    """Dolphin is missing, dead, or macOS Accessibility could not drive its UI."""


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

    def start(self) -> None:
        """Launch Dolphin and boot Channel with Port 2 empty."""
        if self.is_running():
            raise DolphinError(
                "Dolphin is already running; refuse to start a second process. "
                "Use ensure_channel_booted() to reuse it."
            )
        self._write_port2_ini(SIDEVICE_NONE)
        cmd = [
            str(self.paths.dolphin_binary),
            "--exec",
            str(self.paths.channel_iso),
            f"--config=Dolphin.Core.SIDevice0={SIDEVICE_GC_CONTROLLER}",
            f"--config=Dolphin.Core.SIDevice1={SIDEVICE_NONE}",
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
        self._set_port2("gba")
        self._wait_gba(present=True, timeout_s=12)

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
        self._write_port2_ini(
            SIDEVICE_NONE if kind == "none" else SIDEVICE_GBA_INTEGRATED
        )
        self._focus_main_window()
        if not self._click_toolbar(_TOOLBAR_CONTROLLERS):
            self._click_menu(_MENU_OPTIONS, _ITEM_CONTROLLERS)
        time.sleep(0.6)
        gc_groups = _as_string_list(_GC_GROUP)
        none_labels = _as_string_list(_NONE_LABELS)
        close_labels = _as_string_list(_CLOSE)
        _applescript(
            f"""
            tell application "System Events"
              tell process "Dolphin"
                set frontmost to true
                set gcNames to {gc_groups}
                set w to missing value
                repeat with cand in windows
                  repeat with i from 1 to count of gcNames
                    set gname to item i of gcNames as text
                    try
                      if exists group gname of group 1 of cand then
                        set w to cand
                        exit repeat
                      end if
                    end try
                  end repeat
                end repeat
                if w is missing value then error "Controller settings window not found"
                set gcGroup to missing value
                repeat with i from 1 to count of gcNames
                  set gname to item i of gcNames as text
                  try
                    set gcGroup to group gname of group 1 of w
                  end try
                end repeat
                if gcGroup is missing value then error "GameCube controller group not found"
                set port2 to item 2 of combo boxes of gcGroup
                click port2
                delay 0.45
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
                      end repeat
                    end try
                  end if
                end repeat
                set downs to 0
                if "{kind}" is "gba" then
                  set found to false
                  repeat with i from 1 to count of titles
                    set t to item i of titles
                    if t contains "GBA" and (t contains "integrad" or t contains "Integrated" or t contains "integrated") then
                      set downs to i - 1
                      set found to true
                      exit repeat
                    end if
                  end repeat
                  if found is false then error "GBA (Integrated) not in Port 2 list"
                else
                  set found to false
                  repeat with i from 1 to count of titles
                    if item i of titles is in {none_labels} then
                      set downs to i - 1
                      set found to true
                      exit repeat
                    end if
                  end repeat
                  if found is false then set downs to 0
                end if
                repeat 16 times
                  key code 126
                  delay 0.03
                end repeat
                if downs > 0 then
                  repeat downs times
                    key code 125
                    delay 0.03
                  end repeat
                end if
                key code 36
                delay 0.5
                set closeNames to {close_labels}
                set closed to false
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
                if closed is false then
                  key code 53
                end if
              end tell
            end tell
            """
        )
        time.sleep(0.4)
