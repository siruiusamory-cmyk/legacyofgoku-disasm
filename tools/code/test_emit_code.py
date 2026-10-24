from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "gate"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import emit_code
import gate
import testkit

CENSUS = ("address,kind,channel,mode,end,reason,flags,evidence\n"
          "0x08000138,start,copy,arm,0x0800013c,-,-,the copy setup\n"
          "0x0800013c,start,call,thumb,0x08000140,-,-,a call\n"
          "0x08000140,start,table,thumb,0x08000144,-,data,a data entry\n"
          "0x08000144,start,pool,thumb,0x08000148,-,-,a pool word\n")


def census(tmp_path, text=CENSUS):
    path = tmp_path / "CENSUS_EVIDENCE.csv"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_the_rule_reads_code_rows_and_leaves_pool_and_data_rows_raw(tmp_path):
    rows = emit_code.census_rows(census(tmp_path))
    assert [row["address"] for row in emit_code.code_rows(rows)] == [0x08000138, 0x0800013C]
    assert emit_code.raw_bytes(rows, []) == []
    assert emit_code.modeless(rows) == []


def test_a_dropped_code_row_is_reported_as_uncovered(tmp_path):
    rows = emit_code.census_rows(census(tmp_path))
    problem = gate.export_problem(rows, [(0x08000138, 4)])
    assert problem and "uncovered" in problem and "0x08000138" in problem, problem


def test_a_code_row_without_a_mode_is_refused(tmp_path):
    rows = emit_code.census_rows(census(tmp_path, CENSUS.replace(
        "0x0800013c,start,call,thumb", "0x0800013c,start,call,-")))
    problem = gate.export_problem(rows, [])
    assert problem and "modeless" in problem and "0x0800013c" in problem, problem


def test_a_complete_export_names_both_counts_as_zero(tmp_path):
    rows = emit_code.census_rows(census(tmp_path))
    assert gate.export_problem(rows, []) is None


def test_the_tracked_census_covers_every_code_row_from_source():
    assert gate.export_problem() is None


def test_a_halfword_transfer_is_not_a_data_processing_instruction():
    rom = testkit.rom_bytes(os.path.join(ROOT, "baserom.gba"), gate.CANONICAL_SHA256,
                            emit_code.ROM_SIZE)
    assert emit_code.decode(rom, 0x0800020C, "arm") == ("STRH", "r0, [r3, #0x2]", 4)
    assert emit_code.decode(rom, 0x080002C0, "thumb") == ("PUSH", "{r4, lr}", 2)
