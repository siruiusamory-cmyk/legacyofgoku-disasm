from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "gate"))

import actor_rows
import gate
import testkit


def image():
    return testkit.rom_bytes(actor_rows.ROM, gate.CANONICAL_SHA256, gate.ROM_SIZE)


def family(rom):
    return rom[actor_rows.BASE - actor_rows.ROM_BASE:actor_rows.END - actor_rows.ROM_BASE]


def test_the_code_bounds_the_family_at_the_committed_bounds():
    rom = image()
    base, stride, rows, end = actor_rows.bounds(rom)
    assert (base, stride, rows, end) == (actor_rows.BASE, actor_rows.STRIDE,
                                         actor_rows.ROWS, actor_rows.END)
    assert actor_rows.POOL == base + rows * stride


def test_every_row_re_encodes_and_the_family_is_the_image_bytes():
    rom = image()
    measured = actor_rows.census(rom)
    rows, _offsets = actor_rows.decode(rom)
    assert actor_rows.rebuild(rows) == family(rom)
    assert measured["bytes"] == actor_rows.END - actor_rows.BASE
    assert measured["rows"] == actor_rows.ROWS
    assert measured["named"] <= measured["rows"]


def test_every_name_pointer_is_the_first_use_of_its_name():
    rom = image()
    rows, offsets = actor_rows.decode(rom)
    seen = {}
    for row in rows:
        if not row["name"]:
            continue
        seen.setdefault(row["name"], actor_rows.POOL + sum(len(name) + 1 for name in seen))
        assert offsets[row["name"]] == seen[row["name"]]
    assert all(actor_rows.POOL <= pointer < actor_rows.END for pointer in offsets.values())


def test_the_pool_is_the_names_in_first_use_order_and_ends_on_alignment():
    rom = image()
    rows, _offsets = actor_rows.decode(rom)
    at, stop = actor_rows.POOL - actor_rows.ROM_BASE, actor_rows.END - actor_rows.ROM_BASE
    names = []
    while at < stop:
        end = rom.index(b"\0", at)
        if end == at:
            break
        names.append(rom[at:end].decode("ascii"))
        at = end + 1
    assert names == list(dict.fromkeys(row["name"] for row in rows if row["name"]))
    assert stop - at < 4


def test_the_family_is_one_generated_run_and_no_slice_covers_it():
    first, last = actor_rows.BASE, actor_rows.END
    for start, length in gate.incbin_ranges(ROOT):
        assert not (start + actor_rows.ROM_BASE < last and first <
                    start + actor_rows.ROM_BASE + length)
    covered = [(start, length) for start, length in gate.generated_ranges(ROOT)
               if start + actor_rows.ROM_BASE < last and first <
               start + actor_rows.ROM_BASE + length]
    assert covered == [(first - actor_rows.ROM_BASE, last - first)]


def test_a_table_advanced_one_row_passes_no_row():
    rom = image()
    rows = actor_rows.decode(rom)[0]
    moved = [dict(rows[(index + 1) % len(rows)], index=index) for index in range(len(rows))]
    permuted = actor_rows.rebuild(moved)
    assert sum(1 for row in moved
               if permuted[row["index"] * actor_rows.STRIDE:
                           (row["index"] + 1) * actor_rows.STRIDE] ==
               rom[actor_rows.BASE - actor_rows.ROM_BASE +
                   row["index"] * actor_rows.STRIDE:
                   actor_rows.BASE - actor_rows.ROM_BASE +
                   (row["index"] + 1) * actor_rows.STRIDE]) == 0


def test_a_rotation_that_keeps_each_index_reproduces_the_image():
    rom = image()
    rows = actor_rows.decode(rom)[0]
    rotated = [rows[(index + 1) % len(rows)] for index in range(len(rows))]
    assert actor_rows.rebuild(rotated) == family(rom)


def test_a_doctored_row_disagrees_in_exactly_one_row():
    rom = image()
    rows = actor_rows.decode(rom)[0]
    rows[17] = dict(rows[17], hp=rows[17]["hp"] + 1)
    doctored = actor_rows.rebuild(rows)
    assert sum(1 for row in rows
               if doctored[row["index"] * actor_rows.STRIDE:
                           (row["index"] + 1) * actor_rows.STRIDE] !=
               rom[actor_rows.BASE - actor_rows.ROM_BASE +
                   row["index"] * actor_rows.STRIDE:
                   actor_rows.BASE - actor_rows.ROM_BASE +
                   (row["index"] + 1) * actor_rows.STRIDE]) == 1


def test_a_name_pointer_outside_the_pool_is_refused():
    rom = image()
    assert testkit.refused(lambda: actor_rows.name_at(rom, actor_rows.POOL - 4))
    assert testkit.refused(lambda: actor_rows.name_at(rom, actor_rows.END))
    assert actor_rows.name_at(rom, actor_rows.POOL)


def test_a_rom_whose_base_literal_moved_is_refused():
    rom = bytearray(image())
    address, text = next((address, text) for role, address, _mnemonic, text in actor_rows.CITED
                         if role == "base")
    at = actor_rows.pool(address, actor_rows.immediate(text)) - actor_rows.ROM_BASE
    rom[at] ^= 0x01
    assert testkit.refused(lambda: actor_rows.bounds(rom))


def test_a_rom_whose_bytes_differ_is_refused():
    rom = bytearray(image())
    rom[actor_rows.BASE - actor_rows.ROM_BASE + 0x38] ^= 0x01
    with pytest.raises(ValueError) as caught:
        actor_rows.census(rom)
    assert "sha1" in str(caught.value)


def test_the_check_re_derives_the_run_and_the_slices():
    image()
    assert actor_rows.main(["--check"]) == 0
