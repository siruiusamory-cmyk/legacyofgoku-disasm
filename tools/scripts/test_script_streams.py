from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import script_streams
import testkit

DIGEST = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
POPULATION = (282, 17332, 50087, 118634, 18)


def image():
    return testkit.rom_bytes(script_streams.ROM, DIGEST, 0x800000)


def tables():
    return (open(script_streams.TABLE, encoding="utf-8", newline="").read(),
            open(script_streams.OPS, encoding="utf-8", newline="").read())


def test_the_population_is_the_pinned_rows():
    records = script_streams.population(image())
    measured = (len(records),
                sum(record["frames"] for record in records),
                sum(len(rows) for record in records for rows in record["segments"]),
                sum(record["span"] for record in records),
                len(set(record["row"] for record in records)))
    assert measured == POPULATION


def test_every_record_is_the_image_bytes_and_no_two_records_overlap():
    rom = image()
    spans = []
    for record in script_streams.population(rom):
        offset = record["address"] - script_streams.ROM_BASE
        assert record["blob"] == rom[offset:offset + record["span"]]
        spans.append((record["address"], record["stop"]))
    spans.sort()
    for (first, last), (next_first, _next_last) in zip(spans, spans[1:]):
        assert last <= next_first, "0x%08X runs into 0x%08X" % (first, next_first)


def test_every_record_start_is_a_word_its_own_table_holds():
    rom = image()
    for row in script_streams.descriptor_rows(rom):
        words = [script_streams.word_at(rom, row["table"] + 4 * i) for i in range(row["width"])]
        for start in sorted(row["starts"]):
            assert words.count(start) >= 1, "0x%08X is in no table" % start


def test_the_records_of_a_row_tile_its_band_and_stop_at_its_word_table():
    rom = image()
    for row in script_streams.descriptor_rows(rom):
        starts = sorted(row["starts"])
        ends = [script_streams.decode(rom, start)["stop"] for start in starts]
        for last, next_first in zip(ends, starts[1:]):
            assert last == next_first, "the row %d does not tile at 0x%08X" % (row["index"], last)
        assert 0 <= row["table"] - ends[-1] <= 3


def test_a_mode_above_one_carries_the_images_own_flag_byte():
    rom = image()
    agreed = 0
    for record in script_streams.population(rom):
        for rows in record["segments"]:
            for _segment, _slot, mode, flags, _fields in rows:
                if mode < 2:
                    continue
                assert flags == script_streams.byte_at(rom, script_streams.FLAGS + mode)
                agreed += 1
    assert agreed > 0


def test_a_table_whose_slots_are_permuted_passes_no_record():
    rom = image()
    tracked = script_streams.load_records(*tables())
    permuted = []
    for record in tracked:
        segments = []
        for rows in record["segments"]:
            segments.append([(segment, (slot + 1) % script_streams.SLOTS, mode, flags, fields)
                             for segment, slot, mode, flags, fields in rows])
        permuted.append({"address": record["address"], "frames": record["frames"],
                         "span": record["span"], "segments": segments,
                         "blob": script_streams.encode({"address": record["address"],
                                                        "frames": record["frames"],
                                                        "segments": segments})})
    passing = [record for record in permuted
               if record["blob"] == rom[record["address"] - script_streams.ROM_BASE:
                                        record["address"] - script_streams.ROM_BASE
                                        + record["span"]]]
    assert len(tracked) == POPULATION[0]
    assert passing == []


def test_a_doctored_operand_is_refused():
    rom = image()
    records_text, ops_text = tables()
    lines = ops_text.splitlines()
    for index in range(1, len(lines)):
        fields = lines[index].split(",")
        if len(fields) >= 9 and fields[5]:
            fields[5] = "%02x" % ((int(fields[5], 16) ^ 0xFF))
            lines[index] = ",".join(fields)
            break
    else:
        raise AssertionError("no row carries a field")
    tracked = script_streams.load_records(records_text, "\n".join(lines) + "\n")
    differs = [record for record in tracked
               if record["blob"] != rom[record["address"] - script_streams.ROM_BASE:
                                        record["address"] - script_streams.ROM_BASE
                                        + record["span"]]]
    assert len(differs) == 1


def test_the_tracked_tables_are_what_the_image_derives():
    testkit.rom_bytes(script_streams.ROM, DIGEST, 0x800000)
    assert script_streams.main(["--check"]) == 0


if __name__ == "__main__":
    if os.path.exists(script_streams.ROM):
        test_the_population_is_the_pinned_rows()
        test_every_record_is_the_image_bytes_and_no_two_records_overlap()
        test_every_record_start_is_a_word_its_own_table_holds()
        test_the_records_of_a_row_tile_its_band_and_stop_at_its_word_table()
        test_a_mode_above_one_carries_the_images_own_flag_byte()
        test_a_table_whose_slots_are_permuted_passes_no_record()
        test_a_doctored_operand_is_refused()
        test_the_tracked_tables_are_what_the_image_derives()
        print("PASS test_script_streams")
