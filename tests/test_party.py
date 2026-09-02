"""Unit tests for Gen 3 party parse / Jirachi SV (no ROM dumps)."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from botjirachi.party import (
    CHANNEL_TID,
    JIRACHI_SPECIES,
    PARTY_SLOT_SIZE,
    RS_PARTY_COUNT_OFFSET,
    RS_PARTY_OFFSET,
    SAVE_BLOCKS,
    SECTION_COUNT,
    SECTION_DATA_SIZE,
    SECTION_SIZE,
    SIGNATURE,
    SavError,
    _SUBSTRUCTURE_ORDERS,
    _pokemon_checksum,
    _section_checksum,
    _xor_data,
    jirachi_from_save,
    jirachi_shiny_value,
    parse_party,
    shiny_value,
)


def _encode_gen3(text: str, length: int) -> bytes:
    table = {c: 0xBB + i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
    table.update({c: 0xD5 + i for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")})
    table[" "] = 0x00
    # OT is 7 bytes: "CHANNEL" fills the field with no 0xFF terminator.
    out = bytearray([0xFF] * length)
    for i, char in enumerate(text[:length]):
        out[i] = table[char]
    return bytes(out)


def _pack_mon(
    *,
    personality: int,
    tid: int,
    sid: int,
    species: int,
    nickname: str,
    ot_name: str,
) -> bytes:
    otid = (tid & 0xFFFF) | ((sid & 0xFFFF) << 16)
    decrypted = bytearray(48)
    order = _SUBSTRUCTURE_ORDERS[personality % 24]
    growth_at = order.index("G") * 12
    struct.pack_into("<H", decrypted, growth_at, species)
    checksum = _pokemon_checksum(bytes(decrypted))
    encrypted = _xor_data(bytes(decrypted), personality ^ otid)
    blob = bytearray(PARTY_SLOT_SIZE)
    struct.pack_into("<II", blob, 0, personality, otid)
    blob[0x08:0x12] = _encode_gen3(nickname, 10)
    blob[0x14:0x1B] = _encode_gen3(ot_name, 7)
    struct.pack_into("<H", blob, 0x1C, checksum)
    blob[0x20:0x50] = encrypted
    return bytes(blob)


def _write_section(buf: bytearray, slot: int, section_id: int, counter: int, payload: bytes) -> None:
    off = slot * SECTION_SIZE
    data = bytearray(SECTION_SIZE)
    data[: len(payload)] = payload
    struct.pack_into("<HHII", data, 0xFF4, section_id, 0, SIGNATURE, counter)
    struct.pack_into("<H", data, 0xFF6, _section_checksum(bytes(data)))
    buf[off : off + SECTION_SIZE] = data


def _build_save(mons: list[bytes], *, counter: int = 1) -> bytes:
    buf = bytearray(SAVE_BLOCKS * SECTION_COUNT * SECTION_SIZE)
    for section_id in range(SECTION_COUNT):
        payload = bytearray()
        if section_id == 1:
            payload = bytearray(RS_PARTY_OFFSET + PARTY_SLOT_SIZE * 6)
            payload[RS_PARTY_COUNT_OFFSET] = len(mons)
            for i, mon in enumerate(mons):
                start = RS_PARTY_OFFSET + i * PARTY_SLOT_SIZE
                payload[start : start + PARTY_SLOT_SIZE] = mon
        _write_section(buf, section_id, section_id, counter, bytes(payload))
    return bytes(buf)


def _write_tmp(data: bytes) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".sav", delete=False)
    tmp.write(data)
    tmp.close()
    return Path(tmp.name)


class ShinyValueTests(unittest.TestCase):
    def test_formula(self) -> None:
        # Live Channel Jirachi from the working -2.sav (plan 05 receive).
        self.assertEqual(shiny_value(0x2B69810E, 40122, 49197), 63216)
        self.assertFalse(63216 <= 7)

    def test_shiny_range(self) -> None:
        # PID 0x00000007, TID 0, SID 0 → SV 7 (shiny inclusive).
        self.assertEqual(shiny_value(0x00000007, 0, 0), 7)
        self.assertEqual(shiny_value(0x00000008, 0, 0), 8)


class PartyParseTests(unittest.TestCase):
    def tearDown(self) -> None:
        for path in getattr(self, "_tmps", []):
            path.unlink(missing_ok=True)

    def _tmp(self, data: bytes) -> Path:
        path = _write_tmp(data)
        self._tmps = getattr(self, "_tmps", []) + [path]
        return path

    def test_channel_jirachi_sv(self) -> None:
        mon = _pack_mon(
            personality=0x2B69810E,
            tid=CHANNEL_TID,
            sid=49197,
            species=JIRACHI_SPECIES,
            nickname="JIRACHI",
            ot_name="CHANNEL",
        )
        path = self._tmp(_build_save([mon]))
        found = jirachi_from_save(path)
        self.assertEqual(found.species, JIRACHI_SPECIES)
        self.assertEqual(found.ot_name, "CHANNEL")
        self.assertEqual(found.tid, CHANNEL_TID)
        self.assertEqual(found.shiny_value, 63216)
        self.assertFalse(found.is_shiny)
        self.assertEqual(jirachi_shiny_value(path), 63216)

    def test_empty_party_fails(self) -> None:
        path = self._tmp(_build_save([]))
        with self.assertRaises(SavError) as ctx:
            jirachi_from_save(path)
        self.assertIn("No Jirachi", str(ctx.exception))

    def test_party_without_jirachi_fails(self) -> None:
        groudon = _pack_mon(
            personality=0xBE120DA1,
            tid=25909,
            sid=20577,
            species=405,
            nickname="GROUDON",
            ot_name="CAPORAL",
        )
        path = self._tmp(_build_save([groudon]))
        party = parse_party(path)
        self.assertEqual(len(party), 1)
        self.assertEqual(party[0].nickname, "GROUDON")
        with self.assertRaises(SavError):
            jirachi_shiny_value(path)

    def test_too_small_file_fails(self) -> None:
        path = self._tmp(b"\x00" * 64)
        with self.assertRaises(SavError):
            parse_party(path)


if __name__ == "__main__":
    unittest.main()
