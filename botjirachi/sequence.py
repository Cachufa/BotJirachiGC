"""One Channel → Ruby Jirachi receive: timed Channel menus, then GBA on.

v1 is delays + mapped pads, not GameCube RAM. Tune the constants below from a
working manual run (`jirachi-steps.txt`). Do not pass SIDevice on the Dolphin
command line; Port 2 GBA is enabled only at the “turn on GBA” prompt.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from botjirachi.dolphin import DolphinError, DolphinSession
from botjirachi.inputs import PadDriver
from botjirachi.restore import RestoreError, restore_ruby_save

# PAL boot: "choose 50/60 Hz", A, then two options (60 top, 50 bottom).
# On this Dolphin setup the prompt appears every boot (unlike retail GC).
# 60 is faster wall-clock for the hunt.
PAL_HZ = 60
# Intro "you must choose" can take A early. The 50/60 list must be up
# before A or that press lands on title Continue and the rest is junk.
HZ_INTRO_S = 0.7
HZ_AFTER_A_S = 2.8
HZ_CONFIRM_S = 2.0
HZ_AFTER_CONFIRM_S = 2.5
# 60 Hz is already highlighted (top). 50 Hz is the lower option — nudge down.
HZ_STICK_HOLD_S = 0.18
# Title is a 2x2 on the TV (screenshot, cursor on Options):
#   NUEVO JUEGO    OPCIONES
#   CONTINUAR      EXTRA
# Cursor starts on Continuar. Right → Extra (0.08s was enough).
# Up 0.08s overshot Opciones by a little.
TITLE_READY_S = 8.0
TITLE_STICK_RIGHT_S = 0.08
TITLE_STICK_UP_S = 0.05
# Between attempts the Options cursor sits a tad below Jirachi.
# 0.04/0.02 were both clamped to 0.05s HID min and overshot above the button.
RETRY_JIRACHI_STICK_UP_S = 0.02
# Options submenu is the same 2x2 (screenshot, cursor on Jirachi):
#   1 Ajustes    2 Jirachi
#   3 Créditos   4 Volver
# Buttons appear a beat later than the title 2x2.
OPTIONS_AFTER_OPEN_S = 2.6
# After Jirachi: wait, then A to Oak, animation, then more A/Yes, then GBA.
# A during a text crawl only skips the crawl, not the next box.
JIRACHI_AFTER_SELECT_S = 9.0
OAK_A_BEFORE_ANIM_S = 9
OAK_A_BEFORE_ANIM_BETWEEN_S = 1.15
JIRACHI_SCENE_S = 30.0
OAK_YES_BEFORE_GBA = 16
OAK_YES_BETWEEN_S = 0.55
GBA_AFTER_OAK_S = 2.0
# After GBA on, Channel writes -2.sav when Jirachi lands (~17 s measured
# from "GBA on" to mtime). Cap 18 s; return earlier if the file updates.
TRANSFER_AFTER_GBA_S = 18.0
# After a failed receive Channel is on “turn off the GBA”. Port 2 None,
# then A through leftover text, then restore while the GBA is off.
# 1 s after the A's is a placeholder; tune when Home/Options is confirmed.
FAIL_A_TIMES = 3
FAIL_A_BETWEEN_S = 0.55
FAIL_AFTER_A_S = 1.0


class SequenceError(Exception):
    """Timed Channel/Ruby sequence missed a window or timed out."""


def recover_after_fail(
    session: DolphinSession,
    pad: PadDriver | None = None,
) -> None:
    """Turn off GBA, dismiss leftover Channel text, restore the Ruby save.

    Order matters: do not copy the original `.sav` while Port 2 GBA is still
    on. Does not reset Channel and does not touch PAL 50/60 Hz.
    """
    if pad is None:
        pad = PadDriver(session)
    _log("fail: Port 2 None (turn off GBA)")
    try:
        session.set_port2_none()
    except DolphinError as exc:
        raise SequenceError(str(exc)) from exc
    _log(f"fail: A x{FAIL_A_TIMES}, then wait {FAIL_AFTER_A_S:.0f}s")
    pad.tap_channel("A", times=FAIL_A_TIMES, between_s=FAIL_A_BETWEEN_S)
    time.sleep(FAIL_AFTER_A_S)
    _log("fail: restore original Ruby save")
    try:
        restore_ruby_save(session.paths)
    except RestoreError as exc:
        raise SequenceError(str(exc)) from exc


def receive_jirachi(
    session: DolphinSession,
    pad: PadDriver | None = None,
    *,
    pal_hz: int = PAL_HZ,
    select_pal_hz: bool = True,
) -> Path:
    """Run one unattended receive. Returns the Port 2 Ruby `.sav` path.

    Caller must already have Channel booted and the original Ruby save
    restored. Does not parse SV and does not loop. When `select_pal_hz` is
    true, resets Channel so the PAL 50/60 Hz prompt is a known first step.
    Retries after `recover_after_fail` skip that (Channel is already in-game).
    """
    if pal_hz not in (50, 60):
        raise SequenceError(f"pal_hz must be 50 or 60, not {pal_hz!r}")
    if pad is None:
        pad = PadDriver(session)
    sav = session.paths.dolphin_ruby_sav_port2

    if select_pal_hz:
        _log("Reset Channel for a known boot (Hz prompt → title)")
        session.reset_emulation()
        time.sleep(2.0)
        session.wait_channel_without_gba(timeout_s=40)
        _select_pal_hz(pad, pal_hz)
    else:
        _log("skip PAL Hz (Channel already in-game)")
    _channel_to_gba_prompt(pad, from_boot=select_pal_hz)
    before = _mtime(sav)
    _turn_on_gba(session)
    gba_on = datetime.now().isoformat(timespec="seconds")
    _log(f"GBA on at {gba_on}; wait up to {TRANSFER_AFTER_GBA_S:.0f}s for {sav.name}")
    waited = _wait_sav_update(sav, before, TRANSFER_AFTER_GBA_S)
    if waited is None:
        _log(f"sav mtime unchanged after {TRANSFER_AFTER_GBA_S:.0f}s")
    else:
        _log(
            f"sav updated at {datetime.now().isoformat(timespec='seconds')} "
            f"(+{waited:.1f}s after GBA on)"
        )
    return sav


def _nudge_tv_top_right(pad: PadDriver) -> None:
    """2x2 TV buttons: from bottom-left, Right then Up to the top-right slot."""
    pad.hold_channel_stick("Right", hold_s=TITLE_STICK_RIGHT_S)
    time.sleep(0.18)
    pad.hold_channel_stick("Up", hold_s=TITLE_STICK_UP_S)
    time.sleep(0.18)


def _select_pal_hz(pad: PadDriver, pal_hz: int) -> None:
    """A on 'you must choose'; pick 50/60; A on 'you selected Hz'.

    60 Hz is the upper option and already highlighted — do not shove the
    cursor to the top of the screen. 50 Hz is a short Down. Then A on the
    confirmation screen (that A is not the title Continue).
    """
    _log(f"PAL Hz: wait {HZ_INTRO_S:.1f}s, A, pick {pal_hz}, A, confirm A")
    time.sleep(HZ_INTRO_S)
    pad.tap_channel("A")
    time.sleep(HZ_AFTER_A_S)
    if pal_hz == 50:
        pad.hold_channel_stick("Down", hold_s=HZ_STICK_HOLD_S)
        time.sleep(0.12)
    pad.tap_channel("A")
    time.sleep(HZ_CONFIRM_S)
    pad.tap_channel("A")
    time.sleep(HZ_AFTER_CONFIRM_S)


def _channel_to_gba_prompt(pad: PadDriver, *, from_boot: bool = True) -> None:
    _log(f"wait {TITLE_READY_S:.0f}s for Channel title")
    time.sleep(TITLE_READY_S)
    _log("title: Continuar → Right (Extra) → Up (Opciones) → A")
    _nudge_tv_top_right(pad)
    pad.tap_channel("A")
    _log(f"wait {OPTIONS_AFTER_OPEN_S:.1f}s for Options 2x2; Jirachi already under cursor")
    time.sleep(OPTIONS_AFTER_OPEN_S)
    if not from_boot:
        _log(f"retry: Up {RETRY_JIRACHI_STICK_UP_S:.2f}s onto Jirachi (stick only)")
        pad.hold_channel_stick(
            "Up", hold_s=RETRY_JIRACHI_STICK_UP_S, refocus=False
        )
    pad.tap_channel("A")
    _log(f"wait {JIRACHI_AFTER_SELECT_S:.1f}s, then {OAK_A_BEFORE_ANIM_S} A, then animation")
    time.sleep(JIRACHI_AFTER_SELECT_S)
    pad.tap_channel(
        "A", times=OAK_A_BEFORE_ANIM_S, between_s=OAK_A_BEFORE_ANIM_BETWEEN_S
    )
    _log(f"wait {JIRACHI_SCENE_S:.0f}s for Oak animation (no A)")
    time.sleep(JIRACHI_SCENE_S)
    _log(f"Oak A/Yes x{OAK_YES_BEFORE_GBA} fast (after animation, before GBA)")
    pad.tap_channel("A", times=OAK_YES_BEFORE_GBA, between_s=OAK_YES_BETWEEN_S)
    time.sleep(GBA_AFTER_OAK_S)


def _turn_on_gba(session: DolphinSession) -> None:
    """Last step: Port 2 GBA + Rom2. No Ruby/Channel buttons."""
    _log("enable Port 2 GBA + load Ruby (last step, no pad)")
    try:
        session.load_ruby_rom()
    except DolphinError as exc:
        raise SequenceError(str(exc)) from exc
    if not session.has_gba_window():
        raise SequenceError(
            "GBA window missing after Port 2 GBA. "
            f"Windows: {session.window_titles()}"
        )


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _wait_sav_update(path: Path, before: float, timeout_s: float) -> float | None:
    """Seconds until mtime changes, or None on timeout."""
    deadline = time.time() + timeout_s
    t0 = time.time()
    while time.time() < deadline:
        if _mtime(path) > before:
            return time.time() - t0
        time.sleep(0.2)
    return None


def _log(message: str) -> None:
    print(f"sequence: {message}", flush=True)
