"""Parse a Gen 3 Ruby/Sapphire party from a `.sav` and compute Jirachi SV.

v1 reads the on-disk save after Channel writes it. No PKHeX, no GBA RAM.
Gen 3 stores an *internal* species index (Jirachi = 409), not National Dex 385.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

JIRACHI_NATIONAL_DEX = 385
# pret/pokeruby `SPECIES_JIRACHI` — Hoenn internal index, not National Dex.
JIRACHI_SPECIES = 409
CHANNEL_TID = 40122
SHINY_SV_MAX = 7

SECTION_SIZE = 0x1000
SECTION_DATA_SIZE = 0xF80
SECTION_COUNT = 14
SAVE_BLOCKS = 2
SIGNATURE = 0x08012025

RS_PARTY_COUNT_OFFSET = 0x0234
RS_PARTY_OFFSET = 0x0238
PARTY_SLOT_SIZE = 100
PARTY_MAX = 6

# PID % 24 → order of Growth / Attacks / EVs / Misc 12-byte chunks.
_SUBSTRUCTURE_ORDERS = (
    "GAEM",
    "GAME",
    "GEAM",
    "GEMA",
    "GMAE",
    "GMEA",
    "AGEM",
    "AGME",
    "AEGM",
    "AEMG",
    "AMGE",
    "AMEG",
    "EGAM",
    "EGMA",
    "EAGM",
    "EAMG",
    "EMGA",
    "EMAG",
    "MGAE",
    "MGEA",
    "MAGE",
    "MAEG",
    "MEGA",
    "MEAG",
)

# Western Gen 3 text (enough for CHANNEL / JIRACHI / player OT).
_GEN3_CHARS = {
    **{0xA1 + i: c for i, c in enumerate("0123456789")},
    **{0xBB + i: c for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")},
    **{0xD5 + i: c for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")},
    0x00: " ",
}


class SavError(Exception):
    """Save is missing, corrupt, or has no Channel Jirachi in the party."""


@dataclass(frozen=True)
class PartyMon:
    slot: int
    personality: int
    tid: int
    sid: int
    species: int
    nickname: str
    ot_name: str
    checksum_ok: bool

    @property
    def shiny_value(self) -> int:
        return shiny_value(self.personality, self.tid, self.sid)

    @property
    def is_shiny(self) -> bool:
        return self.shiny_value <= SHINY_SV_MAX


def shiny_value(personality: int, tid: int, sid: int) -> int:
    """`(PID_high XOR PID_low XOR TID XOR SID) & 0xFFFF`."""
    pid_high = (personality >> 16) & 0xFFFF
    pid_low = personality & 0xFFFF
    return (pid_high ^ pid_low ^ (tid & 0xFFFF) ^ (sid & 0xFFFF)) & 0xFFFF


def decode_gen3_text(raw: bytes) -> str:
    chars: list[str] = []
    for byte in raw:
        if byte == 0xFF:
            break
        chars.append(_GEN3_CHARS.get(byte, "?"))
    return "".join(chars).rstrip()


def jirachi_from_save(path: Path) -> PartyMon:
    """Return the Channel Jirachi in the party of `path`.

    Prefers OT CHANNEL / TID 40122 if more than one Jirachi is present.
    Raises `SavError` if the save is unreadable or Jirachi is missing.
    """
    party = parse_party(path)
    jirachi = [mon for mon in party if mon.species == JIRACHI_SPECIES]
    if not jirachi:
        raise SavError(f"No Jirachi (species {JIRACHI_SPECIES}) in party: {path}")
    bad = [mon for mon in jirachi if not mon.checksum_ok]
    if bad and len(bad) == len(jirachi):
        raise SavError(f"Jirachi in party has a bad checksum: {path}")
    valid = [mon for mon in jirachi if mon.checksum_ok]
    channel = [
        mon
        for mon in valid
        if mon.tid == CHANNEL_TID and mon.ot_name == "CHANNEL"
    ]
    return channel[0] if channel else valid[0]


def jirachi_shiny_value(path: Path) -> int:
    """SV of the received Jirachi. Caller logs this every attempt."""
    return jirachi_from_save(path).shiny_value


def parse_party(path: Path) -> list[PartyMon]:
    data = _read_sav(path)
    team = _active_section(data, section_id=1)
    count = team[RS_PARTY_COUNT_OFFSET]
    if count > PARTY_MAX:
        raise SavError(f"Party count {count} is not 0..{PARTY_MAX}: {path}")
    party: list[PartyMon] = []
    for slot in range(count):
        start = RS_PARTY_OFFSET + slot * PARTY_SLOT_SIZE
        blob = team[start : start + PARTY_SLOT_SIZE]
        if len(blob) < PARTY_SLOT_SIZE:
            raise SavError(f"Truncated party slot {slot}: {path}")
        party.append(_parse_party_mon(slot, blob))
    return party


def _read_sav(path: Path) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise SavError(f"Cannot read Ruby save: {path}") from exc
    need = SAVE_BLOCKS * SECTION_COUNT * SECTION_SIZE
    if len(data) < need:
        raise SavError(f"Ruby save is too small ({len(data)} bytes): {path}")
    return data


def _active_section(data: bytes, *, section_id: int) -> bytes:
    sections = _active_sections(data)
    return sections[section_id][:SECTION_DATA_SIZE]


def _active_sections(data: bytes) -> dict[int, bytes]:
    by_counter: dict[int, dict[int, bytes]] = {}
    limit = SAVE_BLOCKS * SECTION_COUNT
    for index in range(limit):
        off = index * SECTION_SIZE
        chunk = data[off : off + SECTION_SIZE]
        sid, checksum, signature, counter = struct.unpack_from("<HHII", chunk, 0xFF4)
        if signature != SIGNATURE or not (0 <= sid < SECTION_COUNT):
            continue
        if _section_checksum(chunk) != checksum:
            continue
        by_counter.setdefault(counter, {})[sid] = chunk
    complete = [
        (counter, secs)
        for counter, secs in by_counter.items()
        if len(secs) == SECTION_COUNT
    ]
    if not complete:
        raise SavError("No complete valid Gen 3 save slot (14 checksummed sections)")
    newest = complete[0]
    for candidate in complete[1:]:
        if _counter_newer(candidate[0], newest[0]):
            newest = candidate
    return newest[1]


def _counter_newer(a: int, b: int) -> bool:
    """True if unsigned save index `a` is newer than `b` (handles wrap)."""
    return a != b and ((a - b) & 0xFFFFFFFF) < 0x80000000


def _section_checksum(chunk: bytes) -> int:
    total = 0
    for offset in range(0, SECTION_DATA_SIZE, 4):
        total += struct.unpack_from("<I", chunk, offset)[0]
    return ((total & 0xFFFF) + (total >> 16)) & 0xFFFF


def _parse_party_mon(slot: int, blob: bytes) -> PartyMon:
    personality, otid = struct.unpack_from("<II", blob, 0)
    stored_checksum = struct.unpack_from("<H", blob, 0x1C)[0]
    encrypted = blob[0x20:0x50]
    decrypted = _xor_data(encrypted, personality ^ otid)
    checksum_ok = _pokemon_checksum(decrypted) == stored_checksum
    species = 0
    if checksum_ok:
        order = _SUBSTRUCTURE_ORDERS[personality % 24]
        growth_at = order.index("G") * 12
        species = struct.unpack_from("<H", decrypted, growth_at)[0]
    return PartyMon(
        slot=slot,
        personality=personality,
        tid=otid & 0xFFFF,
        sid=(otid >> 16) & 0xFFFF,
        species=species,
        nickname=decode_gen3_text(blob[0x08:0x12]),
        ot_name=decode_gen3_text(blob[0x14:0x1B]),
        checksum_ok=checksum_ok,
    )


def _xor_data(encrypted: bytes, key: int) -> bytes:
    key &= 0xFFFFFFFF
    out = bytearray()
    for offset in range(0, 48, 4):
        word = struct.unpack_from("<I", encrypted, offset)[0]
        out += struct.pack("<I", word ^ key)
    return bytes(out)


def _pokemon_checksum(decrypted: bytes) -> int:
    total = 0
    for offset in range(0, 48, 2):
        total += struct.unpack_from("<H", decrypted, offset)[0]
    return total & 0xFFFF
