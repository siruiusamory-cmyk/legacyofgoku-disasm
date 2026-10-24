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


def test_the_tracked_evidence_is_what_the_retail_image_gives():
    path = os.path.join(ROOT, "baserom.gba")
    if not os.path.exists(path):
        pytest.skip("%s is absent, so this ROM-gated test cannot run" % path)
    rom = open(path, "rb").read()
    assert len(rom) == census.ROM_SIZE
    result = census.census_result(rom)
    open_bounds = [address for address in result["ends"] if not result["ends"][address][0]]
    assert open_bounds == []
    for path, payload in ((census.EVIDENCE, census.text(census.rows(result))),
                          (census.DOC, census.doc_text(result, census.remainder(rom, result)))):
        assert os.path.exists(path)
        assert open(path, encoding="utf-8").read() == payload
