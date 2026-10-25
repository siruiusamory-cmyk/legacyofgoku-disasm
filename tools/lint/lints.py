from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

QUOTED_INTERPRETER = re.compile(r"""["']cmd["']""")
SWITCH_INTERPRETER = re.compile(r"(?<![\w.\\/:-])cmd\s+[/-][ck]\b", re.I)
BATCH_INTERPRETER = re.compile(r"(?<![\w.\\/:-])cmd(?![A-Za-z0-9_.\-])")
POOL_SOURCE = re.compile(r"(?m)^\s*(?:import\s+multiprocessing\b"
                         r"|from\s+multiprocessing[\w.]*\s+import\b"
                         r"|from\s+concurrent\.futures\s+import\b[^\n]*ProcessPool)")
POOL_CALL = re.compile(r"\b(?:multiprocessing\.Pool|ProcessPoolExecutor)\s*\(")
MAIN_GUARD = re.compile(r"(?m)^if\s+__name__\s*==\s*[\"']__main__[\"']\s*:")
SEARCH_PATH = re.compile(r"sys\.path\.(?:insert|append)\s*\([^)]*")
WINDOWS_PATH = re.compile(r"[A-Za-z]:[\\/]")
TRACKED_IMAGE = re.compile(r"\.gba$")
SIZE_LIMIT = 1024 * 1024
GENERATED_LISTING = "asm/remainder.s"
ASSETS = "assets/"
ASM = "asm"
EQUATE_FILES = ("asm/registers.s", "asm/memory.s")
ADDRESS_LITERAL = re.compile(r"\b0x0([34])[0-9A-Fa-f]{6}\b")
ADDRESS_SYMBOL = re.compile(r"\bsub_[0-9A-F]{8}\b")
README_PERCENT = re.compile(r"([\d.]+)\s*%")
README_BYTES = re.compile(r"([\d,]+)\s+of\s+([\d,]+)\s+bytes")
README_COMMAND = re.compile(r"python tools\\gate\\gate\.py")
README_STARTS = re.compile(r"code%20starts-([\d,]+)-")
BEHAVIOUR_GUARD = "LG1_BEHAVIOUR_TEST"
CITED_PASSED = ("PASSED", "SKIPPED", "XFAIL", "XPASS")
CITED_RESULT = re.compile(r"^(\S+?\.py)::(\S+?)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b")
BATCH = (".cmd", ".bat")
SOURCES = (".py", ".cmd", ".bat")

CHECKS = ("P-148-repo-module-path", "P-159-bare-interpreter", "P-167-pool-guard",
          "ROM-tracked-image", "README-numbers", "READABILITY-ratchet", "READABILITY-path",
          "NAMING-address-ratchet")


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def bare_interpreter(name, text):
    patterns = [QUOTED_INTERPRETER, SWITCH_INTERPRETER]
    if name.endswith(BATCH):
        patterns.append(BATCH_INTERPRETER)
    hits = []
    reported = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            line = line_of(text, match.start())
            if line in reported:
                continue
            reported.add(line)
            hits.append(("P-159-bare-interpreter",
                         "%s:%d: %s" % (name, line, text.splitlines()[line - 1].strip())))
    return hits


def pool_without_guard(name, text):
    match = POOL_SOURCE.search(text) or POOL_CALL.search(text)
    if match is None or MAIN_GUARD.search(text):
        return []
    line = line_of(text, match.start())
    return [("P-167-pool-guard", "%s:%d: a process pool in a module with no main guard: %s"
             % (name, line, text.splitlines()[line - 1].strip()))]


def out_of_repo_module_path(name, text):
    hits = []
    for match in SEARCH_PATH.finditer(text):
        if WINDOWS_PATH.search(match.group(0)):
            hits.append(("P-148-repo-module-path",
                         "%s:%d: %s" % (name, line_of(text, match.start()), match.group(0).strip())))
    return hits


def tracked_files():
    proc = subprocess.run(["git", "ls-files", "-z", "--cached"], cwd=ROOT, capture_output=True)
    if proc.returncode != 0:
        return None
    return sorted(name for name in proc.stdout.decode("utf-8", "replace").split("\0") if name)


def source_files():
    proc = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                          cwd=ROOT, capture_output=True)
    if proc.returncode != 0:
        return None
    return sorted(name for name in proc.stdout.decode("utf-8", "replace").split("\0")
                  if name.endswith(SOURCES))


