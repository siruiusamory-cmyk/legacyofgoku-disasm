import csv
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "lint"))
sys.path.insert(0, os.path.join(ROOT, "tools", "code"))

import emit_code
import fill_runs
import lints

IMAGE_NAME = "ROM_START"
GAME_CODE = b"ALGE"
CANONICAL_SHA256 = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
ROM_SIZE = 8388608
BUILD = os.path.join(ROOT, "rebuild.cmd")
EXTRACT = os.path.join(ROOT, "extract.cmd")
IMAGE = os.path.join(ROOT, "build", IMAGE_NAME)
RETAIL = os.path.join(ROOT, "baserom.gba")
SHA1_FILE = os.path.join(ROOT, "baserom.sha1")
LOG = os.path.join(ROOT, "work", "rebuild.log")
CENSUS = os.path.join(ROOT, "tools", "code", "CENSUS_EVIDENCE.csv")
CENSUS_CHANNELS = ("vector", "copy", "call", "pool", "table", "repeated", "runtime")
CENSUS_REASONS = ("-", "next-start", "pool", "no-return")
SLICE = re.compile(r"baserom\.gba_0x([0-9a-fA-F]+)_0x([0-9a-fA-F]+)\.extracted")
GENERATED = re.compile(r"stream_0x([0-9a-f]+)_0x([0-9a-f]+)\.bin")
INCBIN = re.compile(r"INCBIN\s+(\S+\.extracted)")
STEP_EXIT = re.compile(r"(\w+)_exit=(\d+)")


def digest(path, algorithm):
    handle = hashlib.new(algorithm)
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            handle.update(chunk)
    return handle.hexdigest()


def retail_problem(path=None, sha1_file=None):
    path = RETAIL if path is None else path
    sha1_file = SHA1_FILE if sha1_file is None else sha1_file
    if not os.path.exists(path):
        return "%s is absent: the builder supplies the retail image" % path
    size = os.path.getsize(path)
    if size != ROM_SIZE:
        return "%s is %d B, not the image's %d B" % (path, size, ROM_SIZE)
    expected = open(sha1_file, encoding="ascii").read().strip().lower()
    measured = digest(path, "sha1")
    if measured != expected:
        return "%s sha1 %s is not %s's %s" % (path, measured, os.path.basename(sha1_file),
                                              expected)
    with open(path, "rb") as source:
        header = source.read(0x100)
    if header[0xAC:0xB0] != GAME_CODE:
        return "%s carries game code %r, not %r" % (path, header[0xAC:0xB0], GAME_CODE)
    return None


def asm_files(root=None):
    root = ROOT if root is None else root
    directory = os.path.join(root, "asm")
    return [os.path.join(directory, name) for name in sorted(os.listdir(directory))
            if name.endswith(".s")]


def incbin_ranges(root=None):
    out = []
    for path in asm_files(root):
        text = open(path, errors="replace").read()
        for match in SLICE.finditer(text):
            start, end = int(match.group(1), 16), int(match.group(2), 16)
            out.append((start, end - start))
    return sorted(out)


def generated_ranges(root=None):
    out = []
    for path in asm_files(root):
        text = open(path, errors="replace").read()
        for match in GENERATED.finditer(text):
            start, end = int(match.group(1), 16), int(match.group(2), 16)
            out.append((start, end - start))
    return sorted(out)


def identity_ranges():
    return []


def fill_bytes(root=None):
    root = ROOT if root is None else root
    path = os.path.join(root, "asm", "remainder.s")
    try:
        return fill_runs.carried(open(path, encoding="utf-8", errors="replace").read())
    except OSError:
        return 0


def fill_leftovers(retail, root=None):
    found = []
    for start, length in incbin_ranges(root):
        for offset, run, value in fill_runs.runs(retail[start:start + length]):
            found.append((start + offset, run, value))
    return found


def union_ranges(ranges):
    out = []
    for start, length in sorted(ranges):
        if out and start <= out[-1][0] + out[-1][1]:
            end = max(out[-1][0] + out[-1][1], start + length)
            out[-1] = (out[-1][0], end - out[-1][0])
        else:
            out.append((start, length))
    return out


def interval_problems(intervals):
    problems, spans = [], []
    for start, length in intervals:
        if length <= 0 or start < 0 or start + length > ROM_SIZE:
            problems.append("interval %#x+%#x is outside 0..%#x" % (start, length, ROM_SIZE))
        else:
            spans.append((start, start + length))
    spans.sort()
    end = 0
    for start, stop in spans:
        if start < end:
            problems.append("interval %#x..%#x overlaps the span ending at %#x"
                            % (start, stop, end))
        if stop > end:
            end = stop
    return problems


def source_bytes(root=None):
    ranges = incbin_ranges(root) + identity_ranges()
    problems = interval_problems(ranges)
    if problems:
        raise SystemExit("the measured intervals do not partition the image: %s"
                         % "; ".join(problems))
    covered = union_ranges(ranges)
    return ROM_SIZE - sum(length for _start, length in covered)


