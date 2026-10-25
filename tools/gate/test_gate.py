from __future__ import annotations

import contextlib
import hashlib
import io
import os
import re
import shutil
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "research"))

import gate
import pointer_rows


def in_scratch(call):
    root = tempfile.mkdtemp(prefix="gate-test-")
    previous = gate.ROOT
    gate.ROOT = root
    try:
        return call(root)
    finally:
        gate.ROOT = previous
        shutil.rmtree(root, ignore_errors=True)


def made(root, name, content=b"x"):
    path = os.path.join(root, *name.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(content)
    return path


def require_cmd():
    if sys.platform != "win32":
        pytest.skip("cmd.exe is absent, so the build step cannot run")


def pointer_bytes():
    text = open(pointer_rows.ASM, encoding="utf-8", newline="").read()
    items = pointer_rows.tokens(text, pointer_rows.code_bounds())
    return sum(size for kind, _position, size, _line in items if kind == "dcd")


def test_the_source_count_is_the_slices_and_the_rest():
    ranges = gate.incbin_ranges()
    raw = sum(length for _start, length in ranges)
    assert ranges and gate.interval_problems(ranges) == []
    assert ranges[0][0] == 0
    assert ranges[-1][0] + ranges[-1][1] == gate.ROM_SIZE
    assert raw + gate.source_bytes() == gate.ROM_SIZE
    rows = gate.emit_code.census_rows()
    emitted = sum(row["end"] - row["address"] for row in gate.emit_code.code_rows(rows))
    generated = sum(length for _start, length in gate.generated_ranges())
    assert pointer_bytes() > 0
    assert gate.source_bytes() == 0x78 + emitted + generated + pointer_bytes()


def test_a_double_counted_interval_is_refused_instead_of_passing_as_arithmetic():
    problems = gate.interval_problems([(0x100, 0x20), (0x110, 0x10)])
    assert problems and "overlaps" in problems[0]


def test_an_interval_outside_the_image_is_refused():
    problems = gate.interval_problems([(gate.ROM_SIZE - 8, 0x10)])
    assert problems and "outside" in problems[0]


def test_the_accounted_class_totals_are_the_image_and_a_perturbed_one_fails():
    raw = sum(length for _start, length in gate.incbin_ranges())
    source = gate.source_bytes()
    assert gate.accounted(raw, 0, source) == (gate.ROM_SIZE, None)
    total, problem = gate.accounted(raw + 2, 0, source)
    assert total == gate.ROM_SIZE + 2 and problem is not None, problem


def image_of(code=b"ALGE", size=0x100):
    data = bytearray(size)
    data[0xAC:0xB0] = code
    return bytes(data)


def identity_files(tmp_path, data):
    image = tmp_path / "baserom.gba"
    image.write_bytes(data)
    sha1_file = tmp_path / "baserom.sha1"
    sha1_file.write_text(hashlib.sha1(data).hexdigest(), encoding="ascii")
    return str(image), str(sha1_file)


def test_the_rom_identity_gate_refuses_an_absent_image_a_short_one_and_a_wrong_digest(
        monkeypatch, tmp_path):
    data = image_of()
    image, sha1_file = identity_files(tmp_path, data)
    monkeypatch.setattr(gate, "ROM_SIZE", 0x100)
    assert "absent" in gate.retail_problem(str(tmp_path / "gone.gba"), sha1_file)
    assert gate.retail_problem(image, sha1_file) is None
    monkeypatch.setattr(gate, "ROM_SIZE", 0x200)
    assert "not the image's" in gate.retail_problem(image, sha1_file)
    monkeypatch.setattr(gate, "ROM_SIZE", 0x100)
    changed = bytearray(data)
    changed[0] = 1
    image_wrong = tmp_path / "changed.gba"
    image_wrong.write_bytes(bytes(changed))
    assert "sha1" in gate.retail_problem(str(image_wrong), sha1_file)


def test_the_rom_identity_gate_refuses_another_game_code(monkeypatch, tmp_path):
    data = image_of(code=b"ALFE")
    image, sha1_file = identity_files(tmp_path, data)
    monkeypatch.setattr(gate, "ROM_SIZE", 0x100)
    problem = gate.retail_problem(image, sha1_file)
    assert problem and "game code" in problem, problem
    assert gate.retail_problem(*identity_files(tmp_path, image_of())) is None


def rebuild_with(script, image_created=False):
    def check(root):
        step = made(root, "step.cmd", script.encode())
        previous = gate.BUILD, gate.LOG, gate.IMAGE
        gate.BUILD, gate.LOG = step, os.path.join(root, "rebuild.log")
        gate.IMAGE = (made(root, "build/ROM_START", b"x") if image_created
                      else os.path.join(root, "no-such-image"))
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                rc = gate.rebuild()
        finally:
            gate.BUILD, gate.LOG, gate.IMAGE = previous
        return rc, out.getvalue()
    return in_scratch(check)


def test_a_failed_tools_lowercase_error_line_reaches_the_gate_summary():
    require_cmd()
    rc, printed = rebuild_with("@echo off\r\necho Fatal error: L6031U: Could not open scatter "
                               "description file\r\nexit /b 1\r\n")
    assert rc == 1
    assert "Fatal error: L6031U" in printed


def test_a_step_reporting_a_nonzero_exit_fails_the_build_it_still_produced():
    require_cmd()
    rc, printed = rebuild_with("@echo off\r\necho armasm_log1_exit=1\r\necho armlink_exit=0\r\n"
                               "exit /b 0\r\n", image_created=True)
    assert rc == 1
    assert "FAILED STEPS=armasm_log1" in printed


def test_the_purge_removes_every_object_and_the_image_and_nothing_else():
    def check(root):
        made(root, "build/log1.o")
        made(root, "build/log1.axf")
        made(root, "build/bg.pal")
        image = made(root, "build/ROM_START")
        previous = gate.IMAGE
        gate.IMAGE = image
        try:
            gate.purge_outputs()
        finally:
            gate.IMAGE = previous
        return [name for name in sorted(os.listdir(os.path.join(root, "build")))]
    assert in_scratch(check) == ["bg.pal", "log1.axf"]


def test_the_cold_start_purges_the_slices_and_runs_the_extract_step():
    require_cmd()
    def check(root):
        made(root, "baserom.gba_0x0_0xc0.extracted")
        made(root, "build/log1.o")
        made(root, "baserom.gba")
        step = made(root, "cold-step.cmd", b"@echo off\r\nexit /b 0\r\n")
        previous = gate.EXTRACT, gate.IMAGE
        gate.EXTRACT = step
        gate.IMAGE = os.path.join(root, "build", "ROM_START")
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                rc = gate.cold_start()
        finally:
            gate.EXTRACT, gate.IMAGE = previous
        return rc, out.getvalue(), {
            "slice": os.path.exists(os.path.join(root, "baserom.gba_0x0_0xc0.extracted")),
            "object": os.path.exists(os.path.join(root, "build", "log1.o")),
            "retail": os.path.exists(os.path.join(root, "baserom.gba")),
        }
    rc, printed, state = in_scratch(check)
    assert rc == 0
    assert "1 INCBIN slice(s)" in printed
    assert state == {"slice": False, "object": False, "retail": True}


def gate_run(monkeypatch, tmp_path, canonical=None, recomp=None):
    image = tmp_path / "ROM_START"
    image.write_bytes(bytes(gate.ROM_SIZE))
    monkeypatch.setattr(gate, "IMAGE", str(image))
    monkeypatch.setattr(gate, "RETAIL", str(image))
    monkeypatch.setattr(gate, "retail_problem", lambda path=None, sha1_file=None: None)
    monkeypatch.setattr(gate, "rebuild", lambda quiet=False: 0)
    monkeypatch.setattr(gate, "tracked_rom_slices", lambda retail, root=None: [])
    monkeypatch.setattr(gate, "missing_slices", lambda root=None: [])
    monkeypatch.setattr(gate, "identity_ranges", lambda: [])
    monkeypatch.setattr(gate.lints, "run", lambda: [])
    monkeypatch.setattr(gate.lints, "run_cited_tests",
                        lambda pairs, launch=None: dict((pair, (0, "")) for pair in pairs))
    monkeypatch.setattr(gate, "recomp_export",
                        recomp or (lambda root=None:
                                   ("RECOMP PASS rows=0 uncovered=0 modeless=0", None)))
    monkeypatch.setattr(gate.sys, "argv", ["gate.py"])
    if canonical is not None:
        monkeypatch.setattr(gate, "CANONICAL_SHA256", canonical)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = gate.main()
    return rc, out.getvalue().splitlines()


def test_main_prints_the_digest_the_counted_split_and_the_verdict(monkeypatch, tmp_path):
    rc, lines = gate_run(monkeypatch, tmp_path,
                         hashlib.sha256(bytes(gate.ROM_SIZE)).hexdigest())
    assert rc == 0
    assert [line for line in lines if line.startswith("DIGEST ")] == ["DIGEST MATCH"]
    ranges = gate.incbin_ranges()
    raw = sum(length for _start, length in ranges)
    covered = bytearray(gate.ROM_SIZE)
    for start, length in ranges:
        covered[start:start + length] = b"\x01" * length
    source = covered.count(0)
    assert [line for line in lines if line.startswith("raw-data=")] == [
        "raw-data=%d (%.4f %%)" % (raw, 100.0 * raw / gate.ROM_SIZE)]
    assert [line for line in lines if line.startswith("source=")] == [
        "source=%d of %d (%.4f %%)"
        % (source, gate.ROM_SIZE, 100.0 * source / gate.ROM_SIZE)]
    accounted = [line for line in lines if line.startswith("accounted=")]
    assert len(accounted) == 1
    parts = re.search(r"raw (\d+) \+ identity (\d+) \+ source (\d+)", accounted[0])
    assert parts is not None
    assert sum(int(part) for part in parts.groups()) == gate.ROM_SIZE
    assert " of %d (100.0000 %%)" % gate.ROM_SIZE in accounted[0]
    assert lines[-1] == "GATE PASS"


def test_the_gate_refuses_an_export_check_that_reports_a_row_defect(monkeypatch, tmp_path):
    defect = ("tools/recomp/RECOMP_INPUTS.toml: 1 census start(s) have no row, the first "
              "0x08000000")
    rc, lines = gate_run(monkeypatch, tmp_path,
                         hashlib.sha256(bytes(gate.ROM_SIZE)).hexdigest(),
                         recomp=lambda root=None: (None, defect))
    assert rc == 1
    assert [line for line in lines if line.startswith("GATE FAIL: ")] == ["GATE FAIL: " + defect]


def test_the_gate_fails_when_the_image_is_not_the_retail_digest(monkeypatch, tmp_path):
    rc, lines = gate_run(monkeypatch, tmp_path)
    assert rc == 1
    assert [line for line in lines if line.startswith("DIGEST ")] == ["DIGEST MISMATCH"]
    assert lines[-1] == "GATE FAIL"


CENSUS_HEADER = "address,kind,channel,mode,end,reason,flags,evidence"
CLOSED_ROWS = "\n".join([
    CENSUS_HEADER,
    "0x08000100,start,vector,thumb,0x08000104,-,-,the reset vector",
    "0x08000108,start,copy,arm,0x0800010c,-,-,the copy setup",
    "0x0800010a,start,call,thumb,0x0800010e,-,-,a call",
    "0x08000110,start,pool,thumb,0x08000114,pool,-,a pool word",
    "0x08000118,start,table,thumb,0x0800011c,next-start,-,a pointer run",
    "0x08000120,start,repeated,thumb,0x08000124,no-return,-,a repeated word",
    "0x08000128,start,runtime,thumb,0x0800012c,-,-,a recorded entry",
]) + "\n"


def test_a_closed_census_passes_and_an_open_bound_is_refused(tmp_path):
    closed = tmp_path / "closed.csv"
    closed.write_text(CLOSED_ROWS, encoding="utf-8")
    assert gate.census_problem(str(closed)) is None
    opened = tmp_path / "opened.csv"
    opened.write_text(CLOSED_ROWS.replace("0x08000118,start,table,thumb,0x0800011c",
                                          "0x08000118,start,table,thumb,-"), encoding="utf-8")
    problem = gate.census_problem(str(opened))
    assert problem and "0x08000118" in problem and "open bound" in problem, problem


def test_a_census_missing_a_seed_channel_is_refused(tmp_path):
    dropped = tmp_path / "dropped.csv"
    rows = [line for line in CLOSED_ROWS.splitlines() if ",pool," not in line]
    dropped.write_text("\n".join(rows) + "\n", encoding="utf-8")
    problem = gate.census_problem(str(dropped))
    assert problem and "pool" in problem, problem


def test_the_tracked_census_carries_every_start_and_every_channel():
    assert os.path.exists(gate.CENSUS)
    assert gate.census_problem() is None


if __name__ == "__main__":
    test_the_source_count_is_the_slices_and_the_rest()
    test_a_double_counted_interval_is_refused_instead_of_passing_as_arithmetic()
    test_an_interval_outside_the_image_is_refused()
    test_the_accounted_class_totals_are_the_image_and_a_perturbed_one_fails()
    print("PASS test_gate")
