from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ROM = os.path.join(ROOT, "baserom.gba")
REMAINDER = os.path.join(ROOT, "asm", "remainder.s")
ROM_BASE = 0x08000000
MINIMUM = 32
VALUES = (0x00, 0xFF)
SLICE = re.compile(r"baserom\.gba_0x([0-9a-f]+)_0x([0-9a-f]+)\.extracted")
ZERO = re.compile(r"^\tSPACE\t(\d+)$")
DEFINE = re.compile(r"^\tGBLA\tfill_[0-9a-f]{8}$")
COUNT = re.compile(r"^fill_[0-9a-f]{8}\tSETA\t(\d+)$")
BODY = re.compile(r"^(?:\tWHILE\tfill_[0-9a-f]{8} > 0|\tDCB\t0xFF|\tWEND"
                  r"|fill_[0-9a-f]{8}\tSETA\tfill_[0-9a-f]{8} - 1)$")


def runs(blob):
    found, index, size = [], 0, len(blob)
    while index < size:
        value = blob[index]
        stop = index
        while stop < size and blob[stop] == value:
            stop += 1
        if value in VALUES and stop - index >= MINIMUM:
            found.append((index, stop - index, value))
        index = stop
    return found


def fill_line(line):
    hit = ZERO.match(line) or COUNT.match(line)
    if hit is not None:
        return int(hit.group(1))
    if DEFINE.match(line) or BODY.match(line):
        return 0
    return None


def carried(text):
    return sum(fill_line(line) or 0 for line in text.splitlines())


def listed(text):
    out = []
    for line in text.splitlines():
        hit = ZERO.match(line)
        if hit is not None:
            out.append((0x00, int(hit.group(1))))
        hit = COUNT.match(line)
        if hit is not None:
            out.append((0xFF, int(hit.group(1))))
    return out


def gap_name(begin, stop):
    return "baserom.gba_0x%x_0x%x.extracted" % (begin, stop)


def directive(begin, value, length):
    if value:
        name = "fill_%08x" % (ROM_BASE + begin)
        return ["\tGBLA\t" + name,
                "%s\tSETA\t%d" % (name, length),
                "\tWHILE\t%s > 0" % name,
                "\tDCB\t0xFF",
                "%s\tSETA\t%s - 1" % (name, name),
                "\tWEND"]
    return ["\tSPACE\t%d" % length]


def split(rom, text):
    out, pieces, directives = [], [], []
    for line in text.splitlines():
        found = SLICE.search(line)
        if found is None or "INCBIN" not in line:
            out.append(line)
            continue
        begin, stop = int(found.group(1), 16), int(found.group(2), 16)
        holes = runs(rom[begin:stop])
        if not holes:
            out.append(line)
            continue
        cursor = begin
        for offset, length, value in holes:
            if begin + offset > cursor:
                out.append("\tINCBIN\t" + gap_name(cursor, begin + offset))
                pieces.append((cursor, begin + offset))
                cursor = begin + offset
            out += directive(cursor, value, length)
            directives.append((value, length))
            cursor += length
        if cursor < stop:
            out.append("\tINCBIN\t" + gap_name(cursor, stop))
            pieces.append((cursor, stop))
    return "\n".join(out) + "\n", pieces, directives


def held(path, blob):
    if not os.path.exists(path):
        raise ValueError("%s is absent" % path)
    if open(path, "rb").read() != blob:
        raise ValueError("%s does not hold its bytes" % path)


def build(image):
    text, pieces, directives = split(image, open(REMAINDER, encoding="utf-8",
                                                newline="").read())
    for begin, stop in pieces:
        path = os.path.join(ROOT, gap_name(begin, stop))
        with open(path, "wb") as handle:
            handle.write(image[begin:stop])
        held(path, image[begin:stop])
    with open(REMAINDER, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return directives


def summary(directives):
    return ("directives=%d zeros=%d ff=%d bytes=%d"
            % (len(directives),
               sum(length for value, length in directives if value == 0x00),
               sum(length for value, length in directives if value == 0xFF),
               sum(length for _value, length in directives)))


def check(image):
    text = open(REMAINDER, encoding="utf-8", newline="").read()
    expected, pieces, _directives = split(image, text)
    if text != expected:
        print("FILL FAIL: asm\\remainder.s is not the fill list this image derives")
        return 1
    for begin, stop in pieces:
        held(os.path.join(ROOT, gap_name(begin, stop)), image[begin:stop])
    print(summary(listed(text)))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["--write"], ["--check"]):
        print("usage: python tools\\code\\fill_runs.py [--write|--check]")
        return 2
    if not os.path.exists(ROM):
        print("the fill generator needs the retail image at %s" % ROM)
        return 1
    image = open(ROM, "rb").read()
    try:
        if argv == ["--check"]:
            return check(image)
        print(summary(build(image)))
    except ValueError as error:
        print("FILL FAIL: %s" % error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
