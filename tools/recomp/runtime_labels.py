from __future__ import annotations

import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "code"))
sys.path.insert(0, os.path.join(ROOT, "tools", "split"))

import census
import emit_code

LABELS = census.RUNTIME
RUNS = os.path.join(ROOT, "tools", "code", "RUNTIME_LABELS_RUNS.csv")
ROM = os.path.join(ROOT, "baserom.gba")
HEADER = "region,address,mode"
RUN_HEADER = "run,frames,hash,entries,rom,iwram,route"
REGIONS = ("rom", "iwram")
MODES = emit_code.MODES


def read(path=LABELS):
    with open(path, encoding="ascii", newline="") as handle:
        return [(row["region"], int(row["address"], 16), row["mode"])
                for row in csv.DictReader(handle)]


def run_of(path=RUNS):
    with open(path, encoding="ascii", newline="") as handle:
        return list(csv.DictReader(handle))


def form_problem(path=LABELS):
    text = open(path, encoding="ascii", newline="").read()
    if not text.startswith(HEADER + "\n"):
        return "%s does not open with the header %s" % (path, HEADER)
    labels = read(path)
    seen = set()
    for region, address, mode in labels:
        if region not in REGIONS:
            return "the label at 0x%08x carries region %s" % (address, region)
        if mode not in MODES:
            return "the label at 0x%08x carries mode %s" % (address, mode)
        if (region, address) in seen:
            return "the label at 0x%08x repeats" % address
        seen.add((region, address))
    if [address for _region, address, _mode in labels] != sorted(
            address for _region, address, _mode in labels):
        return "the labels are not in address order"
    return None


def admitted(labels, rows):
    starts = dict((row["address"], row) for row in rows if row["kind"] == "start")
    out, refused = [], []
    for region, address, mode in labels:
        row = starts.get(address) if region == "rom" else None
        if row is None or row["end"] is None or row["mode"] != mode:
            refused.append(address)
        else:
            out.append(address)
    return out, refused


def refused_text(addresses):
    return "the label at 0x%08x is not an instruction boundary that closes into a row" \
        % addresses[0]


def merged(path, labels):
    existing = read(path) if os.path.exists(path) else []
    return sorted(set(existing) | set(labels), key=lambda row: (row[1], row[0]))


def admitted_by_the_census(labels, path=LABELS):
    union = merged(path, labels)
    rom = open(ROM, "rb").read()
    result = census.census_result(
        rom, labels=[(address, census.MODE_THUMB if mode == "thumb" else census.MODE_ARM)
                     for _region, address, mode in union])
    runtime = set(result["runtime"])
    return ([label for label in labels if label[1] in runtime],
            [label for label in labels if label[1] not in runtime])


def displaced(labels):
    known = {address for _region, address, _mode in labels}
    return [(region, address + 2, mode) for region, address, mode in labels
            if address + 2 not in known]


def run_problem(rows, labels, path=RUNS):
    if not rows:
        return "%s carries no run, so the labels carry no provenance" % path
    total = {"entries": 0, "rom": 0, "iwram": 0}
    for row in rows:
        for name in ("frames", "entries", "rom", "iwram"):
            if not row[name].isdigit():
                return "%s: %s is %r, not a count" % (path, name, row[name])
            if name in total:
                total[name] += int(row[name])
        if len(row["hash"]) != 16 or any(character not in "0123456789abcdef"
                                         for character in row["hash"]):
            return "%s: the frame hash %r is not sixteen hex digits" % (path, row["hash"])
    rom = len([1 for region, _address, _mode in labels if region == "rom"])
    iwram = len(labels) - rom
    if (total["entries"], total["rom"], total["iwram"]) != (len(labels), rom, iwram):
        return ("%s: the runs record %d entries (%d rom, %d iwram) and the labels carry %d (%d "
                "rom, %d iwram)" % (path, total["entries"], total["rom"], total["iwram"],
                                    len(labels), rom, iwram))
    return None


