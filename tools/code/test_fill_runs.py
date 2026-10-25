from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import fill_runs

BACKGROUND = 0x11
TEXT = ("\tAREA\tRemainder, CODE, READONLY\n"
        "\tINCBIN\tbaserom.gba_0x0_0x200.extracted\n")


def image(*spans):
    data = bytearray([BACKGROUND]) * 0x200
    for start, blob in spans:
        data[start:start + len(blob)] = blob
    return bytes(data)


def sample():
    return image((0x10, b"\x00" * 0x20), (0x40, b"\xff" * 0x1f),
                 (0x80, b"\x00" * 0x28 + b"\xff" * 0x28))


def test_a_run_of_thirty_two_bytes_is_one_directive_and_a_shorter_run_is_not():
    rom = sample()
    text, pieces, directives = fill_runs.split(rom, TEXT)
    lines = text.splitlines()
    assert directives == [(0x00, 0x20), (0x00, 0x28), (0xFF, 0x28)]
    assert lines[1] == "\tINCBIN\tbaserom.gba_0x0_0x10.extracted"
    assert lines[2] == "\tSPACE\t32"
    assert lines[3] == "\tINCBIN\tbaserom.gba_0x30_0x80.extracted"
    assert rom[0x40:0x60].count(0xFF) == 0x1F
    assert pieces == [(0x0, 0x10), (0x30, 0x80), (0xD0, 0x200)]
    assert [rom[start:stop] for start, stop in pieces] == [
        rom[0x0:0x10], rom[0x30:0x80], rom[0xD0:0x200]]
    assert fill_runs.carried(text) == 0x20 + 0x28 + 0x28


def test_the_mixed_run_is_two_directives_and_the_second_one_is_the_value_loop():
    text, _pieces, _directives = fill_runs.split(sample(), TEXT)
    lines = text.splitlines()
    assert lines[4] == "\tSPACE\t40"
    assert lines[5] == "\tGBLA\tfill_080000a8"
    assert lines[6] == "fill_080000a8\tSETA\t40"
    assert lines[7] == "\tWHILE\tfill_080000a8 > 0"
    assert lines[8] == "\tDCB\t0xFF"
    assert lines[9] == "fill_080000a8\tSETA\tfill_080000a8 - 1"
    assert lines[10] == "\tWEND"
    assert lines[11] == "\tINCBIN\tbaserom.gba_0xd0_0x200.extracted"


def test_the_split_is_idempotent_so_a_second_run_moves_nothing():
    rom = sample()
    once, _pieces, _directives = fill_runs.split(rom, TEXT)
    twice, pieces, directives = fill_runs.split(rom, once)
    assert twice == once and pieces == [] and directives == []
