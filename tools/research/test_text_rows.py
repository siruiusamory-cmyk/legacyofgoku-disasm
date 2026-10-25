from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "gate"))

import gate
import testkit
import text_rows


def image():
    return testkit.rom_bytes(text_rows.ROM, gate.CANONICAL_SHA256, gate.ROM_SIZE)


def family(rom, base, end):
    return rom[base - text_rows.ROM_BASE:end - text_rows.ROM_BASE]


def extents(measured):
    at = measured["base"] + text_rows.WORD * len(measured["pointers"])
    return [(measured["base"], at)] + [
        (at, at) for at in ()]


def test_the_reader_bounds_the_stride_and_names_an_emitted_table():
    rom = image()
    seen = text_rows.cited(rom)
    assert text_rows.immediate(seen["stride"][1]) == 3
    base = text_rows.word(rom, text_rows.pool(seen["base"][0],
                                              text_rows.immediate(seen["base"][1])))
    assert base in [family[0] for family in text_rows.FAMILIES]


def test_every_family_re_encodes_from_its_rows_and_is_the_image_bytes():
    rom = image()
    measured = text_rows.census(rom)
    families = text_rows.decode(rom)
    assert measured["families"] == len(text_rows.FAMILIES)
    assert measured["bytes"] == sum(end - base for base, end in text_rows.FAMILIES)
    for one, (base, end) in zip(families, text_rows.FAMILIES):
        assert text_rows.rebuild(one) == family(rom, base, end)
        assert one["base"] == base


def test_every_pointer_tiles_and_every_string_ends_inside_its_family():
    rom = image()
    for measured, (base, end) in zip(text_rows.decode(rom), text_rows.FAMILIES):
        starts = []
        at = base + text_rows.WORD * len(measured["pointers"])
        for pointer in measured["pointers"]:
            assert base < pointer < end
            if pointer in starts:
                continue
            assert pointer == at
            starts.append(pointer)
            at = pointer + len(measured["strings"][len(starts) - 1]) + 1
        assert at == end


def test_the_spans_are_generated_runs_and_no_slice_covers_them():
    for base, end in text_rows.FAMILIES:
        for start, length in gate.incbin_ranges(ROOT):
            assert not (start + text_rows.ROM_BASE < end and
                        base < start + text_rows.ROM_BASE + length)
        covered = [(start, length) for start, length in gate.generated_ranges(ROOT)
                   if start + text_rows.ROM_BASE < end and
                   base < start + text_rows.ROM_BASE + length]
        assert covered == [(base - text_rows.ROM_BASE, end - base)]


def test_a_family_boundary_moved_by_one_byte_is_refused():
    rom = image()
    base, end = text_rows.FAMILIES[0]
    assert testkit.refused(lambda: text_rows.table_of(rom, base, end + 1))
    assert testkit.refused(lambda: text_rows.table_of(rom, base, end - 1))
    base, end = text_rows.FAMILIES[2]
    assert testkit.refused(lambda: text_rows.table_of(rom, base, end + 1))
    assert testkit.refused(lambda: text_rows.table_of(rom, base, end - 1))


def test_one_changed_string_byte_stops_the_re_encoding():
    rom = image()
    measured = text_rows.decode(rom)[0]
    base, end = text_rows.FAMILIES[0]
    good = text_rows.rebuild(measured)
    assert good == family(rom, base, end)
    measured["strings"][0] = measured["strings"][0][:4] + \
        bytes([measured["strings"][0][4] ^ 0x01]) + measured["strings"][0][5:]
    doctored = text_rows.rebuild(measured)
    assert doctored != family(rom, base, end)
    assert sum(1 for left, right in zip(doctored, family(rom, base, end))
               if left != right) == 1


def test_a_table_word_that_leaves_the_family_is_refused():
    rom = bytearray(image())
    base = text_rows.FAMILIES[0][0]
    at = base - text_rows.ROM_BASE + 3 * text_rows.WORD
    rom[at:at + 4] = (base + 0x100000).to_bytes(4, "little")
    assert testkit.refused(lambda: text_rows.table_of(bytes(rom), *text_rows.FAMILIES[0]))


def test_a_rom_whose_bytes_differ_is_refused():
    rom = bytearray(image())
    base, end = text_rows.FAMILIES[1]
    rom[end - text_rows.ROM_BASE - 1] ^= 0x01
    with pytest.raises(ValueError) as caught:
        text_rows.census(bytes(rom))
    assert "sha1" in str(caught.value)


def test_a_rom_whose_reader_moved_is_refused():
    rom = bytearray(image())
    address, text = next((address, text) for role, address, _mnemonic, text
                         in text_rows.CITED if role == "base")
    at = text_rows.pool(address, text_rows.immediate(text)) - text_rows.ROM_BASE
    rom[at] ^= 0x01
    assert testkit.refused(lambda: text_rows.cited(bytes(rom)))


def test_the_check_re_derives_the_runs_and_the_slices():
    image()
    assert text_rows.main(["--check"]) == 0