def measure(path=LABELS, runs=RUNS, evidence=census.EVIDENCE):
    if not os.path.exists(path):
        return None, "%s is absent, so there is no label record" % path
    problem = form_problem(path)
    if problem:
        return None, problem
    labels = read(path)
    if not os.path.exists(evidence):
        return None, "%s is absent, so no label can be measured against a row" % evidence
    rows = emit_code.census_rows(evidence)
    found, refused = admitted(labels, rows)
    if refused:
        return None, refused_text(refused)
    starts = set(row["address"] for row in rows if row["kind"] == "start")
    nulls = [row for row in displaced(labels) if row[1] not in starts]
    _found, null_refused = admitted(nulls, rows)
    if not nulls:
        return None, "the labels carry no address that a one-halfword displacement moves"
    if len(null_refused) != len(nulls):
        return None, ("the same labels displaced by one halfword are refused %d of %d times, so "
                      "the boundary rule is not what admits them"
                      % (len(null_refused), len(nulls)))
    if not os.path.exists(runs):
        return None, "%s is absent, so the labels carry no provenance" % runs
    problem = run_problem(run_of(runs), labels, runs)
    if problem:
        return None, problem
    return {"rows": len(labels), "admitted": len(found), "null_samples": len(nulls),
            "null_refused": len(null_refused)}, None


def check(path=LABELS, runs=RUNS, evidence=census.EVIDENCE):
    figures, problem = measure(path, runs, evidence)
    return problem


def imported(path):
    labels, digest = [], None
    for line in open(path, encoding="ascii"):
        parts = line.split()
        if len(parts) == 2 and parts[0] == "rom-sha256":
            digest = parts[1]
        elif len(parts) == 3 and parts[0] in REGIONS:
            labels.append((parts[0], int(parts[1], 16), "thumb" if parts[2] == "t" else "arm"))
    unique = sorted(set(labels), key=lambda row: (row[1], row[0]))
    return unique, digest


def image_problem(digest):
    if not os.path.exists(ROM):
        return None
    sys.path.insert(0, os.path.join(ROOT, "tools", "gate"))
    import gate
    measured = gate.digest(ROM, "sha256")
    if measured != digest:
        return "%s has sha256 %s, not the accumulator's %s" % (ROM, measured, digest)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--import", dest="source")
    parser.add_argument("--admit", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--labels", default=LABELS)
    parser.add_argument("--runs", default=RUNS)
    arguments = parser.parse_args(argv)
    if arguments.source:
        labels, digest = imported(arguments.source)
        if digest is None:
            print("LABELS FAIL %s carries no rom-sha256 line" % arguments.source)
            return 1
        problem = image_problem(digest)
        if problem:
            print("LABELS FAIL %s" % problem)
            return 1
        if arguments.admit:
            labels, refused = admitted_by_the_census(labels, arguments.labels)
            print("admit kept=%d refused=%s"
                  % (len(labels), " ".join("0x%08x" % row[1] for row in refused) or "none"))
        labels = merged(arguments.labels, labels)
        text = HEADER + "\n" + "".join("%s,0x%08x,%s\n" % row for row in labels)
        if not arguments.write:
            print("LABELS PASS rows=%d, and --write would record them" % len(labels))
            return 0
        with open(arguments.labels, "w", encoding="ascii", newline="\n") as handle:
            handle.write(text)
        print("wrote %s rows=%d" % (os.path.relpath(arguments.labels, ROOT).replace("\\", "/"),
                                    len(labels)))
        return 0
    figures, problem = measure(arguments.labels, arguments.runs)
    if problem:
        print("LABELS FAIL %s" % problem)
        return 1
    print("LABELS PASS rows=%d admitted=%d null_refused=%d of %d"
          % (figures["rows"], figures["admitted"], figures["null_refused"],
             figures["null_samples"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
