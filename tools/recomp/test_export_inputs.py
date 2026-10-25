from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "code"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import emit_code
import export_inputs
import testkit

DIGEST = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
CENSUS = ("address,kind,channel,mode,end,reason,flags,evidence\n"
          "0x08000138,start,copy,arm,0x0800013c,-,-,the copy setup\n"
          "0x0800013c,start,call,thumb,0x08000140,-,-,a call\n"
          "0x08000140,start,table,thumb,0x08000144,-,data,a data entry\n"
          "0x08000144,start,pool,thumb,0x08000148,-,-,a pool word\n")


def census_rows(tmp_path, text=CENSUS):
    path = tmp_path / "CENSUS_EVIDENCE.csv"
    path.write_text(text, encoding="utf-8")
    return emit_code.census_rows(str(path))


def small_text(tmp_path, rows=None):
    rows = census_rows(tmp_path) if rows is None else rows
    return export_inputs.text_of(export_inputs.rows_of(rows), "0" * 40, "0" * 32, [])


def test_a_code_row_and_a_raw_row_carry_the_census_channel_and_the_raw_reason(tmp_path):
    records = export_inputs.rows_of(census_rows(tmp_path))
    assert [(record["section"], record["origin"], record.get("reason")) for record in records] == [
        ("code", "copy", None),
        ("code", "call", None),
        ("raw", "table", "data"),
        ("raw", "pool", "pool"),
    ]
    assert [record["end"] for record in records] == [0x0800013C, 0x08000140, 0x08000144,
                                                     0x08000148]


def test_a_complete_export_names_no_defect(tmp_path):
    rows = census_rows(tmp_path)
    assert export_inputs.audit(small_text(tmp_path, rows), rows) == []


def test_a_dropped_row_is_refused_as_uncovered(tmp_path):
    rows = census_rows(tmp_path)
    text = small_text(tmp_path, rows)
    dropped = text.replace("[[code]]\naddr = 0x0800013c\nmode = \"thumb\"\nsize = 4\n"
                           "end = 0x08000140\norigin = \"call\"\n\n", "")
    problem = export_inputs.audit(dropped, rows)
    assert problem and "have no row" in problem[0] and "0x0800013C" in problem[0], problem


def test_a_duplicated_row_is_refused(tmp_path):
    rows = census_rows(tmp_path)
    text = small_text(tmp_path, rows)
    block = "[[code]]\naddr = 0x08000138\nmode = \"arm\"\nsize = 4\nend = 0x0800013c\n" \
            "origin = \"copy\"\n\n"
    problem = export_inputs.audit(text + block, rows)
    assert problem and "repeat an address" in problem[0] and "0x08000138" in problem[0], problem


def test_an_open_row_is_refused(tmp_path):
    rows = census_rows(tmp_path)
    text = small_text(tmp_path, rows).replace("end = 0x08000144", "end = 0x08000140")
    problem = export_inputs.audit(text, rows)
    assert problem and "open bound" in problem[0] and "0x08000140" in problem[0], problem


def test_a_size_that_does_not_reach_its_own_end_is_refused(tmp_path):
    rows = census_rows(tmp_path)
    text = small_text(tmp_path, rows).replace("size = 4\nend = 0x0800013c",
                                             "size = 2\nend = 0x0800013c")
    problem = export_inputs.audit(text, rows)
    assert problem and "not its own bound" in problem[0], problem


def test_a_row_without_a_mode_is_refused(tmp_path):
    rows = census_rows(tmp_path)
    text = small_text(tmp_path, rows).replace("mode = \"arm\"", "mode = \"-\"")
    problem = export_inputs.audit(text, rows)
    assert problem and "mode outside" in problem[0], problem


def test_an_end_the_census_does_not_carry_is_refused(tmp_path):
    rows = census_rows(tmp_path)
    text = small_text(tmp_path, rows)
    changed = text.replace("addr = 0x08000138\nmode = \"arm\"\nsize = 4\nend = 0x0800013c",
                           "addr = 0x08000138\nmode = \"arm\"\nsize = 8\nend = 0x08000140", 1)
    problem = export_inputs.audit(changed, rows)
    assert problem and "the census says" in problem[0], problem


def test_the_tracked_export_carries_every_census_start_once_with_a_bound_and_a_mode():
    rows = emit_code.census_rows()
    assert os.path.exists(export_inputs.OUT)
    text = open(export_inputs.OUT, encoding="ascii", newline="").read()
    found = export_inputs.found_rows(text)
    assert export_inputs.audit(text, rows) == []
    assert len(found) == len(rows) == len(set(record["addr"] for record in found))
    assert all(record["end"] > record["addr"] for record in found)
    assert all(record["mode"] in export_inputs.MODES for record in found)


def test_the_tracked_export_is_the_export_this_tree_derives():
    testkit.rom_bytes(export_inputs.ROM, DIGEST, 8388608)
    assert export_inputs.check() is None


def test_the_tracked_export_carries_the_recorded_starts_as_runtime_rows():
    found = export_inputs.found_rows(open(export_inputs.OUT, encoding="ascii", newline="").read())
    runtime = [record for record in found if record["origin"] == "runtime"]
    assert len(runtime) == 282
    code = [record for record in runtime if record["section"] == "code"]
    raw = [record for record in runtime if record["section"] == "raw"]
    assert len(code) == 280 and len(raw) == 2
    assert set(record["mode"] for record in code) == {"thumb", "arm"}
    assert all(record["reason"] == "data" for record in raw)
    assert sorted(record["addr"] for record in raw) == [0x08004D5C, 0x08008016]


def doctored(text, name):
    if name == "missing":
        start = text.index("[[code]]\naddr = 0x08000204")
        return text[:start] + text[text.index("[[code]]", start + 1):]
    if name == "duplicate":
        start = text.index("[[code]]\naddr = 0x08000138")
        return text + text[start:text.index("[[code]]", start + 1)]
    if name == "open":
        return text.replace("addr = 0x08000000\nmode = \"arm\"\nsize = 4\nend = 0x08000004",
                            "addr = 0x08000000\nmode = \"arm\"\nsize = 0\nend = 0x08000000", 1)
    raise AssertionError(name)


def test_a_doctored_export_copy_is_refused_three_ways(tmp_path):
    testkit.rom_bytes(export_inputs.ROM, DIGEST, 8388608)
    text = export_inputs.render()
    expected = {"missing": "have no row", "duplicate": "repeat an address",
                "open": "open bound"}
    for name, wanted in expected.items():
        body = doctored(text, name)
        assert body != text, name
        path = tmp_path / ("%s.toml" % name)
        path.write_text(body, encoding="ascii", newline="")
        problem = export_inputs.check(str(path))
        assert problem and wanted in problem, (name, problem)


def test_the_export_the_image_derives_names_the_regions_step():
    testkit.rom_bytes(export_inputs.ROM, DIGEST, 8388608)
    text = export_inputs.render()
    assert "[[code_copy]]\nruntime_start = 0x03003bc0\nsource_start = 0x08000138\n" \
           "size = 0x13c\n" in text
    assert "entry_pc = 0x08000000" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
