from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lints


def test_the_recorded_readability_baseline_is_the_tree_it_sits_in():
    baseline = lints.read_source("tools/lint/READABILITY_BASELINE.txt")
    assert lints.readability_findings(baseline, lints.address_literal_counts()) == []
    assert lints.address_literal_counts() == {"ram": 0, "hardware": 0}


def test_a_raw_ram_literal_above_the_baseline_is_a_finding():
    found = lints.readability_findings("ram=0\nhardware=0\n", {"ram": 1, "hardware": 0})
    assert found and "above the baseline" in found[0][1], found


def test_a_baseline_the_tree_no_longer_meets_is_a_finding():
    found = lints.readability_findings("ram=2\nhardware=0\n", {"ram": 1, "hardware": 0})
    assert found and "must lower" in found[0][1], found


def test_an_address_literal_is_counted_per_class(tmp_path, monkeypatch):
    directory = os.path.join(str(tmp_path), "asm")
    os.makedirs(directory)
    with open(os.path.join(directory, "code.s"), "w", encoding="utf-8") as handle:
        handle.write("\tDCD\t0x03007FA0\n\tDCD\t0x04000000\n\tINCBIN\tbaserom.gba_0x0_0xc0\n")
    monkeypatch.setattr(lints, "ROOT", str(tmp_path))
    assert lints.address_literal_counts() == {"ram": 1, "hardware": 1}


def test_the_equate_files_are_not_counted_against_the_ratchet(tmp_path, monkeypatch):
    directory = os.path.join(str(tmp_path), "asm")
    os.makedirs(directory)
    with open(os.path.join(directory, "memory.s"), "w", encoding="utf-8") as handle:
        handle.write("Sp_Irq\tEQU\t0x03007FA0\n")
    monkeypatch.setattr(lints, "ROOT", str(tmp_path))
    assert lints.address_literal_counts() == {"ram": 0, "hardware": 0}


def test_the_recorded_naming_baseline_is_the_tree_it_sits_in():
    assert lints.naming_findings(lints.read_source("tools/lint/NAMING_BASELINE.txt")) == []
    assert lints.naming_live() == 0


def test_a_new_address_named_symbol_above_the_baseline_is_a_finding(monkeypatch):
    monkeypatch.setattr(lints, "naming_live", lambda: 3)
    found = lints.naming_findings("0\n")
    assert found and "above the baseline" in found[0][1], found


def test_an_absent_baseline_count_is_a_finding():
    found = lints.naming_findings("")
    assert found and "expected" in found[0][1], found


def test_a_readme_number_the_gate_does_not_print_is_a_finding():
    text = "0.0014 % of the ROM (120 of 8,388,608 bytes) from python tools\\gate\\gate.py\n"
    assert lints.readme_numbers_findings(text, 120, 8388608, "0.0014") == []
    wrong = text.replace("120 of", "121 of")
    found = lints.readme_numbers_findings(wrong, 120, 8388608, "0.0014")
    assert found and "not the gate's 120" in found[0][1], found


def test_a_readme_carrying_the_share_with_and_without_fill_is_clean():
    text = ("72.1966 % with fill and 60.2846 % without, 6,056,196 of 8,388,608 bytes from "
            "python tools\\gate\\gate.py\n")
    assert lints.readme_numbers_findings(text, 6056196, 8388608, "72.1966", "60.2846") == []
    found = lints.readme_numbers_findings(text.replace("60.2846", "60.2845"),
                                          6056196, 8388608, "72.1966", "60.2846")
    assert found and "60.2846" in found[0][1], found


def test_a_readme_code_start_count_the_census_does_not_carry_is_a_finding():
    text = "![Code starts](https://img.shields.io/badge/code%20starts-1520-blueviolet.svg)\n"
    assert lints.readme_starts_findings(text, 1520) == []
    found = lints.readme_starts_findings(text.replace("1520", "1521"), 1520)
    assert found and "not the census's 1520" in found[0][1], found


def test_the_generated_remainder_listing_may_exceed_the_tracked_file_size_limit(
        tmp_path, monkeypatch):
    directory = os.path.join(str(tmp_path), "asm")
    os.makedirs(directory)
    for name in ("remainder.s", "pasted.s"):
        with open(os.path.join(directory, name), "wb") as handle:
            handle.write(b"x" * (1024 * 1024 + 1))
    monkeypatch.setattr(lints, "ROOT", str(tmp_path))
    monkeypatch.setattr(lints, "tracked_files",
                        lambda: ["asm/remainder.s", "asm/pasted.s"])
    found = lints.tracked_rom_findings()
    assert [detail for name, detail in found] == [
        "asm/pasted.s: 1048577 tracked bytes outside assets/"]


def test_a_bare_interpreter_call_is_a_finding():
    interpreter = "c" + "md"
    fixture = interpreter + " /c python tools\\gate\\gate.py -q\n"
    found = lints.bare_interpreter("tools/build.cmd", fixture)
    assert found and found[0][0] == "P-159-bare-interpreter"


def test_a_repository_path_inserted_into_the_module_path_is_a_finding():
    fixture = "sys.path.insert(0, r'C:" + "\\outside\\tools')\n"
    found = lints.out_of_repo_module_path("tools/x.py", fixture)
    assert found and found[0][0] == "P-148-repo-module-path"


def test_a_pool_in_a_module_with_a_main_guard_is_clean():
    text = "import multiprocessing\nif __name__ == '__main__':\n    pass\n"
    assert lints.pool_without_guard("tools/x.py", text) == []
