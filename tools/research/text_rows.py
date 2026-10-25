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
OUT = os.path.join(ROOT, "build", "text")
ROM_BASE = 0x08000000
ROM_SIZE = 8388608
GAME_CODE = b"ALGE"
WORD = 4
CITED = (("base", 0x08001830, "LDR", "r3, [pc, #0x17C]"),
         ("stride", 0x08001832, "LSL", "r1, r1, #0x3"),
         ("entry", 0x08001834, "ADD", "r3, r1, r3"),
         ("pick", 0x08001844, "LDR", "r3, [r3, r1]"))
FAMILIES = ((0x080109F0, 0x08010EC2),
            (0x08010EC4, 0x08010F82),
            (0x081C6224, 0x081C6335))
SLICE = re.compile(r"baserom\.gba_0x([0-9a-f]+)_0x([0-9a-f]+)\.extracted")


def inside(address, length=1):
    return ROM_BASE <= address and address + length <= ROM_BASE + ROM_SIZE


def word(image, address):
    if not inside(address, 4):
        raise ValueError("the word at 0x%08X is outside the image" % address)
    return int.from_bytes(image[address - ROM_BASE:address - ROM_BASE + 4], "little")


def immediate(operands):
    return int(operands.split("#", 1)[1].rstrip("]"), 16)


def pool(address, offset):
    return ((address + 4) & ~3) + offset


def cited(image):
    seen = {}
    for role, address, mnemonic, text in CITED:
        found = emit_code.decode(image, address, "thumb")
        if found != (mnemonic, text, 2):
            raise ValueError("the code at 0x%08X is %r, not %s %s"
                             % (address, found, mnemonic, text))
        seen[role] = (address, text)
    base = word(image, pool(seen["base"][0], immediate(seen["base"][1])))
    if base not in [family[0] for family in FAMILIES]:
        raise ValueError("the reader at 0x%08X names 0x%08X, not an emitted table"
                         % (seen["base"][0], base))
    return seen


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


def table_of(image, base, end):
    first = word(image, base)
    rows = (first - base) // WORD
    if rows <= 0 or base + WORD * rows != first:
        raise ValueError("the table at 0x%08X does not end where its first pointer 0x%08X begins"
                         % (base, first))
    if first >= end:
        raise ValueError("the table at 0x%08X pools at 0x%08X, past its end 0x%08X"
                         % (base, first, end))
    pointers = [word(image, base + WORD * index) for index in range(rows)]
    strings, starts, at = [], [], first
    for pointer in pointers:
        if pointer in starts:
            strings.append(starts.index(pointer))
            continue
        if pointer != at:
            raise ValueError("the pointer 0x%08X is not the tiling position 0x%08X"
                             % (pointer, at))
        if not inside(pointer, 1) or pointer >= end:
            raise ValueError("the string at 0x%08X is outside 0x%08X..0x%08X"
                             % (pointer, base, end))
        stop = image.index(b"\0", pointer - ROM_BASE)
        if ROM_BASE + stop + 1 > end:
            raise ValueError("the string at 0x%08X runs past its end 0x%08X" % (pointer, end))
        name = image[pointer - ROM_BASE:stop]
        if not name or any(byte < 0x20 or byte > 0x7E for byte in name):
            raise ValueError("the string at 0x%08X is not printable text" % pointer)
        starts.append(pointer)
        strings.append(len(starts) - 1)
        at = ROM_BASE + stop + 1
    if at != end:
        raise ValueError("the family at 0x%08X tiles 0x%08X, not its end 0x%08X"
                         % (base, at, end))
    return {"base": base, "pointers": pointers, "names": strings,
            "strings": [image[start - ROM_BASE:image.index(b"\0", start - ROM_BASE)]
                        for start in starts]}


def rebuild(measured):
    out = bytearray()
    for pointer in measured["pointers"]:
        out += struct.pack("<I", pointer)
    for name in measured["strings"]:
        out += name + b"\0"
    return bytes(out)


def decode(image):
    return [table_of(image, base, end) for base, end in FAMILIES]


