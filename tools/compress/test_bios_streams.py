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
    (0x08166C38, 28232, 29056),
    (0x0816DC80, 22668, 23544),
    (0x0817370C, 25284, 26152),
    (0x0817ED7C, 22856, 38404),
    (0x081848C4, 22756, 23648),
    (0x0818B328, 21512, 22524),
    (0x08190930, 18164, 38404),
    (0x08195224, 22608, 23420),
    (0x0819AC74, 3688, 3916),
    (0x0819BCE8, 20836, 21636),
    (0x081A104C, 16416, 17220),
    (0x081A526C, 18180, 19396),
    (0x081A9B70, 21784, 22912),
    (0x081B3520, 20884, 21952),
    (0x081B88B4, 20840, 21664),
    (0x084DEDE4, 24380, 24924),
    (0x0853B3E0, 364, 368),
    (0x0853B578, 332, 336),
    (0x0853B6F0, 388, 400),
    (0x0853B8A0, 384, 396),
    (0x0853BBC4, 424, 444),
    (0x0853BD98, 388, 396),
    (0x0853BF48, 360, 376),
    (0x0853C0DC, 392, 428),
    (0x0853C474, 368, 372),
    (0x0853C798, 360, 364),
    (0x0853CAA4, 396, 408),
    (0x0853CC5C, 396, 424),
    (0x0853CE14, 428, 440),
    (0x0853CFEC, 396, 408),
    (0x0853D304, 368, 388),
    (0x0853D4A0, 412, 420),
    (0x0853D668, 412, 432),
    (0x0853D830, 404, 428),
    (0x0853D9F0, 408, 424),
    (0x0853DBB4, 420, 440),
    (0x0853DD84, 360, 368),
    (0x0853E34C, 412, 440),
    (0x0853E514, 344, 360),
    (0x0853EA04, 428, 444),
    (0x0853EBDC, 420, 444),
    (0x0853EDAC, 380, 428),
    (0x0853EF54, 424, 444),
    (0x0853F128, 368, 392),
    (0x0853F2C4, 412, 424),
    (0x0853F48C, 432, 440),
    (0x0853F668, 432, 440),
    (0x0853F844, 400, 404),
    (0x0853FA00, 372, 416),
    (0x0853FBA0, 420, 440),
    (0x0853FD70, 388, 424),
    (0x0853FF2C, 424, 436),
    (0x085400F4, 416, 436),
    (0x085402C0, 396, 424),
    (0x08540478, 436, 440),
    (0x08540808, 372, 376),
    (0x085409A8, 388, 424),
    (0x08540B58, 356, 380),
    (0x08540CE8, 416, 424),
    (0x08540EB4, 428, 432),
    (0x0854108C, 388, 392),
    (0x0854123C, 436, 440),
    (0x0854141C, 416, 428),
    (0x08541C20, 364, 368),
    (0x08541DB8, 384, 412),
    (0x08541F64, 408, 416),
    (0x085422E0, 404, 420),
    (0x085424A0, 372, 392),
    (0x08542640, 364, 368),
    (0x085427D8, 404, 428),
    (0x085C31F8, 1648, 1752),
    (0x085C3888, 4484, 4760),
    (0x085C4A0C, 22244, 35204),
    (0x085CA0F0, 9536, 9892),
    (0x085CC630, 16804, 18500),
    (0x085D07D4, 17440, 18996),
    (0x085D4BF4, 9468, 9860),
    (0x085D70F0, 11892, 13732),
    (0x085D9F64, 10152, 10732),
    (0x085DC70C, 9592, 9952),
    (0x085DEC84, 15600, 16828),
    (0x085E2974, 12260, 13132),
    (0x085E5958, 9752, 10080),
    (0x085E7F70, 12748, 13984),
    (0x085EB13C, 2944, 3032),
    (0x085EBCBC, 15248, 15700),
    (0x085EF84C, 5880, 6200),
    (0x085F0F44, 7580, 7892),
    (0x085F2CE0, 13948, 15112),
    (0x085F635C, 6564, 6976),
    (0x085F7D00, 4768, 4944),
    (0x085F8FA0, 17024, 17952),
    (0x085FD220, 6160, 6512),
    (0x085FEA30, 15008, 16536),
    (0x08603FC8, 7208, 7440),
    (0x08605BF0, 16656, 17836),
    (0x08609D00, 16836, 18076),
    (0x0860DEC4, 14656, 15772),
    (0x08611804, 7528, 7876),
    (0x0861356C, 10100, 10976),
    (0x08615CE0, 9536, 9900),
    (0x08618DE4, 7800, 8016),
    (0x0861AC5C, 15764, 17100),
    (0x0861E9F0, 8240, 8544),
    (0x08620A20, 25972, 30364),
    (0x08626F94, 8632, 9080),
    (0x0862914C, 20528, 22460),
    (0x0862E17C, 17916, 19376),
    (0x08632778, 8344, 8528),
    (0x08634810, 1672, 1740),
    (0x08634E98, 6904, 7192),
    (0x08636990, 15184, 18948),
    (0x0863A4E0, 7316, 7588),
    (0x0863C174, 16692, 17928),
    (0x086402A8, 2736, 3120),
    (0x08643510, 2944, 3124),
    (0x08644090, 15848, 16836),
    (0x08647E78, 2624, 2804),
    (0x086488B8, 16584, 17680),
    (0x0864C980, 2608, 2776),
    (0x0864D3B0, 18244, 19064),
    (0x08651AF4, 2620, 2832),
    (0x08652530, 12456, 13380),
    (0x086555D8, 3000, 3176),
    (0x08656190, 13676, 14496),
    (0x086596FC, 2884, 3100),
    (0x0865A240, 14868, 15704),
    (0x0865DC54, 2424, 2484),
    (0x0865E5CC, 18876, 19440),
    (0x08662F88, 2208, 2340),
    (0x08663828, 18900, 19696),
    (0x086681FC, 2108, 2252),
    (0x08668A38, 17352, 18152),
    (0x0866CE00, 1584, 1672),
    (0x0866D430, 14144, 14852),
    (0x08670B70, 3960, 4144),
    (0x08671AE8, 17080, 17916),
    (0x08675DA0, 3652, 3860),
    (0x08676BE4, 15396, 16212),
    (0x0867A808, 2748, 2896),
    (0x0867B2C4, 16876, 17776),
    (0x0867F4B0, 1772, 1844),
    (0x0867FB9C, 15728, 16412),
    (0x0868390C, 3972, 4192),
    (0x08684890, 14392, 15172),
    (0x086880C8, 4124, 4324),
    (0x086890E4, 14976, 16224),
    (0x0868CB64, 2964, 3128),
    (0x0868D6F8, 16684, 17680),
    (0x08693080, 19504, 23708),
    (0x08697CB0, 9372, 10120),
    (0x0869E49C, 6260, 6744),
    (0x0869FD10, 9372, 10120),
    (0x086A21AC, 5880, 6200),
    (0x086A7A2C, 15624, 19320),
)
REFUSED = 0x0818A3A8


