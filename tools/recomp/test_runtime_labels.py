from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "code"))
sys.path.insert(0, os.path.join(ROOT, "tools", "split"))

import runtime_labels

MID = 0x08000146


def doctored(tmp_path, extra="rom,0x%08x,thumb\n" % MID):
    lines = open(runtime_labels.LABELS, encoding="ascii", newline="").read().splitlines()
    lines.append(extra.strip())
    body = sorted(lines[1:], key=lambda line: int(line.split(",")[1], 16))
    path = tmp_path / "RUNTIME_LABELS.csv"
    path.write_text("\n".join([lines[0]] + body) + "\n", encoding="ascii", newline="")
    return str(path)


def test_the_tracked_labels_are_unique_rom_rows_in_address_order():
    labels = runtime_labels.read()
    rows = runtime_labels.run_of()
    assert len(rows) == 6
    assert len(labels) == sum(int(row["entries"]) for row in rows) == 493
    assert set(region for region, _address, _mode in labels) == {"rom"}
    assert set(mode for _region, _address, mode in labels) <= {"thumb", "arm"}
    assert set(mode for _region, _address, mode in labels) == {"thumb", "arm"}
    addresses = [address for _region, address, _mode in labels]
    assert addresses == sorted(addresses)
    assert len(set(addresses)) == len(addresses)


def test_the_two_runs_are_the_attract_record_and_the_gameplay_traversal():
    rows = runtime_labels.run_of()
    assert [row["route"] for row in rows] == ["no-input", "fight-traversal", "attract", "boot-newgame-field-menu", "fight-traversal", "fight-fuzz"]
    assert rows[0]["frames"] == "10800" and rows[0]["entries"] == rows[0]["rom"] == "126"
    assert rows[1]["frames"] == "1630" and rows[1]["entries"] == rows[1]["rom"] == "156"
    assert rows[1]["iwram"] == rows[0]["iwram"] == "0"


def test_the_tracked_labels_are_the_boundary_admitted_ones_beside_their_null():
    figures, problem = runtime_labels.measure()
    assert problem is None
    assert figures["rows"] == figures["admitted"] == 493
    assert figures["null_refused"] == figures["null_samples"] > 0


def test_a_label_inside_an_instruction_is_refused(tmp_path):
    path = doctored(tmp_path)
    figures, problem = runtime_labels.measure(path=path)
    assert figures is None
    assert problem and "0x08000146" in problem and "not an instruction boundary" in problem


def test_a_duplicated_label_is_refused(tmp_path):
    labels = runtime_labels.read()
    path = doctored(tmp_path, "rom,0x%08x,thumb\n" % labels[0][1])
    _figures, problem = runtime_labels.measure(path=path)
    assert problem and "repeats" in problem


def test_a_run_that_records_a_different_count_is_refused(tmp_path):
    path = tmp_path / "RUNTIME_LABELS_RUNS.csv"
    text = open(runtime_labels.RUNS, encoding="ascii", newline="").read()
    path.write_text(text.replace(",126,126,0,", ",127,127,0,"), encoding="ascii", newline="")
    _figures, problem = runtime_labels.measure(runs=str(path))
    assert problem and "494 entries" in problem and "493" in problem


def test_the_run_counts_are_read_as_the_sum_of_their_rows(tmp_path):
    path = tmp_path / "RUNTIME_LABELS_RUNS.csv"
    text = open(runtime_labels.RUNS, encoding="ascii", newline="").read()
    path.write_text(text.replace(",156,156,0,", ",157,157,0,"), encoding="ascii", newline="")
    _figures, problem = runtime_labels.measure(runs=str(path))
    assert problem and "494 entries" in problem


def test_a_run_whose_count_is_not_a_number_is_refused(tmp_path):
    path = tmp_path / "RUNTIME_LABELS_RUNS.csv"
    text = open(runtime_labels.RUNS, encoding="ascii", newline="").read()
    path.write_text(text.replace(",1630,", ",many,"), encoding="ascii", newline="")
    _figures, problem = runtime_labels.measure(runs=str(path))
    assert problem and "'many'" in problem


def test_the_import_unions_into_the_tracked_rows(tmp_path):
    tracked = runtime_labels.read()
    path = tmp_path / "RUNTIME_LABELS.csv"
    path.write_text("region,address,mode\nrom,0x%08x,thumb\n" % tracked[0][1],
                    encoding="ascii", newline="")
    labels = [(region, address, mode) for region, address, mode in tracked[:3]]
    out = runtime_labels.merged(str(path), labels)
    assert len(out) == 3
    assert out == sorted(set(tracked[:3]), key=lambda row: (row[1], row[0]))


def test_a_label_that_is_not_a_row_boundary_is_not_admitted(tmp_path):
    rom = os.path.join(ROOT, "baserom.gba")
    if not os.path.exists(rom):
        pytest.skip("%s is absent, so the census cannot measure an admission" % rom)
    tracked = runtime_labels.read()
    path = tmp_path / "RUNTIME_LABELS.csv"
    path.write_text("region,address,mode\n" + "".join(
        "%s,0x%08x,%s\n" % row for row in tracked), encoding="ascii", newline="")
    labels = [("rom", 0x08000146, "thumb"), ("rom", tracked[0][1], "thumb")]
    kept, refused = runtime_labels.admitted_by_the_census(labels, str(path))
    assert [row[1] for row in kept] == [tracked[0][1]]
    assert [row[1] for row in refused] == [0x08000146]


def test_the_accumulator_is_read_as_region_address_mode(tmp_path):
    path = tmp_path / "measured.fallback.labels"
    path.write_text("gba-labels v1\nrom-sha256 %s\nrom 08001e90 t\niwram 03000100 t\n"
                    "rom 08001e90 t\n" % ("0" * 64), encoding="ascii")
    labels, digest = runtime_labels.imported(str(path))
    assert digest == "0" * 64
    assert labels == [("iwram", 0x03000100, "thumb"), ("rom", 0x08001E90, "thumb")]


def test_an_accumulator_from_another_image_is_refused(tmp_path):
    path = tmp_path / "elsewhere.labels"
    path.write_text("gba-labels v1\nrom-sha256 %s\nrom 08001e90 t\n" % ("1" * 64),
                    encoding="ascii")
    rom = os.path.join(ROOT, "baserom.gba")
    if not os.path.exists(rom):
        pytest.skip("%s is absent, so the image digest cannot be compared" % rom)
    assert "not the accumulator's" in runtime_labels.image_problem("1" * 64)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
