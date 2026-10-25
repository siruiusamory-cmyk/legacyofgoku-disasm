from __future__ import annotations

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import bios_streams
import testkit

DIGEST = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
POPULATION = (
    (0x081BDC1C, 10947, 11656),
    (0x0815B2FC, 1580, 1736),
    (0x0819AC74, 3688, 3916),
    (0x0819BCE8, 20836, 21636),
    (0x081B3520, 20884, 21952),
    (0x084DEDE4, 24380, 24924),
    (0x0853E34C, 412, 440),
    (0x08541DB8, 384, 412),
    (0x085C31F8, 1648, 1752),
    (0x085C3888, 4484, 4760),
    (0x085C4A0C, 22244, 35204),
)
REFUSED = 0x0818A3A8


def image():
    return testkit.rom_bytes(bios_streams.ROM, DIGEST, 0x800000)


def sites(rom, start):
    word = struct.pack("<I", start)
    out, at = [], rom.find(word)
    while at >= 0:
        out.append(at)
        at = rom.find(word, at + 1)
    return out


def test_the_stream_population_is_the_pinned_rows():
    measured = bios_streams.measured(image())
    assert tuple((row["start"], row["stop"] - row["start"], row["decoded"])
                 for row in measured) == POPULATION


def test_every_stream_is_the_image_bytes_and_carries_its_own_header():
    rom = image()
    for row in bios_streams.measured(rom):
        offset = row["start"] - bios_streams.ROM_BASE
        assert rom[offset] in (0x10, 0x24, 0x28)
        assert row["body"] == rom[offset:offset + row["stop"] - row["start"]]


def test_every_stream_start_is_a_word_the_image_stores_once():
    rom = image()
    for start, _stored, _decoded in POPULATION:
        assert len(sites(rom, start)) == 1, "0x%08X is not named once" % start


def test_a_stream_that_states_its_end_ends_where_the_decoder_stops():
    rom = image()
    agreed = 0
    for row in bios_streams.measured(rom):
        offset = sites(rom, row["start"])[0]
        end = int.from_bytes(rom[offset - 4:offset], "little")
        if 0 < end - row["start"] <= 0x8000:
            assert 0 <= end - row["start"] - (row["stop"] - row["start"]) <= 1
            agreed += 1
    assert agreed == 9


def test_a_permuted_lz77_body_is_refused():
    rom = bytearray(image())
    start, stop = POPULATION[0][0], POPULATION[0][0] + POPULATION[0][1]
    body = rom[start - bios_streams.ROM_BASE + 4:stop - bios_streams.ROM_BASE]
    rom[start - bios_streams.ROM_BASE + 4:stop - bios_streams.ROM_BASE] = body[::-1]
    try:
        bios_streams.measured(bytes(rom))
    except (ValueError, IndexError):
        return
    raise AssertionError("a permuted LZ77 stream passed the round trip")


def test_a_permuted_huffman_tree_is_refused():
    rom = bytearray(image())
    start = POPULATION[1][0] - bios_streams.ROM_BASE
    rom[start + 6] ^= 0x02
    try:
        bios_streams.measured(bytes(rom))
    except (ValueError, IndexError):
        return
    raise AssertionError("a permuted Huffman tree passed the round trip")


def test_a_tree_that_shares_a_node_is_refused_instead_of_coding_twice():
    rom = image()
    assert bios_streams.decode(rom, REFUSED)[1] == 3456
    try:
        bios_streams.encode(rom, REFUSED, bios_streams.decode(rom, REFUSED)[0])
    except ValueError as problem:
        assert "shares a node" in str(problem)
        return
    raise AssertionError("a tree with a shared node re-encoded")


def test_the_tracked_token_list_is_what_the_image_derives():
    testkit.rom_bytes(bios_streams.ROM, DIGEST, 0x800000)
    assert bios_streams.main(["--check"]) == 0


if __name__ == "__main__":
    if os.path.exists(bios_streams.ROM):
        test_the_stream_population_is_the_pinned_rows()
        test_every_stream_is_the_image_bytes_and_carries_its_own_header()
        test_every_stream_start_is_a_word_the_image_stores_once()
        test_a_stream_that_states_its_end_ends_where_the_decoder_stops()
        test_a_permuted_lz77_body_is_refused()
        test_a_permuted_huffman_tree_is_refused()
        test_a_tree_that_shares_a_node_is_refused_instead_of_coding_twice()
        test_the_tracked_token_list_is_what_the_image_derives()
        print("PASS test_bios_streams")