def image():
    return testkit.rom_bytes(bios_streams.ROM, DIGEST, 0x800000)


MEASURED = []


def rows(rom):
    if not MEASURED:
        MEASURED.append(bios_streams.measured(rom))
    return MEASURED[0]


def sites(rom, start):
    word = struct.pack("<I", start)
    out, at = [], rom.find(word)
    while at >= 0:
        out.append(at)
        at = rom.find(word, at + 1)
    return out


def test_the_stream_population_is_the_pinned_rows():
    measured = rows(image())
    assert tuple((row["start"], row["stop"] - row["start"], row["decoded"])
                 for row in measured) == POPULATION


def test_every_stream_is_the_image_bytes_and_carries_its_own_header():
    rom = image()
    for row in rows(rom):
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
    for row in rows(rom):
        offset = sites(rom, row["start"])[0]
        end = int.from_bytes(rom[offset - 4:offset], "little")
        if 0 < end - row["start"] <= 0x8000:
            assert 0 <= end - row["start"] - (row["stop"] - row["start"]) <= 1
            agreed += 1
    assert agreed == 73


def test_no_two_rows_share_a_byte():
    measured = sorted(rows(image()), key=lambda row: row["start"])
    for first, second in zip(measured, measured[1:]):
        assert first["stop"] <= second["start"], "0x%08X overlaps 0x%08X" % (
            first["start"], second["start"])


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
        test_no_two_rows_share_a_byte()
        test_a_stream_that_states_its_end_ends_where_the_decoder_stops()
        test_a_permuted_lz77_body_is_refused()
        test_a_permuted_huffman_tree_is_refused()
        test_a_tree_that_shares_a_node_is_refused_instead_of_coding_twice()
        test_the_tracked_token_list_is_what_the_image_derives()
        print("PASS test_bios_streams")