def read_source(name):
    path = name if os.path.isabs(name) else os.path.join(ROOT, name)
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None


def tracked_rom_findings(tracked=None):
    if tracked is None:
        tracked = tracked_files()
        if tracked is None:
            return [("lint-enumeration",
                     "git ls-files failed, the tracked-path check cannot see the tree")]
    findings = []
    for name in tracked:
        if TRACKED_IMAGE.search(name):
            findings.append(("ROM-tracked-image", "%s: a tracked *.gba path" % name))
        if name.startswith(ASSETS):
            continue
        try:
            size = os.path.getsize(os.path.join(ROOT, name))
        except OSError:
            continue
        if size > SIZE_LIMIT and name != GENERATED_LISTING:
            findings.append(("ROM-tracked-image",
                             "%s: %d tracked bytes outside assets/" % (name, size)))
    return findings


def uncomma(text):
    return int(text.replace(",", ""))


def readme_numbers_findings(text, built, total, percent, without=None):
    findings = []
    percents = README_PERCENT.findall(text)
    spans = README_BYTES.findall(text)
    wanted = [value for value in (percent, without) if value is not None]
    for value in wanted:
        found = percents.count(value)
        if found != 1:
            findings.append(("README-numbers",
                             "README.md: %s %% expected exactly 1 time, found %d"
                             % (value, found)))
    if len(spans) != 1:
        findings.append(("README-numbers",
                         "README.md: one <built> of <size> bytes span expected, found %d"
                         % len(spans)))
    if README_COMMAND.search(text) is None:
        findings.append(("README-numbers",
                         "README.md: the progress line must name the command that prints it: "
                         "python tools\\gate\\gate.py"))
    for listed in percents:
        if listed not in wanted:
            findings.append(("README-numbers",
                             "README.md: %s %% is not the gate's %s %%" % (listed, percent)))
    for first, second in spans:
        if (uncomma(first), uncomma(second)) != (built, total):
            findings.append(("README-numbers",
                             "README.md: %s of %s bytes is not the gate's %d of %d bytes"
                             % (first, second, built, total)))
    return findings


def readme_starts_findings(text, starts):
    found = README_STARTS.findall(text)
    if len(found) != 1:
        return [("README-numbers",
                 "README.md: one 'code%%20starts-<count>-' badge expected, found %d" % len(found))]
    if uncomma(found[0]) != starts:
        return [("README-numbers",
                 "README.md: the badge reads %s code starts, not the census's %d"
                 % (found[0], starts))]
    return []


def readme_findings():
    text = read_source("README.md")
    if text is None:
        return [("README-numbers", "README.md: cannot be read")]
    sys.path.insert(0, os.path.join(ROOT, "tools", "gate"))
    import gate
    import emit_code
    built = gate.source_bytes()
    fill = gate.fill_bytes()
    findings = readme_numbers_findings(text, built, gate.ROM_SIZE,
                                       "%.4f" % (100.0 * built / gate.ROM_SIZE),
                                       "%.4f" % (100.0 * (built - fill) / gate.ROM_SIZE))
    return findings + readme_starts_findings(text, len(emit_code.census_rows()))


def asm_texts():
    directory = os.path.join(ROOT, ASM)
    if not os.path.isdir(directory):
        return []
    out = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".s"):
            continue
        relative = "%s/%s" % (ASM, name)
        if relative in EQUATE_FILES:
            continue
        text = read_source(relative)
        if text is not None:
            out.append((relative, text))
    return out


def address_literal_counts():
    counts = {"ram": 0, "hardware": 0}
    for _name, text in asm_texts():
        for digit in ADDRESS_LITERAL.findall(text):
            counts["ram" if digit == "3" else "hardware"] += 1
    return counts


def readability_findings(baseline_text, live):
    site = "tools/lint/READABILITY_BASELINE.txt"
    recorded = dict((key, int(value))
                    for key, value in re.findall(r"(ram|hardware)=(\d+)", baseline_text or ""))
    findings = []
    for key in ("ram", "hardware"):
        if key not in recorded:
            findings.append(("READABILITY-ratchet", "%s: %s=<count> expected" % (site, key)))
            continue
        if live[key] > recorded[key]:
            findings.append(("READABILITY-ratchet",
                             "%s: %s=%d, above the baseline %d"
                             % (site, key, live[key], recorded[key])))
        if live[key] < recorded[key]:
            findings.append(("READABILITY-ratchet",
                             "%s: %s=%d, below the baseline %d, which this tree must lower"
                             % (site, key, live[key], recorded[key])))
    return findings


