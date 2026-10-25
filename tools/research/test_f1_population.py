from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import f1_population
import testkit

DIGEST = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
EXPECTED_KINDS = {4: (1, 778), 12: (268, 1719166), 15: (1, 4991)}
EXPECTED_ROWS = 21424
EXPECTED_WRITTEN = 1654598
EXPECTED_CONSUMED = 1717558


def image():
    return testkit.rom_bytes(os.path.join(ROOT, "baserom.gba"), DIGEST,
                             f1_population.ROM_SIZE)


def census(rom):
    return f1_population.census(rom)


def test_the_population_is_the_header_count_and_its_entries_tile_every_record():
    measured = census(image())
    found = measured["walk"]
    assert (found["start"], found["end"], found["bytes"]) == (0x083372C8, 0x084DD59F, 1729239)
    assert found["count"] == 269 and len(found["records"]) == 269
    kinds = dict((kind, (row["entries"], row["bytes"]))
                 for kind, row in measured["kinds"].items())
    assert kinds == EXPECTED_KINDS, kinds
    assert (measured["rows"], measured["decoded"], measured["consumed"]) == (
        EXPECTED_ROWS, EXPECTED_WRITTEN, EXPECTED_CONSUMED)
    assert measured["refused"] == []


def test_the_same_walk_over_a_permuted_region_finds_no_record():
    rom = image()
    found = f1_population.walk(rom)
    assert f1_population.null(rom, found) == {"reversed": 0, "halfword": 0, "rotated": 0}


def test_a_changed_row_header_and_a_changed_tail_are_both_refused(tmp_path):
    rom = image()
    found = f1_population.walk(rom)
    record, size = found["records"][1]
    at, entry_size, kind = f1_population.entries(rom, record, size)[0]
    assert kind == f1_population.ROW_STREAM and entry_size == 6008
    doctored = bytearray(rom)
    doctored[at + 6 - f1_population.ROM_BASE] ^= 0x01
    measured = census(bytes(doctored))
    assert len(measured["refused"]) == 1
    assert "names rows" in measured["refused"][0]
    assert measured["rows"] == EXPECTED_ROWS - 80 and measured["decoded"] < EXPECTED_WRITTEN
    doctored = bytearray(rom)
    doctored[at + 6 + entry_size - 10 - f1_population.ROM_BASE] ^= 0x01
    measured = census(bytes(doctored))
    assert len(measured["refused"]) == 1
    assert "consumes" in measured["refused"][0]


def test_the_token_plans_are_not_a_function_of_the_decoded_region():
    plans = f1_population.ambiguity(image())
    assert plans == {"regions": 128670, "contents": 81024, "ambiguous": 576}


if __name__ == "__main__":
    if os.path.exists(os.path.join(ROOT, "baserom.gba")):
        test_the_population_is_the_header_count_and_its_entries_tile_every_record()
        test_the_same_walk_over_a_permuted_region_finds_no_record()
        test_a_changed_row_header_and_a_changed_tail_are_both_refused(None)
        test_the_token_plans_are_not_a_function_of_the_decoded_region()
        print("PASS test_f1_population")
