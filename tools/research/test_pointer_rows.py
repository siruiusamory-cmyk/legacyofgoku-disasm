from __future__ import annotations

import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "gate"))
sys.path.insert(0, os.path.join(ROOT, "tools", "code"))

import emit_code
import gate
import pointer_rows
import testkit

RUNS = 317
BYTES = 21152
EMITTED_RUNS = 14
EMITTED_BYTES = 1308
RAW_RUNS = 303
RAW_BYTES = 19844


def image():
    return testkit.rom_bytes(pointer_rows.ROM, gate.CANONICAL_SHA256, gate.ROM_SIZE)


def measured():
    return pointer_rows.census(image())


def text():
    return open(pointer_rows.ASM, encoding="utf-8", newline="").read()


def test_the_probe_class_is_the_four_word_rule_at_the_measured_size():
    rom, found = image(), measured()["runs"]
    assert len(found) == RUNS
    assert sum(4 * count for _begin, count in found) == BYTES
    for begin, count in found:
        assert count >= pointer_rows.WORDS
        assert begin % 4 == 0
        for step in range(count):
            value = pointer_rows.word(rom, pointer_rows.ROM_BASE + begin + 4 * step)
            assert pointer_rows.ROM_BASE <= value < pointer_rows.ROM_BASE + gate.ROM_SIZE


def test_every_emitted_run_names_a_label_the_code_files_define():
    planned = measured()["planned"]
    assert len(planned) == EMITTED_RUNS
    assert sum(4 * count for _begin, count, _lines in planned) == EMITTED_BYTES
    defined = set()
    for name in os.listdir(pointer_rows.CODE):
        if name.endswith(".s"):
            body = open(os.path.join(pointer_rows.CODE, name), errors="replace").read()
            defined.update(int(hit, 16) for hit in
                           re.findall(r"\|loc_([0-9A-Fa-f]{8})\|", body))
    for begin, count, lines in planned:
        assert len(lines) == count
        for step, line in enumerate(lines):
            found = pointer_rows.DCD.match(line)
            assert found
            target = int(found.group(1), 16)
            assert target in defined
            assert target + int(found.group(2) or 0) == \
                pointer_rows.word(image(), pointer_rows.ROM_BASE + begin + 4 * step)


def test_the_runs_with_an_unlabelled_target_stay_raw():
    rom, item = image(), measured()
    assert len(item["runs"]) - len(item["planned"]) == RAW_RUNS
    assert item["ran"] - item["emitted"] == RAW_BYTES
    covered = []
    for kind, begin, size, _line in item["items"]:
        if kind == "raw":
            covered.append((begin, begin + size))
    named = [int(pointer_rows.DCD.match(line).group(1), 16) for kind, _p, _s, line
             in item["items"] if kind == "dcd"]
    assert len(named) == EMITTED_BYTES // 4
    biggest = max(item["runs"], key=lambda run: (run[1], -run[0]))
    assert (biggest[0], biggest[0] + 4 * biggest[1]) == (0x6B2CA0, 0x6B3248)
    assert any(low <= biggest[0] and biggest[0] + 4 * biggest[1] <= high
               for low, high in covered)
    assert pointer_rows.word(rom, pointer_rows.ROM_BASE + biggest[0]) & ~1 not in named


def test_a_run_whose_target_lost_its_label_is_not_planned():
    rom, item = image(), measured()
    tagged = pointer_rows.labels()
    for begin, _count, _lines in item["planned"]:
        target = pointer_rows.word(rom, pointer_rows.ROM_BASE + begin) & ~1
        users = sum(1 for _b, count, _l in item["planned"]
                    if any(pointer_rows.word(rom, pointer_rows.ROM_BASE + _b + 4 * step)
                           & ~1 == target for step in range(count)))
        fewer = pointer_rows.plan(rom, item["runs"], tagged - {target})
        assert len(fewer) == EMITTED_RUNS - users
        assert all(entry[0] != begin for entry in fewer)


def test_a_dcd_line_naming_the_wrong_label_is_refused():
    line = [entry for entry in text().splitlines() if pointer_rows.DCD.match(entry)][0]
    wrong = line.replace(line.split("|")[1], "%08X" % 0x08000138)
    doctored = text().replace(line, wrong, 1)
    assert testkit.refused(lambda: pointer_rows.verify(image(), doctored))


def test_a_dcd_line_outside_every_run_is_refused():
    doctored = text().replace("\tAREA\tRemainder, CODE, READONLY\n\n",
                              "\tAREA\tRemainder, CODE, READONLY\n\n\tDCD\t|loc_08000138|\n", 1)
    assert testkit.refused(lambda: pointer_rows.tokens(
        doctored, pointer_rows.code_bounds()))


def test_a_rom_whose_bytes_differ_is_refused():
    rom = bytearray(image())
    rom[0x6B2CB0] ^= 0x01
    with pytest.raises(ValueError) as caught:
        pointer_rows.census(bytes(rom))
    assert "sha1" in str(caught.value)


def test_the_code_row_sizes_are_the_census_bounds():
    bounds = pointer_rows.code_bounds()
    rows = [row for row in emit_code.census_rows(pointer_rows.CENSUS)
            if row["kind"] == "start" and row["end"] is not None]
    assert len(bounds) == len(rows)
    assert bounds[0x08000138] == 0x08000204


def test_the_check_re_derives_the_list():
    image()
    assert pointer_rows.main(["--check"]) == 0
    assert pointer_rows.main(["--check"]) == 0
