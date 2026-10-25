from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "gate"))

import gate
import message_rows
import testkit


def image():
    return testkit.rom_bytes(message_rows.ROM, gate.CANONICAL_SHA256, gate.ROM_SIZE)


def span(begin, stop, rom):
    return rom[begin - message_rows.ROM_BASE:stop - message_rows.ROM_BASE]


def extents(measured):
    at, out = message_rows.MESSAGES, []
    for name in measured:
        out.append((at, at + len(name) + 1))
        at += len(name) + 1
    return out


def test_the_code_names_every_message_and_the_six_tile_the_family():
    rom = image()
    names = message_rows.messages(rom)
    starts = [start for start, _name in names]
    assert len(starts) == message_rows.MESSAGE_COUNT
    assert starts[0] == message_rows.MESSAGES
    spans = extents([name for _start, name in names])
    for (_start, stop), next_ in zip(spans, spans[1:] + [(message_rows.MESSAGES_END,)]):
        assert stop == next_[0]
    assert spans[-1][1] == message_rows.MESSAGES_END
    for start, name in names:
        assert all(message_rows.LOW <= byte <= message_rows.HIGH for byte in name)
        assert rom[start - message_rows.ROM_BASE:start - message_rows.ROM_BASE + len(name)] == name
        assert rom[start - message_rows.ROM_BASE + len(name)] == 0


def test_the_code_bounds_the_table_at_the_committed_bounds():
    rom = image()
    measured = message_rows.table(rom)
    assert len(measured["rows"]) == message_rows.ROWS
    assert measured["pad"] == 0x0C
    assert measured["pool"][0][0] == message_rows.TABLE + message_rows.ROWS * \
        message_rows.STRIDE + measured["pad"]
    assert measured["rows"] == sorted(measured["rows"])
    assert max(measured["rows"]) == len(measured["pool"]) - 1
    assert measured["pool"][-1][0] + len(measured["pool"][-1][1]) + 1 == message_rows.TABLE_END


def test_both_families_re_encode_and_are_the_image_bytes():
    rom = image()
    measured = message_rows.census(rom)
    names = message_rows.messages(rom)
    assert message_rows.rebuild_messages(names) == span(message_rows.MESSAGES,
                                                       message_rows.MESSAGES_END, rom)
    assert message_rows.rebuild_table(message_rows.table(rom)) == span(message_rows.TABLE,
                                                                      message_rows.TABLE_END, rom)
    assert measured["bytes"] == 984
    assert measured["messages"] == message_rows.MESSAGE_COUNT
    assert measured["strings"] < measured["rows"]


def test_both_families_are_generated_runs_and_no_slice_covers_them():
    runs = [(start + message_rows.ROM_BASE, start + message_rows.ROM_BASE + length)
            for start, length in gate.generated_ranges(ROOT)]
    for first, last in message_rows.SPANS:
        for start, length in gate.incbin_ranges(ROOT):
            assert not (start + message_rows.ROM_BASE < last and
                        first < start + message_rows.ROM_BASE + length)
        assert [(first, last)] == [(low, high) for low, high in runs
                                   if low <= first and last <= high]


def test_a_moved_message_literal_is_refused():
    rom = bytearray(image())
    for role, address, _mnemonic, text in message_rows.MESSAGE_CITED:
        if address == 0x08000FC0:
            at = message_rows.pool(address, message_rows.immediate(text)) - message_rows.ROM_BASE
            break
    rom[at] ^= 0x02
    assert testkit.refused(lambda: message_rows.messages(bytes(rom)))


def test_a_message_without_its_terminator_is_refused():
    rom = bytearray(image())
    at = message_rows.MESSAGES + 33 - message_rows.ROM_BASE
    assert rom[at] == 0
    rom[at] = ord("A")
    assert testkit.refused(lambda: message_rows.messages(bytes(rom)))


def test_a_bound_advanced_one_message_passes_no_message():
    rom = image()
    names = message_rows.messages(rom)
    spans = extents([name for _start, name in names])
    beyond = message_rows.MESSAGES_END
    stop = rom.index(b"\0", beyond - message_rows.ROM_BASE) + 1
    shifted = [name for _start, name in names][1:] + \
              [rom[beyond - message_rows.ROM_BASE:stop - message_rows.ROM_BASE]]
    at, blob = message_rows.MESSAGES, bytearray()
    for name in shifted:
        blob += name + b"\0"
        at += len(name) + 1
    same = 0
    for low, high in spans:
        if bytes(blob)[low - message_rows.MESSAGES:high - message_rows.MESSAGES] == \
                span(low, high, rom):
            same += 1
    assert same == 0
    assert bytes(blob) != span(message_rows.MESSAGES, message_rows.MESSAGES_END, rom)


def test_a_row_that_names_no_string_is_refused():
    rom = bytearray(image())
    at = message_rows.TABLE + (message_rows.ROWS - 1) * message_rows.STRIDE - \
        message_rows.ROM_BASE
    rom[at:at + 4] = (message_rows.TABLE_END - 0x0C).to_bytes(4, "little")
    assert testkit.refused(lambda: message_rows.table(bytes(rom)))


def test_rows_that_do_not_ascend_are_refused():
    rom = bytearray(image())
    at = message_rows.TABLE - message_rows.ROM_BASE
    rom[at:at + 4] = (message_rows.TABLE_END - 0x22).to_bytes(4, "little")
    assert testkit.refused(lambda: message_rows.table(bytes(rom)))


def test_a_swap_of_two_equal_length_messages_disagrees_in_exactly_two_messages():
    rom = image()
    names = message_rows.messages(rom)
    assert len(names[1][1]) == len(names[3][1])
    swapped = list(names)
    swapped[1] = (names[1][0], names[3][1])
    swapped[3] = (names[3][0], names[1][1])
    blob, same = message_rows.rebuild_messages(swapped), 0
    for start, stop in extents([name for _start, name in names]):
        at, high = start - message_rows.MESSAGES, stop - message_rows.MESSAGES
        if blob[at:high] == span(start, stop, rom):
            same += 1
    assert same == message_rows.MESSAGE_COUNT - 2
    assert blob != span(message_rows.MESSAGES, message_rows.MESSAGES_END, rom)


def test_a_doctored_message_disagrees_in_exactly_one_message():
    rom = image()
    names = message_rows.messages(rom)
    doctored = list(names)
    start, name = doctored[2]
    assert len(name) > 20
    doctored[2] = (start, name[:8] + bytes([name[8] ^ 0x01]) + name[9:])
    blob, same = message_rows.rebuild_messages(doctored), 0
    for begin, stop in extents([name for _start, name in names]):
        at, high = begin - message_rows.MESSAGES, stop - message_rows.MESSAGES
        if blob[at:high] == span(begin, stop, rom):
            same += 1
    assert same == message_rows.MESSAGE_COUNT - 1


def test_a_rom_whose_bytes_differ_is_refused():
    rom = bytearray(image())
    rom[message_rows.TABLE_END - message_rows.ROM_BASE - 2] ^= 0x01
    with pytest.raises(ValueError) as caught:
        message_rows.census(bytes(rom))
    assert "sha1" in str(caught.value)


def test_the_check_re_derives_both_runs():
    image()
    assert message_rows.main(["--check"]) == 0