def accounted(raw, copies, source):
    total = raw + copies + source
    if total == ROM_SIZE:
        return total, None
    return total, ("the disjoint class totals raw %d + identity %d + source %d = %d are not the "
                   "image's %d" % (raw, copies, source, total, ROM_SIZE))


def census_problem(path=None):
    path = CENSUS if path is None else path
    if not os.path.exists(path):
        return "%s is absent: the census carries every bound" % path
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return "%s carries no row" % path
    seen = set()
    for row in rows:
        seen.update(row["channel"].split("+"))
        if row["kind"] == "start" and (row["end"] == "-"
                                       or row["reason"] not in CENSUS_REASONS):
            return "%s: the start at %s has an open bound (%s)" % (path, row["address"],
                                                                   row["reason"])
    missing = [name for name in CENSUS_CHANNELS if name not in seen]
    if missing:
        return "%s: no row carries the %s channel" % (path, ", ".join(missing))
    return None


def export_problem(rows=None, ranges=None):
    rows = emit_code.census_rows() if rows is None else rows
    ranges = incbin_ranges() if ranges is None else ranges
    absent = emit_code.modeless(rows)
    if absent:
        return "modeless: the code start at 0x%08x has no mode" % absent[0]
    raw = emit_code.raw_bytes(rows, ranges)
    if raw:
        return ("uncovered: the code start at 0x%08x has %d B inside an INCBIN slice"
                % raw[0])
    return None


def code_row_count():
    return len(emit_code.code_rows(emit_code.census_rows()))


def recomp_export(root=None):
    root = ROOT if root is None else root
    command = [sys.executable, os.path.join(root, "tools", "recomp", "export_inputs.py"),
               "--check"]
    proc = subprocess.run(command, cwd=root, capture_output=True)
    lines = [line for line in proc.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
    if proc.returncode:
        return None, (lines[-1] if lines else "the export check exits %d" % proc.returncode)
    for line in lines:
        if line.startswith("RECOMP PASS"):
            return line, None
    return None, "the export check printed no RECOMP PASS line"



def missing_slices(root=None):
    root = ROOT if root is None else root
    missing = []
    for path in asm_files(root):
        text = open(path, errors="replace").read()
        for match in INCBIN.finditer(text):
            if not os.path.exists(os.path.join(root, match.group(1))):
                missing.append(match.group(1))
    return missing


def tracked_rom_slices(retail, root=None):
    root = ROOT if root is None else root
    proc = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True)
    if proc.returncode != 0:
        return None
    hits = []
    for raw in proc.stdout.split(b"\0"):
        path = raw.decode()
        if not path or not os.path.exists(os.path.join(root, path)):
            continue
        blob = open(os.path.join(root, path), "rb").read()
        if 32 <= len(blob) <= len(retail) and retail.find(blob) >= 0:
            hits.append(path)
    return hits


def purge_outputs():
    build = os.path.join(ROOT, "build")
    os.makedirs(build, exist_ok=True)
    for name in os.listdir(build):
        if name.endswith(".o"):
            os.remove(os.path.join(build, name))
    if os.path.isfile(IMAGE):
        os.remove(IMAGE)


def purge_slices():
    names = [name for name in os.listdir(ROOT)
             if name.startswith("baserom.gba_0x") and name.endswith(".extracted")]
    for name in names:
        os.remove(os.path.join(ROOT, name))
    return len(names)


def error_lines(log_path):
    return [line.strip() for line in open(log_path, errors="replace")
            if re.search("error:", line, re.IGNORECASE)]


def rebuild(quiet=False):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    purge_outputs()
    with open(LOG, "w") as log:
        rc = subprocess.call(["cmd.exe", "/c", BUILD], stdout=log, stderr=subprocess.STDOUT,
                             cwd=ROOT)
    steps, failed = [], []
    for line in open(LOG):
        match = STEP_EXIT.search(line)
        if match:
            steps.append(match.group(1))
            if match.group(2) != "0":
                failed.append(match.group(1))
    if not quiet:
        if failed:
            print("rebuild exit=%d  FAILED STEPS=%s" % (rc, ",".join(failed)))
        else:
            print("rebuild exit=%d  steps=%d  failed=[]" % (rc, len(steps)))
        for line in error_lines(LOG):
            print("  " + line)
    if rc != 0 or failed or not os.path.exists(IMAGE):
        print("GATE FAIL: the build did not produce an image from every source file")
        return 1
    return 0