def census(image):
    cited(image)
    trouble = problem(image)
    if trouble:
        raise ValueError(trouble)
    families = decode(image)
    total = 0
    for measured, (base, end) in zip(families, FAMILIES):
        blob = rebuild(measured)
        if blob != image[base - ROM_BASE:end - ROM_BASE]:
            raise ValueError("the family at 0x%08X does not re-encode from its rows" % base)
        total += len(blob)
    return {"families": len(families),
            "rows": sum(len(measured["pointers"]) for measured in families),
            "strings": sum(len(measured["strings"]) for measured in families),
            "bytes": total}


def run_name(begin, stop):
    return "..\\build\\text\\stream_0x%x_0x%x.bin" % (begin, stop)


def run_file(begin, stop):
    return os.path.join(OUT, "stream_0x%x_0x%x.bin" % (begin, stop))


def gap_name(begin, stop):
    return "baserom.gba_0x%x_0x%x.extracted" % (begin, stop)


def rewrite(text):
    spans = [(base - ROM_BASE, end - ROM_BASE) for base, end in FAMILIES]
    names = [run_name(begin, stop) for begin, stop in spans]
    if all(name in text for name in names):
        return text, []
    out, gaps, spliced = [], [], 0
    for line in text.splitlines():
        found = SLICE.search(line)
        if not found or "INCBIN" not in line:
            out.append(line)
            continue
        low, high = int(found.group(1), 16), int(found.group(2), 16)
        inner = [(begin, stop) for begin, stop in spans if low <= begin and stop <= high]
        if not inner:
            out.append(line)
            continue
        cursor = low
        for begin, stop in inner:
            if begin > cursor:
                out.append("\tINCBIN\t" + gap_name(cursor, begin))
                gaps.append((cursor, begin))
            out.append("\tINCBIN\t" + run_name(begin, stop))
            cursor = stop
            spliced += 1
        if cursor < high:
            out.append("\tINCBIN\t" + gap_name(cursor, high))
            gaps.append((cursor, high))
    if spliced != len(spans):
        raise ValueError("no INCBIN slice carries %d of %d families" % (len(spans) - spliced,
                                                                       len(spans)))
    return "\n".join(out) + "\n", gaps


def held(path, blob):
    if not os.path.exists(path):
        raise ValueError("%s is absent" % path)
    if open(path, "rb").read() != blob:
        raise ValueError("%s does not hold its bytes" % path)


def summary(measured):
    return "families=%d rows=%d strings=%d bytes=%d" % (
        measured["families"], measured["rows"], measured["strings"], measured["bytes"])


def write_spans(image):
    for base, end in FAMILIES:
        blob = rebuild(table_of(image, base, end))
        path = run_file(base - ROM_BASE, end - ROM_BASE)
        os.makedirs(OUT, exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(blob)
        held(path, image[base - ROM_BASE:end - ROM_BASE])


def build(image):
    measured = census(image)
    text, gaps = rewrite(open(ASM, encoding="utf-8", newline="").read())
    write_spans(image)
    for low, high in gaps:
        path = os.path.join(ROOT, gap_name(low, high))
        with open(path, "wb") as handle:
            handle.write(image[low:high])
        held(path, image[low:high])
    with open(ASM, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return measured


def check(image):
    measured = census(image)
    text = open(ASM, encoding="utf-8", newline="").read()
    if text != rewrite(text)[0]:
        print("TEXT FAIL: asm\\remainder.s is not the run list this image derives")
        return 1
    for base, end in FAMILIES:
        held(run_file(base - ROM_BASE, end - ROM_BASE),
             image[base - ROM_BASE:end - ROM_BASE])
    print(summary(measured))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["--write"], ["--check"]):
        print("usage: python tools\\research\\text_rows.py [--write|--check]")
        return 2
    if not os.path.exists(ROM):
        print("the text generator needs the retail image at %s" % ROM)
        return 1
    image = open(ROM, "rb").read()
    try:
        if argv == ["--check"]:
            return check(image)
        print(summary(build(image)))
    except ValueError as error:
        print("TEXT FAIL: %s" % error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
