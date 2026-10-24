from __future__ import annotations

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import startup_writes
import testkit

DIGEST = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
EXPECTED = [
    (1, 0x0800AA4A, 0x0203F800, 0x040000A0, 0x4, 0xB660, 0x10),
    (2, 0x0800AA58, 0x0203FE00, 0x040000A4, 0x4, 0xF660, 0x10),
    (3, 0x080007EE, 0x030047E8, None, 0x54, 0x8100, 0xA8),
    (3, 0x08009702, 0x030047EC, 0x02000000, 0x0, 0x8500, 0x0),
    (3, 0x08009714, 0x030047EC, 0x03000000, 0x1F80, 0x8500, 0x7E00),
    (3, 0x08009912, 0x030047E8, 0x05000000, 0x100, 0x8100, 0x200),
    (3, 0x08009932, 0x030047EC, 0x0202BE24, 0x100, 0x8500, 0x400),
    (3, 0x08009980, 0x08000138, 0x03003BC0, 0x4F, 0x8400, 0x13C),
    (3, 0x0800999A, 0x030047EC, 0x03003B88, 0xE, 0x8500, 0x38),
    (3, 0x0800AA70, 0x08008814, 0x03003D44, 0x2A, 0x8400, 0xA8),
    (3, 0x0800AA80, 0x080088BC, 0x03003DEC, 0x34, 0x8400, 0xD0),
    (3, 0x0800AA8E, 0x0800898C, 0x03003EBC, 0x35, 0x8400, 0xD4),
    (3, 0x0800AAA4, 0x030047EC, 0x0203EE24, 0x477, 0x8500, 0x11DC),
]


def rows(rom):
    found = startup_writes.census(rom)
    out = []
    for kick in found["kicks"]:
        row = startup_writes.summary(rom, kick)
        item = (row["channel"], row["site"], row["source"], row["destination"],
                row["count"], row["control"], row["bytes"])
        if item not in out:
            out.append(item)
    return sorted(out, key=lambda item: (item[1], item[0]))


def image():
    return testkit.rom_bytes(os.path.join(ROOT, "baserom.gba"), DIGEST,
                             startup_writes.ROM_SIZE)


def test_the_startup_path_programmes_the_documented_bulk_writes():
    assert rows(image()) == sorted(EXPECTED, key=lambda item: (item[1], item[0]))


def test_a_changed_copy_count_is_reported_instead_of_passing_as_the_documented_row(
        tmp_path):
    rom = image()
    at = 0x08009978 - startup_writes.ROM_BASE
    assert struct.unpack_from("<H", rom, at)[0] == 0x214F, "the count literal moved"
    doctored = bytearray(rom)
    struct.pack_into("<H", doctored, at, 0x2140)
    measured = rows(bytes(doctored))
    assert measured != sorted(EXPECTED, key=lambda item: (item[1], item[0]))
    changed = [row for row in measured if row[1] == 0x08009980]
    assert changed == [(3, 0x08009980, 0x08000138, 0x03003BC0, 0x40, 0x8400, 0x100)], changed


def test_the_copied_handler_is_the_address_the_interrupt_vector_is_given():
    rom = image()
    copy = [row for row in rows(rom) if row[1] == 0x08009980][0]
    assert copy[2] == 0x08000138 and copy[3] == 0x03003BC0 and copy[6] == 0x13C
    assert copy[2] + copy[6] == 0x08000274
    found = startup_writes.census(rom)
    vector = [item for item in found["named"]
              if item[1] == copy[3] and item[2] == 0x03007FFC]
    assert vector == [(0x080099A0, 0x03003BC0, 0x03007FFC)], vector


if __name__ == "__main__":
    if os.path.exists(os.path.join(ROOT, "baserom.gba")):
        test_the_startup_path_programmes_the_documented_bulk_writes()
        test_the_copied_handler_is_the_address_the_interrupt_vector_is_given()
        print("PASS test_startup_writes")

