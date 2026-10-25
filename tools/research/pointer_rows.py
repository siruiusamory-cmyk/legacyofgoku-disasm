from __future__ import annotations

import hashlib
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "code"))

import emit_code

ROM = os.path.join(ROOT, "baserom.gba")
ASM = os.path.join(ROOT, "asm", "remainder.s")
SHA1 = os.path.join(ROOT, "baserom.sha1")
CENSUS = os.path.join(ROOT, "tools", "code", "CENSUS_EVIDENCE.csv")
CODE = os.path.join(ROOT, "build", "code")
ROM_BASE = 0x08000000
ROM_SIZE = 8388608
GAME_CODE = b"ALGE"
WORDS = 4
UNPAINTED, FILL, TEXT, RESIDUE, POINTER = 0, 1, 2, 3, 4
SLICE = re.compile(r"^baserom\.gba_0x([0-9a-f]+)_0x([0-9a-f]+)\.extracted$")
STREAM = re.compile(r"^stream_0x([0-9a-f]+)_0x([0-9a-f]+)\.bin$")
INCLUDE = re.compile(r"^code_([0-9a-f]{8})\.s$")
LABEL = re.compile(r"^\|loc_([0-9A-Fa-f]{8})\|$")
DCD = re.compile(r"^\tDCD\t\|loc_([0-9A-Fa-f]{8})\|(?:\+([0-9]+))?$")


def inside(address, length=1):
    return ROM_BASE <= address and address + length <= ROM_BASE + ROM_SIZE


def word(image, address):
    if not inside(address, 4):
        raise ValueError("the word at 0x%08X is outside the image" % address)
    return int.from_bytes(image[address - ROM_BASE:address - ROM_BASE + 4], "little")


def problem(image):
    if len(image) != ROM_SIZE:
        return "the image is %d B, not %d B" % (len(image), ROM_SIZE)
    if image[0xAC:0xB0] != GAME_CODE:
        return "the image carries game code %r, not %r" % (image[0xAC:0xB0], GAME_CODE)
    expected = open(SHA1, encoding="ascii").read().strip().lower()
    measured = hashlib.sha1(image).hexdigest()
    if measured != expected:
        return "the image's sha1 %s is not baserom.sha1's %s" % (measured, expected)
    return None


def code_bounds():
    out = {}
    for row in emit_code.census_rows(CENSUS):
        if row["kind"] == "start" and row["end"] is not None:
            out[row["address"]] = row["end"]
    return out


def tokens(text, bounds):
    out, position = [], emit_code.IMAGE_START - ROM_BASE
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append(("blank", position, 0, line))
            continue
        if stripped.startswith("AREA"):
            out.append(("area", position, 0, line))
            continue
        if stripped.startswith("INCLUDE"):
            parts = stripped.split(None, 1)
            found = INCLUDE.search(os.path.basename(parts[1].replace("\\", "/")))
            if found is None:
                raise ValueError("the include %r names no code row" % parts[1])
            address = int(found.group(1), 16)
            if address not in bounds:
                raise ValueError("the census carries no code row for 0x%08X" % address)
            size = bounds[address] - address
            out.append(("code", position, size, line))
            position += size
            continue
        if stripped.startswith("INCBIN"):
            parts = stripped.split(None, 1)
            name = os.path.basename(parts[1].replace("\\", "/"))
            found = SLICE.search(name)
            kind = "raw"
            if found is None:
                found = STREAM.search(name)
                kind = "stream"
            if found is None:
                raise ValueError("the slice %r names no address range" % parts[1])
            begin, stop = int(found.group(1), 16), int(found.group(2), 16)
            if begin != position:
                raise ValueError("the slice %r starts at 0x%X, not at 0x%X"
                                 % (parts[1], begin, position))
            out.append((kind, position, stop - begin, line))
            position += stop - begin
            continue
        found = LABEL.match(stripped)
        if found is not None:
            if int(found.group(1), 16) != ROM_BASE + position:
                raise ValueError("the label %s names 0x%08X, not 0x%08X"
                                 % (stripped, int(found.group(1), 16), ROM_BASE + position))
            out.append(("label", position, 0, line))
            continue
        found = DCD.match(line)
        if found is not None:
            out.append(("dcd", position, 4, line))
            position += 4
            continue
        raise ValueError("the line %r at 0x%X has no source form" % (line, position))
    if position != ROM_SIZE:
        raise ValueError("the file covers %d B, not %d B" % (position, ROM_SIZE))
    return out


def painted(image, items):
    owner = bytearray(len(image))
    intervals = []
    for kind, begin, size, _line in items:
        if kind not in ("raw", "dcd"):
            continue
        if intervals and begin <= intervals[-1][1]:
            intervals[-1] = (intervals[-1][0], max(intervals[-1][1], begin + size))
        else:
            intervals.append((begin, begin + size))
    for begin, end in intervals:
        chunk = image[begin:end]
        for index in range(begin, min(end, 0xFE3E)):
            owner[index] = RESIDUE
        for match in re.finditer(rb"\x00{32,}|\xff{32,}", chunk):
            for index in range(begin + match.start(), begin + match.end()):
                if owner[index] == UNPAINTED:
                    owner[index] = FILL
        for match in re.finditer(rb"[ -~]{8,}\x00", chunk):
            for index in range(begin + match.start(), begin + match.end()):
                if owner[index] == UNPAINTED:
                    owner[index] = TEXT
        for index in range(begin + ((4 - begin % 4) % 4), end - 15, 4):
            if owner[index] != UNPAINTED:
                continue
            count = 0
            while index + 4 * count + 4 <= end:
                value = struct.unpack_from("<I", image, index + 4 * count)[0]
                if ROM_BASE <= value < ROM_BASE + ROM_SIZE:
                    count += 1
                else:
                    break
            if count >= WORDS:
                for offset in range(index, index + 4 * count):
                    owner[offset] = POINTER
    return owner


