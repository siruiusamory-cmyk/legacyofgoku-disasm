from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "gate"))

import credits_rows
import gate
import testkit


def image():
    return testkit.rom_bytes(credits_rows.ROM, gate.CANONICAL_SHA256, gate.ROM_SIZE)


def family(rom):
    return rom[credits_rows.BASE - credits_rows.ROM_BASE:
               credits_rows.END - credits_rows.ROM_BASE]


def pointers(rom):
    return [credits_rows.word(rom, credits_rows.BASE + credits_rows.HEADER + index *
                              credits_rows.STRIDE)
            for index in range(credits_rows.ROWS)]


def test_the_code_bounds_the_table_at_the_committed_bounds():
    rom = image()
    base, header, stride, rows = credits_rows.bounds(rom)
    assert (base, header, stride, rows) == (credits_rows.BASE, credits_rows.HEADER,
                                            credits_rows.STRIDE, credits_rows.ROWS)
    assert credits_rows.POOL == base + header + rows * stride
    assert credits_rows.POOL < credits_rows.END


def test_every_row_re_encodes_and_the_family_is_the_image_bytes():
    rom = image()
    measured = credits_rows.census(rom)
    rows = credits_rows.decode(rom)
    assert credits_rows.rebuild(rows) == family(rom)
    assert measured["bytes"] == credits_rows.END - credits_rows.BASE
    assert measured["rows"] == credits_rows.ROWS
    assert measured["texts"] <= measured["rows"]


def test_every_pointer_is_the_pool_position_of_its_text():
    rom = image()
    rows = credits_rows.decode(rom)
    starts, cursor = [], credits_rows.POOL
    for name in rows["texts"]:
        starts.append(cursor)
        cursor += len(name) + 1
    assert cursor == credits_rows.END
    for pointer, index in zip(pointers(rom), rows["rows"]):
        assert credits_rows.POOL <= pointer < credits_rows.END
        assert pointer == starts[index]


def test_the_pool_is_the_texts_in_first_use_order():
    rom = image()
    rows = credits_rows.decode(rom)
    at, stop = credits_rows.POOL - credits_rows.ROM_BASE, credits_rows.END - credits_rows.ROM_BASE
    texts = []
    while at < stop:
        end = rom.index(b"\0", at)
        assert end < stop
        texts.append(rom[at:end])
        at = end + 1
    assert at == stop
    assert texts == list(dict.fromkeys(rows["texts"][index] for index in rows["rows"]))


def test_the_family_is_one_generated_run_and_no_slice_covers_it():
    first, last = credits_rows.BASE, credits_rows.END
    for start, length in gate.incbin_ranges(ROOT):
        assert not (start + credits_rows.ROM_BASE < last and first <
                    start + credits_rows.ROM_BASE + length)
    covered = [(start, length) for start, length in gate.generated_ranges(ROOT)
               if start + credits_rows.ROM_BASE < last and first <
               start + credits_rows.ROM_BASE + length]
    assert covered == [(first - credits_rows.ROM_BASE, last - first)]


def test_a_table_advanced_one_row_passes_no_row():
    rom = image()
    rows = credits_rows.decode(rom)
    moved = dict(rows, rows=[(index + 1) % len(rows["texts"]) for index in rows["rows"]])
    permuted = credits_rows.rebuild(moved)
    width = credits_rows.STRIDE
    ok = 0
    for index in range(credits_rows.ROWS):
        at = credits_rows.HEADER + index * width
        if permuted[at:at + width] == family(rom)[at:at + width]:
            ok += 1
    assert ok == 0


def test_a_rotation_of_the_row_values_does_not_reproduce_the_image():
    rom = image()
    rows = credits_rows.decode(rom)
    rotated = dict(rows, rows=[rows["rows"][(index + 1) % len(rows["rows"])]
                              for index in range(len(rows["rows"]))])
    assert credits_rows.rebuild(rotated) != family(rom)
    assert rows["rows"] != rotated["rows"]


def test_a_doctored_text_disagrees_in_exactly_one_row():
    rom = image()
    rows = credits_rows.decode(rom)
    starts, cursor = [], credits_rows.POOL
    for name in rows["texts"]:
        starts.append(cursor)
        cursor += len(name) + 1
    once = [index for index, name in enumerate(rows["texts"])
            if rows["texts"].count(name) == 1 and rows["rows"].count(index) == 1]
    target = once[0]
    rows["texts"][target] = (rows["texts"][target][:4] +
                             bytes([rows["texts"][target][4] ^ 0x01]) +
                             rows["texts"][target][5:])
    doctored = credits_rows.rebuild(rows)
    good = 0
    for index in rows["rows"]:
        at = starts[index] - credits_rows.BASE
        width = len(rows["texts"][index]) + 1
        if doctored[at:at + width] == family(rom)[at:at + width]:
            good += 1
    assert good == credits_rows.ROWS - 1


def test_a_text_pointer_outside_the_pool_is_refused():
    rom = image()
    assert testkit.refused(lambda: credits_rows.string_at(rom, credits_rows.POOL - 4,
                                                          credits_rows.END))
    assert testkit.refused(lambda: credits_rows.string_at(rom, credits_rows.END,
                                                          credits_rows.END))
    assert credits_rows.string_at(rom, credits_rows.POOL, credits_rows.POOL + 4) == b"\n"


def test_a_row_pointer_outside_the_pool_is_refused():
    rom = bytearray(image())
    at = credits_rows.BASE - credits_rows.ROM_BASE + credits_rows.HEADER
    rom[at:at + 4] = (credits_rows.POOL - 8).to_bytes(4, "little")
    assert testkit.refused(lambda: credits_rows.decode(bytes(rom)))


def test_a_rom_whose_base_literal_moved_is_refused():
    rom = bytearray(image())
    address, text = next((address, text) for role, address, _mnemonic, text in credits_rows.CITED
                         if role == "base")
    at = credits_rows.pool(address, credits_rows.immediate(text)) - credits_rows.ROM_BASE
    rom[at] ^= 0x01
    assert testkit.refused(lambda: credits_rows.bounds(bytes(rom)))


def test_a_rom_whose_bytes_differ_is_refused():
    rom = bytearray(image())
    rom[credits_rows.POOL - credits_rows.ROM_BASE + 2] ^= 0x01
    with pytest.raises(ValueError) as caught:
        credits_rows.census(bytes(rom))
    assert "sha1" in str(caught.value)


def test_the_check_re_derives_the_run_and_the_slices():
    image()
    assert credits_rows.main(["--check"]) == 0
