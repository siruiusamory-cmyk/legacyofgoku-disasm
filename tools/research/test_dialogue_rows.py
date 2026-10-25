from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "gate"))

import dialogue_rows
import gate
import testkit


def image():
    return testkit.rom_bytes(dialogue_rows.ROM, gate.CANONICAL_SHA256, gate.ROM_SIZE)


def family(rom):
    return rom[dialogue_rows.BASE - dialogue_rows.ROM_BASE:
               dialogue_rows.END - dialogue_rows.ROM_BASE]


def extents(measured):
    records = measured["records"]
    return [(record["base"], record["base"] + dialogue_rows.NODE * len(record["nodes"]) +
             sum(len(name) + 1 for name in record["strings"])) for record in records]


def test_the_code_bounds_the_table_at_the_committed_bounds():
    rom = image()
    base, stride, node, rows = dialogue_rows.bounds(rom)
    assert (base, stride, node, rows) == (dialogue_rows.BASE, dialogue_rows.STRIDE,
                                          dialogue_rows.NODE, dialogue_rows.ROWS)
    assert dialogue_rows.FIRST == base + rows * stride
    assert dialogue_rows.FIRST < dialogue_rows.END


def test_every_record_re_encodes_and_the_family_is_the_image_bytes():
    rom = image()
    measured = dialogue_rows.census(rom)
    rows = dialogue_rows.decode(rom)
    assert dialogue_rows.rebuild(rows) == family(rom)
    assert measured["bytes"] == dialogue_rows.END - dialogue_rows.BASE
    assert measured["records"] == dialogue_rows.ROWS
    assert measured["nodes"] > measured["records"]
    assert measured["strings"] > measured["records"]


def test_every_record_tiles_to_the_next_record_and_the_last_ends_at_the_bound():
    rom = image()
    measured = dialogue_rows.decode(rom)
    spans = extents(measured)
    assert [base for base, _stop in spans] == [record["base"] for record in measured["records"]]
    for (_base, stop), next_ in zip(spans, spans[1:] + [(dialogue_rows.END,)]):
        assert stop == next_[0]
    assert spans[-1][1] == dialogue_rows.END
    assert spans[0][0] == dialogue_rows.FIRST


def test_every_step_indexes_a_node_and_every_text_pointer_is_a_pool_position():
    rom = image()
    measured = dialogue_rows.decode(rom)
    for record in measured["records"]:
        starts, cursor = [], record["base"] + dialogue_rows.NODE * len(record["nodes"])
        for name in record["strings"]:
            starts.append(cursor)
            cursor += len(name) + 1
        for kind, step, index in record["nodes"]:
            assert step < len(record["nodes"])
            if kind == dialogue_rows.TERMINATOR:
                assert index is None
                continue
            assert index is not None
            assert starts[index] == record["base"] + dialogue_rows.NODE * len(record["nodes"]) + \
                sum(len(name) + 1 for name in record["strings"][:index])


def test_the_family_is_one_generated_run_and_no_slice_covers_it():
    first, last = dialogue_rows.BASE, dialogue_rows.END
    for start, length in gate.incbin_ranges(ROOT):
        assert not (start + dialogue_rows.ROM_BASE < last and first <
                    start + dialogue_rows.ROM_BASE + length)
    covered = [(start, length) for start, length in gate.generated_ranges(ROOT)
               if start + dialogue_rows.ROM_BASE < last and first <
               start + dialogue_rows.ROM_BASE + length]
    assert covered == [(first - dialogue_rows.ROM_BASE, last - first)]


def test_a_table_advanced_one_record_passes_no_row():
    rom = image()
    measured = dialogue_rows.decode(rom)
    moved = dict(measured, rows=[(index + 1) % len(measured["records"])
                                 for index in measured["rows"]])
    permuted = dialogue_rows.rebuild(moved)
    assert permuted != family(rom)
    ok = 0
    for index in range(dialogue_rows.ROWS):
        at = index * dialogue_rows.STRIDE
        if permuted[at:at + dialogue_rows.STRIDE] == family(rom)[at:at + dialogue_rows.STRIDE]:
            ok += 1
    assert ok == 0


def test_a_rotation_of_the_row_values_does_not_reproduce_the_image():
    rom = image()
    measured = dialogue_rows.decode(rom)
    rotated = dict(measured, rows=[measured["rows"][(index + 1) % len(measured["rows"])]
                                   for index in range(len(measured["rows"]))])
    assert dialogue_rows.rebuild(rotated) != family(rom)
    assert measured["rows"] != rotated["rows"]


def test_a_doctored_text_disagrees_in_exactly_one_record():
    rom = image()
    measured = dialogue_rows.decode(rom)
    once = []
    for order, record in enumerate(measured["records"]):
        for index, name in enumerate(record["strings"]):
            if len(name) > 8 and record["strings"].count(name) == 1 and \
                    sum(1 for other in measured["records"] for other_name in other["strings"]
                        if other_name == name) == 1:
                once.append((order, index))
    order, index = once[0]
    name = measured["records"][order]["strings"][index]
    measured["records"][order]["strings"][index] = name[:4] + bytes([name[4] ^ 0x01]) + name[5:]
    doctored = dialogue_rows.rebuild(measured)
    same = 0
    for (base, stop) in extents(measured):
        at = base - dialogue_rows.BASE
        stop -= dialogue_rows.BASE
        if doctored[at:stop] == family(rom)[at:stop]:
            same += 1
    assert same == dialogue_rows.ROWS - 1


def test_a_node_text_pointer_outside_the_pool_is_refused():
    rom = bytearray(image())
    at = dialogue_rows.FIRST - dialogue_rows.ROM_BASE + 4
    rom[at:at + 4] = (dialogue_rows.FIRST + 4).to_bytes(4, "little")
    assert testkit.refused(lambda: dialogue_rows.decode(bytes(rom)))
    rom[at:at + 4] = (dialogue_rows.FIRST - 0x100).to_bytes(4, "little")
    assert testkit.refused(lambda: dialogue_rows.decode(bytes(rom)))


def test_a_table_word_that_names_no_record_is_refused():
    rom = bytearray(image())
    at = dialogue_rows.BASE - dialogue_rows.ROM_BASE + 5 * dialogue_rows.STRIDE
    rom[at:at + 4] = (0).to_bytes(4, "little")
    assert testkit.refused(lambda: dialogue_rows.bounds(bytes(rom)))


def test_a_rom_whose_base_literal_moved_is_refused():
    rom = bytearray(image())
    address, text = next((address, text) for role, address, _mnemonic, text
                         in dialogue_rows.CITED if role == "base")
    at = dialogue_rows.pool(address, dialogue_rows.immediate(text)) - dialogue_rows.ROM_BASE
    rom[at] ^= 0x01
    assert testkit.refused(lambda: dialogue_rows.bounds(bytes(rom)))


def test_a_rom_whose_bytes_differ_is_refused():
    rom = bytearray(image())
    rom[dialogue_rows.END - dialogue_rows.ROM_BASE - 2] ^= 0x01
    with pytest.raises(ValueError) as caught:
        dialogue_rows.census(bytes(rom))
    assert "sha1" in str(caught.value)


def test_the_check_re_derives_the_run_and_the_slices():
    image()
    assert dialogue_rows.main(["--check"]) == 0
