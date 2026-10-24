from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import slice_rom


def test_a_slice_is_the_bytes_the_range_names(tmp_path):
    image = tmp_path / "baserom.gba"
    image.write_bytes(bytes(range(256)) * 4)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert slice_rom.main(["baserom.gba", "0x10", "0x20"]) == 0
        written = (tmp_path / "baserom.gba_0x10_0x20.extracted").read_bytes()
    finally:
        os.chdir(previous)
    assert written == bytes(range(0x10, 0x20))


def test_a_short_read_is_refused(tmp_path):
    image = tmp_path / "baserom.gba"
    image.write_bytes(bytes(16))
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert slice_rom.main(["baserom.gba", "0x8", "0x20"]) == 1
    finally:
        os.chdir(previous)


def test_a_backwards_range_is_refused(tmp_path):
    image = tmp_path / "baserom.gba"
    image.write_bytes(bytes(16))
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert slice_rom.main(["baserom.gba", "0x10", "0x8"]) == 1
    finally:
        os.chdir(previous)