def runs(owner):
    out, index = [], 0
    while index < len(owner) - 15:
        if owner[index] == POINTER and index % 4 == 0:
            count = 0
            while index + 4 * count + 4 <= len(owner) and \
                    owner[index + 4 * count] == POINTER:
                count += 1
            out.append((index, count))
            index += 4 * count
            continue
        index += 1
    return out


def labels():
    if not os.path.isdir(CODE):
        raise ValueError("the pointer generator needs the code labels in %s" % CODE)
    found = set()
    for directory in (os.path.join(ROOT, "asm"), CODE):
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".s"):
                continue
            text = open(os.path.join(directory, name), errors="replace").read()
            found.update(int(hit, 16) for hit in re.findall(r"\|loc_([0-9A-Fa-f]{8})\|", text))
    return found


def plan(image, found, tagged):
    out = []
    for begin, count in found:
        targets = [word(image, ROM_BASE + begin + 4 * step) for step in range(count)]
        if not all(target & ~1 in tagged for target in targets):
            continue
        if begin % 4:
            raise ValueError("the run at 0x%08X is not four-byte aligned" % (ROM_BASE + begin))
        lines = ["\tDCD\t|loc_%08X|%s" % (target & ~1, "+1" if target & 1 else "")
                 for target in targets]
        out.append((begin, count, lines))
    return out


def gap_name(begin, stop):
    return "baserom.gba_0x%x_0x%x.extracted" % (begin, stop)


def split(items, planned):
    blocks = dict((begin, (count, lines)) for begin, count, lines in planned)
    starts = sorted(blocks)
    emitted, out, gaps = set(), [], []
    for kind, position, size, line in items:
        if kind == "raw":
            stop = position + size
            cursor = position
            for begin in starts:
                if not position <= begin < stop:
                    continue
                count, lines = blocks[begin]
                if begin + 4 * count > stop:
                    raise ValueError("the run at 0x%X leaves its slice at 0x%X"
                                     % (begin, stop))
                if begin > cursor:
                    gaps.append((cursor, begin))
                    out.append("\tINCBIN\t" + gap_name(cursor, begin))
                out.extend(lines)
                emitted.add(begin)
                cursor = begin + 4 * count
            if cursor < stop:
                gaps.append((cursor, stop))
                out.append("\tINCBIN\t" + gap_name(cursor, stop))
            continue
        if kind == "dcd":
            if position in blocks and position not in emitted:
                out.extend(blocks[position][1])
                emitted.add(position)
            continue
        out.append(line)
    absent = [begin for begin, _count, _lines in planned if begin not in emitted]
    if absent:
        raise ValueError("the run at 0x%08X is inside no slice" % (ROM_BASE + absent[0]))
    return "\n".join(out) + "\n", gaps


def held(path, blob):
    if not os.path.exists(path):
        raise ValueError("%s is absent" % path)
    if open(path, "rb").read() != blob:
        raise ValueError("%s does not hold its bytes" % path)


def census(image):
    trouble = problem(image)
    if trouble:
        raise ValueError(trouble)
    items = tokens(open(ASM, encoding="utf-8", newline="").read(), code_bounds())
    found = runs(painted(image, items))
    tagged = labels()
    planned = plan(image, found, tagged)
    return {"items": items, "runs": found, "planned": planned,
            "ran": sum(4 * count for _b, count in found),
            "emitted": sum(4 * count for _b, count, _l in planned)}


def verify(image, text):
    items = tokens(text, code_bounds())
    for kind, position, size, line in items:
        if kind == "dcd":
            found = DCD.match(line)
            value = int(found.group(1), 16) + int(found.group(2) or 0)
            if value != word(image, ROM_BASE + position):
                raise ValueError("the line %r at 0x%X names 0x%08X, not 0x%08X"
                                 % (line, ROM_BASE + position, value,
                                    word(image, ROM_BASE + position)))
        if kind == "raw":
            held(os.path.join(ROOT, gap_name(position, position + size)),
                 image[position:position + size])
    return items


def summary(measured):
    return ("runs=%d bytes=%d emitted_runs=%d emitted_bytes=%d raw_runs=%d raw_bytes=%d"
            % (len(measured["runs"]), measured["ran"], len(measured["planned"]),
               measured["emitted"], len(measured["runs"]) - len(measured["planned"]),
               measured["ran"] - measured["emitted"]))


def build(image):
    measured = census(image)
    text, gaps = split(measured["items"], measured["planned"])
    for begin, stop in gaps:
        path = os.path.join(ROOT, gap_name(begin, stop))
        with open(path, "wb") as handle:
            handle.write(image[begin:stop])
        held(path, image[begin:stop])
    verify(image, text)
    with open(ASM, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return measured


def check(image):
    measured = census(image)
    text = open(ASM, encoding="utf-8", newline="").read()
    if text != split(measured["items"], measured["planned"])[0]:
        print("POINTER FAIL: asm\\remainder.s is not the pointer list this image derives")
        return 1
    verify(image, text)
    print(summary(measured))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["--write"], ["--check"]):
        print("usage: python tools\\research\\pointer_rows.py [--write|--check]")
        return 2
    if not os.path.exists(ROM):
        print("the pointer generator needs the retail image at %s" % ROM)
        return 1
    image = open(ROM, "rb").read()
    try:
        if argv == ["--check"]:
            return check(image)
        print(summary(build(image)))
    except ValueError as error:
        print("POINTER FAIL: %s" % error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
