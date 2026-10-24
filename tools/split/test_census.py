from __future__ import annotations

import os
import struct
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import census

BODY = 0x08000100
OPEN = 0x08000130
CALLER = 0x08000140
COPY = 0x08000340


def put(image, address, values, width):
    offset = address - census.ROM_BASE
    for number, value in enumerate(values):
        struct.pack_into("<H" if width == 2 else "<I", image, offset + number * width, value)


def crafted():
    image = bytearray(0x400)
    put(image, 0x08000000, [0xEA00002E], 4)
    put(image, 0x080000C0, [0xE92D4000, 0xEB000019, 0xE8BD8000], 4)
    put(image, BODY, [0xB500, 0xD000, 0xBD00, 0xBD00], 2)
    put(image, OPEN, [0xF0000000], 4)
    put(image, CALLER, [0xB500, 0xD000, 0xBD00, 0xBD00], 2)
    put(image, 0x08000200, [BODY | 1, CALLER | 1, 0x00000000, 0x00000000], 4)
    put(image, 0x08000300, [0x4806, 0x4907, 0x6001, 0x4907, 0x6041, 0x2102, 0x8101, 0x0000], 2)
    put(image, 0x0800031C, [0x040000D4, COPY, 0x03003BC0], 4)
    put(image, COPY, [0xE92D4000, 0xE8BD8000], 4)
    return bytes(image)


def test_the_pointer_run_starts_its_words():
    result = census.census_result(crafted())
    assert BODY in result["starts"]
    assert result["starts"][BODY]["limbs"] == ["table"]
    assert CALLER in result["starts"]


def test_a_dropped_seed_channel_drops_the_start_it_owns():
    image = crafted()
    kept = census.census_result(image)
    dropped = census.census_result(image, channels=("vector", "call", "pool", "repeated"))
    assert BODY in kept["starts"]
    assert BODY not in dropped["starts"]
    assert CALLER not in dropped["starts"]


def test_the_copy_channel_is_load_bearing():
    image = crafted()
    kept = census.census_result(image)
    dropped = census.census_result(image, channels=("vector", "call", "pool", "table",
                                                    "repeated"))
    assert COPY in kept["starts"]
    assert kept["starts"][COPY]["limbs"] == ["copy"]
    assert COPY not in dropped["starts"]


def test_a_body_with_no_decodable_first_instruction_is_an_open_bound():
    result = census.census_result(crafted())
    assert result["ends"][OPEN] == (None, "no-body")
    assert sorted(address for address in result["ends"] if not result["ends"][address][0]) \
        == [OPEN]


def test_the_open_bound_closes_when_the_body_returns():
    image = bytearray(crafted())
    put(image, OPEN, [0xE92D4000, 0xE8BD8000], 4)
    result = census.census_result(bytes(image))
    assert result["ends"][OPEN][0] == OPEN + 8
    assert [address for address in result["ends"] if not result["ends"][address][0]] == []


def test_every_tracked_row_carries_its_end_and_its_channel():
    result = census.census_result(crafted())
    lines = census.text(census.rows(result)).splitlines()
    assert lines[0] == census.HEADER
    channels = set()
    opened = []
    for line in lines[1:]:
        address, kind, channel, _mode, end, _reason, _flags, _evidence = line.split(",")
        channels.update(channel.split("+"))
        if kind == "start" and end == "-":
            opened.append(int(address, 16))
    assert opened == [OPEN]
    assert "vector" in channels and "table" in channels


def test_a_body_that_runs_past_the_cap_closes_at_its_measured_end():
    image = bytearray(0x1000)
    put(image, 0x08000080, [0x46C0] * 0x3C0, 2)
    put(image, 0x08000800, [0x4770], 2)
    starts = {0x08000080: census.MODE_THUMB}
    ends, _bodies = census.ends_of(bytes(image), starts, starts, set())
    assert ends[0x08000080] == (0x08000802, "-")


def test_closure_reads_a_run_without_a_class_array():
    image = bytearray(0x100)
    put(image, 0x08000020, [0x2000, 0x4770], 2)
    assert census.closure(bytes(image), 0x08000020) == ("return", 0x08000024)


def test_a_channel_at_or_above_its_bar_is_refused():
    assert census.under_bar(4, 100) is True
    assert census.under_bar(5, 100) is False
    assert census.under_bar(1, 20) is False


def test_the_remainder_classes_partition_a_crafted_image():
    image = crafted()
    result = census.census_result(image)
    table = census.remainder(image, result)
    assert sum(size for _name, size in table["split"]) == table["bytes"]
    assert result["proven_bytes"] + table["bytes"] == len(image)


def test_an_empty_register_list_halfword_is_recognised():
    assert census.empty_list(bytearray(b"\x00\xcd"), 0x08000000) is True
    assert census.empty_list(bytearray(b"\x00\xc0"), 0x08000000) is True
    assert census.empty_list(bytearray(b"\x01\xcd"), 0x08000000) is False
    assert census.empty_list(bytearray(b"\x00\xdd"), 0x08000000) is False


def test_a_body_with_an_empty_register_list_is_flagged_data():
    image = bytearray(crafted())
    put(image, CALLER, [0xB500, 0xD000, 0xCD00, 0x4770], 2)
    result = census.census_result(bytes(image))
    assert "data" in result["flags"][CALLER]


def test_a_body_without_an_empty_register_list_is_not_flagged_data():
    result = census.census_result(crafted())
    assert "data" not in result["flags"][CALLER]


def test_the_tracked_evidence_is_what_the_retail_image_gives():
    path = os.path.join(ROOT, "baserom.gba")
    if not os.path.exists(path):
        pytest.skip("%s is absent, so this ROM-gated test cannot run" % path)
    rom = open(path, "rb").read()
    assert len(rom) == census.ROM_SIZE
    result = census.census_result(rom)
    open_bounds = [address for address in result["ends"] if not result["ends"][address][0]]
    assert open_bounds == []
    table = census.remainder(rom, result)
    assert sum(size for _name, size in table["split"]) == table["bytes"]
    split = census.split_of(table["split"])
    assert (result["proven_bytes"] + split["padding"] + split["data"] + split["code"]
            + split["residual"]) == len(rom)
    for path, payload in ((census.EVIDENCE, census.text(census.rows(result))),
                          (census.DOC, census.doc_text(result, table))):
        assert os.path.exists(path)
        assert open(path, encoding="utf-8").read() == payload
