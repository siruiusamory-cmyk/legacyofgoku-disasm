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
import dialogue_runtime
import gate
import testkit


def image():
    return testkit.rom_bytes(dialogue_runtime.ROM, gate.CANONICAL_SHA256, gate.ROM_SIZE)


def at(address):
    return address - dialogue_runtime.ROM_BASE


def test_the_reader_admits_the_retail_image():
    measured = dialogue_runtime.measure(image())
    assert measured["cites"] == len(dialogue_runtime.CITED)
    assert measured["records"] == dialogue_rows.ROWS
    assert measured["nodes"] == 988
    assert measured["pages"] == dialogue_runtime.PAGES
    assert measured["stride"] == dialogue_runtime.PAGE_STRIDE
    assert measured["staging"] == dialogue_runtime.STAGING
    assert measured["slots"] == dialogue_runtime.STATE_SLOTS
    assert measured["pads"] == (0x06, 0x0E, 0x16, 0x1E)
    assert measured["scene"] == dialogue_runtime.SCENE


def test_the_page_literal_names_the_object_whose_stride_the_literals_follow():
    rom = image()
    assert dialogue_runtime.page_bases(rom) == [dialogue_runtime.PAGE +
                                                dialogue_runtime.PAGE_STRIDE * index
                                                for index in range(dialogue_runtime.PAGES)]


def test_the_flush_subtrahend_is_the_staging_base_negated():
    rom = image()
    base = dialogue_runtime.word(rom, dialogue_runtime.STAGING_LITERAL)
    negated = dialogue_runtime.word(rom, dialogue_runtime.CURSOR_LITERAL)
    assert base == dialogue_runtime.STAGING
    assert negated == (0 - base) & 0xFFFFFFFF
    assert rom.count(base.to_bytes(4, "little")) == 2


def test_every_state_slot_names_a_target_that_decodes():
    rom = image()
    derived = dialogue_runtime.states(rom)
    assert derived == dialogue_runtime.STATE_TARGETS
    for target in derived:
        assert target % 2 == 0


def test_record_66_runs_once_then_repeats_from_the_terminal_successor():
    rom = image()
    scene = dialogue_runtime.scene(rom)
    assert scene["base"] == 0x081647F4
    assert scene["nodes"] == 39
    assert scene["visited"] == tuple(range(11))
    assert scene["cycle"] == 8
    assert scene["terminals"] == (7, 10, 12, 14, 19, 24, 26, 34, 36, 38)
    assert scene["last"] == (6, 9)


def test_a_changed_cited_instruction_is_refused():
    rom = bytearray(image())
    role, address, _mnemonic, _text = dialogue_runtime.CITED[0]
    assert role == "talk-index"
    rom[at(address)] ^= 0x01
    with pytest.raises(ValueError) as caught:
        dialogue_runtime.measure(bytes(rom))
    assert "0x%08X" % address in str(caught.value)


def test_a_moved_page_literal_is_refused():
    rom = bytearray(image())
    address = dialogue_runtime.PAGE_BASE_LITERAL
    rom[at(address):at(address) + 4] = dialogue_runtime.PAGE.to_bytes(4, "little")
    rom[at(address)] ^= 0x04
    assert testkit.refused(lambda: dialogue_runtime.page_bases(bytes(rom)))


def test_a_flush_that_negates_the_wrong_span_is_refused():
    rom = bytearray(image())
    address = dialogue_runtime.CURSOR_LITERAL
    rom[at(address):at(address) + 4] = ((0 - dialogue_runtime.STAGING - 4) & 0xFFFFFFFF) \
        .to_bytes(4, "little")
    assert testkit.refused(lambda: dialogue_runtime.staging(bytes(rom)))


def test_a_matrix_store_outside_the_pad_offsets_is_refused():
    rom = bytearray(image())
    address = dialogue_runtime.MATRIX_PADS[0][0]
    rom[at(address):at(address) + 2] = (0x8000).to_bytes(2, "little")
    assert testkit.refused(lambda: dialogue_runtime.matrices(bytes(rom)))


def test_a_state_slot_that_moves_by_one_halfword_is_refused():
    rom = bytearray(image())
    address = dialogue_runtime.STATES + 4 * 2
    rom[at(address):at(address) + 4] = (0xFFFF645B).to_bytes(4, "little")
    assert testkit.refused(lambda: dialogue_runtime.states(bytes(rom)))


def test_a_rom_whose_bytes_differ_is_refused():
    rom = bytearray(image())
    rom[at(dialogue_runtime.STATES) + 3] ^= 0x01
    with pytest.raises(ValueError) as caught:
        dialogue_runtime.measure(bytes(rom))
    assert "sha1" in str(caught.value) or "state slots" in str(caught.value)


def test_the_check_reads_the_retail_image_and_writes_nothing():
    image()
    before = {}
    for name in sorted(os.listdir(HERE)):
        if name.endswith(".py"):
            before[name] = os.path.getmtime(os.path.join(HERE, name))
    assert dialogue_runtime.main(["--check"]) == 0
    after = dict((name, os.path.getmtime(os.path.join(HERE, name)))
                 for name in sorted(os.listdir(HERE)) if name.endswith(".py"))
    assert after == before