def cold_start():
    slices = purge_slices()
    purge_outputs()
    print("cold start: %d INCBIN slice(s) and every build output purged" % slices)
    rc = subprocess.call(["cmd.exe", "/c", EXTRACT], cwd=ROOT)
    if rc != 0:
        print("GATE FAIL: extract exit %d" % rc)
    return rc


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--verify-rom":
        problem = retail_problem()
        if problem:
            print("GATE FAIL: %s" % problem)
            return 1
        print("ROM IDENTITY MATCH sha1=%s game=%s size=%d"
              % (digest(RETAIL, "sha1"), GAME_CODE.decode("ascii"), ROM_SIZE))
        return 0

    cold = len(sys.argv) == 2 and sys.argv[1] == "--cold"
    problem = retail_problem()
    if problem:
        print("GATE FAIL: %s" % problem)
        return 1

    findings = lints.run()
    for name, detail in findings:
        print("LINT FAIL %s: %s" % (name, detail))
    if findings:
        print("GATE FAIL: %d lint finding(s)" % len(findings))
        return 1
    print("LINT PASS %s" % ",".join(lints.CHECKS))

    problem = census_problem()
    if problem:
        print("GATE FAIL: %s" % problem)
        return 1
    print("CENSUS PASS every start has an end, channels %s" % ",".join(CENSUS_CHANNELS))

    problem = export_problem()
    if problem:
        print("GATE FAIL: %s" % problem)
        return 1
    print("EXPORT PASS uncovered=0 modeless=0 over %d code rows" % code_row_count())

    line, problem = recomp_export()
    if problem:
        print("GATE FAIL: %s" % problem)
        return 1
    print(line)


    cited = [("tools/gate/test_gate.py", "test_the_source_count_is_the_slices_and_the_rest"),
             ("tools/gate/test_gate.py",
              "test_a_double_counted_interval_is_refused_instead_of_passing_as_arithmetic")]
    started = time.time()
    results = lints.run_cited_tests(cited)
    failed = [(pair, results[pair]) for pair in cited if results[pair][0] != 0]
    for (path, name), (code, output) in failed:
        print("GATE FAIL: %s::%s exits %d: %s" % (path, name, code, output))
    print("BEHAVIOUR %s %d test(s) in %.1fs"
          % ("FAIL" if failed else "PASS", len(cited), time.time() - started))
    if failed:
        return 1

    if cold and cold_start() != 0:
        return 1
    if rebuild() != 0:
        return 1

    image = open(IMAGE, "rb").read()
    if len(image) != ROM_SIZE:
        print("GATE FAIL: image size %d" % len(image))
        return 1
    measured = hashlib.sha256(image).hexdigest()
    print("image sha256=%s" % measured)
    print("canonical    =%s" % CANONICAL_SHA256)
    digest_ok = measured == CANONICAL_SHA256
    print("DIGEST %s" % ("MATCH" if digest_ok else "MISMATCH"))
    ok = digest_ok

    retail = open(RETAIL, "rb").read()
    copies = tracked_rom_slices(retail)
    print("tracked ROM slices: %s" % ("git ls-files failed" if copies is None
                                      else (", ".join(copies) if copies else "none")))
    ok = ok and copies == []
    missing = missing_slices()
    if missing:
        print("MISSING .extracted files: %s" % missing)
        ok = False

    ranges = incbin_ranges()
    identity = identity_ranges()
    raw = sum(length for _start, length in ranges)
    copies_total = sum(length for _start, length in identity)
    problems = interval_problems(ranges + identity)
    for entry in problems:
        print("GATE FAIL: %s" % entry)
    ok = ok and not problems
    source = ROM_SIZE - sum(length for _start, length in union_ranges(ranges + identity))
    print("incbin slices=%d total=%d" % (len(ranges), raw))
    print("generated=%d" % sum(length for _start, length in generated_ranges()))
    print("identity copies=%d (%.4f %%)" % (copies_total, 100.0 * copies_total / ROM_SIZE))
    print("raw-data=%d (%.4f %%)" % (raw, 100.0 * raw / ROM_SIZE))
    print("source=%d of %d (%.4f %%)" % (source, ROM_SIZE, 100.0 * source / ROM_SIZE))
    total, problem = accounted(raw, copies_total, source)
    print("accounted=%d of %d (%.4f %%) raw %d + identity %d + source %d"
          % (total, ROM_SIZE, 100.0 * total / ROM_SIZE, raw, copies_total, source))
    if problem:
        print("GATE FAIL: %s" % problem)
        ok = False
    fill = fill_bytes()
    without = source - fill
    print("fill=%d bytes (%.4f %%) as directives" % (fill, 100.0 * fill / ROM_SIZE))
    print("source-without-fill=%d of %d (%.4f %%)"
          % (without, ROM_SIZE, 100.0 * without / ROM_SIZE))
    leftovers = fill_leftovers(retail)
    for start, length, value in leftovers:
        print("GATE FAIL: the %d B run of 0x%02X at 0x%x is still INCBINed"
              % (length, value, start))
    ok = ok and not leftovers
    print("GATE %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
