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
STREAMS = ((0x081BDC1C, 10947, 11656),)


def image():
    return testkit.rom_bytes(bios_streams.ROM, DIGEST, 0x800000)


def test_the_lz77_population_is_the_pinned_streams():
    measured = bios_streams.measured(image())
    assert tuple((row["start"], row["stop"] - row["start"], row["decoded"])
                 for row in measured) == STREAMS


def test_every_stream_is_the_image_bytes_and_the_image_holds_a_header():
    rom = image()
    for row in bios_streams.measured(rom):
        assert rom[row["start"] - bios_streams.ROM_BASE] == 0x10
        assert row["body"] == rom[row["start"] - bios_streams.ROM_BASE:
                                  row["stop"] - bios_streams.ROM_BASE]


def test_the_streams_start_is_a_word_the_code_names():
    rom = image()
    for start, _stored, _decoded in STREAMS:
        word = struct.pack("<I", start)
        sites = [offset for offset in range(0, len(rom) - 3, 4)
                 if rom[offset:offset + 4] == word]
        assert sites, "no word names 0x%08X" % start


def test_a_permuted_stream_body_is_refused():
    rom = bytearray(image())
    start, stop = STREAMS[0][0], STREAMS[0][0] + STREAMS[0][1]
    body = rom[start - bios_streams.ROM_BASE + 4:stop - bios_streams.ROM_BASE]
    rom[start - bios_streams.ROM_BASE + 4:stop - bios_streams.ROM_BASE] = body[::-1]
    try:
        bios_streams.measured(bytes(rom))
    except (ValueError, IndexError):
        return
    raise AssertionError("a permuted stream passed the round trip")


def test_the_tracked_token_list_is_what_the_image_derives():
    testkit.rom_bytes(bios_streams.ROM, DIGEST, 0x800000)
    assert bios_streams.main(["--check"]) == 0


if __name__ == "__main__":
    if os.path.exists(bios_streams.ROM):
        test_the_lz77_population_is_the_pinned_streams()
        test_every_stream_is_the_image_bytes_and_the_image_holds_a_header()
        test_the_streams_start_is_a_word_the_code_names()
        test_a_permuted_stream_body_is_refused()
        test_the_tracked_token_list_is_what_the_image_derives()
        print("PASS test_bios_streams")