def naming_live():
    return sum(len(ADDRESS_SYMBOL.findall(text)) for _name, text in asm_texts())


def naming_findings(baseline_text):
    site = "tools/lint/NAMING_BASELINE.txt"
    live = naming_live()
    found = re.search(r"\d+", baseline_text or "")
    if found is None:
        return [("NAMING-address-ratchet", "%s: one count of address-named symbols expected" % site)]
    baseline = int(found.group(0))
    if live > baseline:
        return [("NAMING-address-ratchet",
                 "%s: %d address-named symbols, above the baseline %d" % (site, live, baseline))]
    if live < baseline:
        return [("NAMING-address-ratchet",
                 "%s: %d address-named symbols, below the baseline %d, which this tree must "
                 "lower" % (site, live, baseline))]
    return []


def newcomer_path_findings(readme, install):
    tokens = ("extract.cmd", "rebuild.cmd", "python tools\\gate\\gate.py", "docs/README.md")
    findings = []
    for token in tokens:
        if token not in readme and token not in install:
            findings.append(("READABILITY-path",
                             "README.md and INSTALL.md: neither names %s" % token))
    return findings


def cited_test_problem(path, name):
    text = read_source(path)
    if text is None:
        return "%s cannot be read" % path
    if re.search(r"(?m)^def %s\(" % re.escape(name), text) is None:
        return "%s does not define %s" % (path, name)
    return None


def run_cited_test(path, name, launch=None):
    if os.environ.get(BEHAVIOUR_GUARD) == "1":
        return 0, "skipped: a nested lint run does not run a cited test"
    argv = [sys.executable, "-m", "pytest", "-q", "%s::%s" % (path, name)]
    environment = dict(os.environ)
    environment[BEHAVIOUR_GUARD] = "1"
    proc = (launch or subprocess.run)(argv, cwd=ROOT, capture_output=True, env=environment)
    lines = [line for line in proc.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
    return proc.returncode, lines[-1] if lines else ""


def cited_test_results(text):
    results = {}
    for line in text.splitlines():
        match = CITED_RESULT.match(line)
        if match:
            results[(match.group(1), match.group(2))] = match.group(3)
    return results


def run_cited_tests(pairs, launch=None):
    if os.environ.get(BEHAVIOUR_GUARD) == "1":
        return dict((pair, run_cited_test(*pair)) for pair in pairs)
    environment = dict(os.environ)
    environment[BEHAVIOUR_GUARD] = "1"
    argv = [sys.executable, "-m", "pytest", "-v", "--tb=no"]
    argv += ["%s::%s" % pair for pair in dict.fromkeys(pairs)]
    proc = (launch or subprocess.run)(argv, cwd=ROOT, capture_output=True, env=environment)
    status = cited_test_results(proc.stdout.decode("utf-8", "replace"))
    return dict((pair, (0, "") if status.get(pair, "") in CITED_PASSED
                 else run_cited_test(pair[0], pair[1], launch)) for pair in pairs)


def run(files=None):
    whole_tree = files is None
    if whole_tree:
        files = source_files()
        if files is None:
            return [("lint-enumeration", "git ls-files failed, the lints cannot see the tree")]
    findings = []
    for name in files:
        path = name if os.path.isabs(name) else os.path.join(ROOT, name)
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError as exc:
            findings.append(("lint-read", "%s: %s" % (name, exc)))
            continue
        findings += bare_interpreter(name, text)
        if name.endswith(".py"):
            findings += pool_without_guard(name, text)
            findings += out_of_repo_module_path(name, text)
    if whole_tree:
        findings += tracked_rom_findings()
        findings += readme_findings()
        findings += readability_findings(read_source("tools/lint/READABILITY_BASELINE.txt"),
                                        address_literal_counts())
        findings += naming_findings(read_source("tools/lint/NAMING_BASELINE.txt"))
        findings += newcomer_path_findings(read_source("README.md") or "",
                                          read_source("INSTALL.md") or "")
    return findings


def main(argv=None):
    files = list(argv) if argv else None
    findings = run(files)
    for name, detail in findings:
        print("LINT FAIL %s: %s" % (name, detail))
    print("LINT %s: %d finding(s) over %d file(s)"
          % ("FAIL" if findings else "PASS", len(findings),
             len(files) if files else len(source_files() or [])))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
