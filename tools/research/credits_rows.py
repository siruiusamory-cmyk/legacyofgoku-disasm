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
OUT = os.path.join(ROOT, "build", "credits")
ROM_BASE = 0x08000000
ROM_SIZE = 8388608
GAME_CODE = b"ALGE"
BASE = 0x08010094
HEADER = 8
STRIDE = 4
ROWS = 0x8E
POOL = BASE + HEADER + ROWS * STRIDE
END = 0x0801082B
HEADER_FIELDS = ("h0", "h2", "h4", "h6")
CITED = (("count", 0x08001D28, "CMP", "r0, #0x8E"),
         ("base", 0x08001D2C, "LDR", "r1, [pc, #0x138]"),
         ("stride", 0x08001D2E, "LSL", "r0, r0, #0x2"),
         ("header", 0x08001D30, "ADD", "r1, #0x8"),
         ("read", 0x08001D32, "LDR", "r1, [r1, r0]"))
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


def bounds(image):
    seen = {}
    for role, address, mnemonic, text in CITED:
        found = emit_code.decode(image, address, "thumb")
        if found != (mnemonic, text, 2):
            raise ValueError("the code at 0x%08X is %r, not %s %s"
                             % (address, found, mnemonic, text))
        seen[role] = (address, text)
    base = word(image, pool(seen["base"][0], immediate(seen["base"][1])))
    stride = 1 << immediate(seen["stride"][1])
    header = immediate(seen["header"][1])
    rows = immediate(seen["count"][1])
    measured = (base, header, stride, rows)
    if measured != (BASE, HEADER, STRIDE, ROWS):
        raise ValueError("the code bounds the table at 0x%08X header 0x%X stride 0x%X rows %d, "
                         "not 0x%08X 0x%X 0x%X %d" % (measured + (BASE, HEADER, STRIDE, ROWS)))
    return measured


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


def string_at(image, pointer, stop):
    if not POOL <= pointer < stop:
        raise ValueError("the text pointer 0x%08X is outside the pool" % pointer)
    start = pointer - ROM_BASE
    end = image.index(b"\0", start)
    if end >= stop - ROM_BASE:
        raise ValueError("the text at 0x%08X runs past the family's end" % pointer)
    return image[start:end]


def decode(image):
    header = [int.from_bytes(image[BASE - ROM_BASE + 2 * index:
                                  BASE - ROM_BASE + 2 * index + 2], "little")
              for index in range(HEADER // 2)]
    pointers = [word(image, BASE + HEADER + index * STRIDE) for index in range(ROWS)]
    last = max(pointers)
    if last < POOL:
        raise ValueError("the table names no text")
    order, index_at, cursor = [], {}, POOL
    while cursor <= last:
        text = string_at(image, cursor, last + 0x100)
        index_at[cursor] = len(order)
        order.append(text)
        cursor += len(text) + 1
    if cursor > END:
        raise ValueError("the text ends at 0x%08X, past the family's end 0x%08X" % (cursor, END))
    rows = []
    for pointer in pointers:
        if pointer not in index_at:
            raise ValueError("the text pointer 0x%08X is outside the pool" % pointer)
        rows.append(index_at[pointer])
    return {"header": header, "rows": rows, "texts": order}


def rebuild(measured):
    starts, cursor = [], POOL
    for name in measured["texts"]:
        starts.append(cursor)
        cursor += len(name) + 1
    body = bytearray()
    for value in measured["header"]:
        body += value.to_bytes(2, "little")
    for index in measured["rows"]:
        body += struct.pack("<I", starts[index])
    for name in measured["texts"]:
        body += name + b"\0"
    return bytes(body)


def census(image):
    bounds(image)
    trouble = problem(image)
    if trouble:
        raise ValueError(trouble)
    measured = decode(image)
    blob = rebuild(measured)
    if blob != image[BASE - ROM_BASE:END - ROM_BASE]:
        raise ValueError("the family at 0x%08X does not re-encode from its rows" % BASE)
    return {"rows": len(measured["rows"]), "texts": len(measured["texts"]),
            "bytes": len(blob), "header": measured["header"], "row_list": measured}


def run_name(begin, stop):
    return "..\\build\\credits\\stream_0x%x_0x%x.bin" % (begin, stop)


def run_file(begin, stop):
    return os.path.join(OUT, "stream_0x%x_0x%x.bin" % (begin, stop))


def gap_name(begin, stop):
    return "baserom.gba_0x%x_0x%x.extracted" % (begin, stop)


def rewrite(text):
    first, last = BASE - ROM_BASE, END - ROM_BASE
    lines = text.splitlines()
    if any(os.path.basename(run_name(first, last)) in line for line in lines):
        return text, [(first, first), (last, last)]
    for index, line in enumerate(lines):
        found = SLICE.search(line)
        if not found or "INCBIN" not in line:
            continue
        low, high = int(found.group(1), 16), int(found.group(2), 16)
        if low <= first and last <= high:
            lines[index:index + 1] = ["\tINCBIN\t" + gap_name(low, first),
                                      "\tINCBIN\t" + run_name(first, last),
                                      "\tINCBIN\t" + gap_name(last, high)]
            return "\n".join(lines) + "\n", [(low, first), (last, high)]
    raise ValueError("no INCBIN slice carries the family")


def held(path, blob):
    if not os.path.exists(path):
        raise ValueError("%s is absent" % path)
    if open(path, "rb").read() != blob:
        raise ValueError("%s does not hold its bytes" % path)


def summary(measured):
    return "rows=%d texts=%d bytes=%d" % (measured["rows"], measured["texts"],
                                          measured["bytes"])


def build(image):
    measured = census(image)
    first, last = BASE - ROM_BASE, END - ROM_BASE
    text, gaps = rewrite(open(ASM, encoding="utf-8", newline="").read())
    blob = rebuild(measured["row_list"])
    os.makedirs(OUT, exist_ok=True)
    for low, high in gaps:
        if low == high:
            continue
        path = os.path.join(ROOT, gap_name(low, high))
        with open(path, "wb") as handle:
            handle.write(image[low:high])
        held(path, image[low:high])
    path = run_file(first, last)
    with open(path, "wb") as handle:
        handle.write(blob)
    held(path, image[first:last])
    with open(ASM, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return measured


def check(image):
    measured = census(image)
    first, last = BASE - ROM_BASE, END - ROM_BASE
    text = open(ASM, encoding="utf-8", newline="").read()
    if text != rewrite(text)[0]:
        print("CREDITS FAIL: asm\\remainder.s is not the run list this image derives")
        return 1
    held(run_file(first, last), image[first:last])
    print(summary(measured))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["--write"], ["--check"]):
        print("usage: python tools\\research\\credits_rows.py [--write|--check]")
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
        print("CREDITS FAIL: %s" % error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
