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
OUT = os.path.join(ROOT, "build", "actors")
ROM_BASE = 0x08000000
ROM_SIZE = 8388608
GAME_CODE = b"ALGE"
BASE = 0x086B6094
END = 0x086B6A78
STRIDE = 0x40
ROWS = 35
POOL = BASE + ROWS * STRIDE
CITED = (("base", 0x08006E68, "LDR", "r1, [pc, #0x31C]"),
         ("stride", 0x08006E6A, "LSL", "r0, r2, #0x6"),
         ("keep", 0x08006D9E, "BLT", "|loc_08006E66|"),
         ("count", 0x08006DA0, "CMP", "r2, #0x22"),
         ("end", 0x0800481C, "LDR", "r2, [pc, #0x170]"))
FIELDS = (("id", 0x00, 4, False), ("class", 0x08, 2, False), ("reserved_a", 0x0A, 2, False),
          ("counter", 0x0C, 4, False), ("h10", 0x10, 2, False), ("h12", 0x12, 2, False),
          ("h14", 0x14, 2, False), ("h16", 0x16, 2, False), ("s18", 0x18, 2, True),
          ("h1a", 0x1A, 2, False), ("h1c", 0x1C, 2, False), ("s1e", 0x1E, 2, True),
          ("s20", 0x20, 2, True), ("s22", 0x22, 2, True), ("s24", 0x24, 2, True),
          ("s26", 0x26, 2, True), ("s28", 0x28, 2, True), ("s2a", 0x2A, 2, True),
          ("s2c", 0x2C, 2, True), ("s2e", 0x2E, 2, True), ("s30", 0x30, 2, True),
          ("s32", 0x32, 2, True), ("ep", 0x34, 4, False), ("hp", 0x38, 4, False),
          ("damage", 0x3C, 4, False))
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
    end = word(image, pool(seen["end"][0], immediate(seen["end"][1])))
    stride = 1 << immediate(seen["stride"][1])
    rows = immediate(seen["count"][1]) + 1
    measured = (base, stride, rows, end)
    if measured != (BASE, STRIDE, ROWS, END):
        raise ValueError("the code bounds the family at 0x%08X stride 0x%X rows %d end 0x%08X, "
                         "not 0x%08X 0x%X %d 0x%08X" % (measured + (BASE, STRIDE, ROWS, END)))
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


def name_at(image, pointer):
    if not POOL <= pointer < END:
        raise ValueError("the name pointer 0x%08X is outside the pool" % pointer)
    start = pointer - ROM_BASE
    stop = image.index(b"\0", start)
    if stop > END - ROM_BASE:
        raise ValueError("the name at 0x%08X runs past the family's end" % pointer)
    name = image[start:stop]
    if not name or any(byte < 0x20 or byte >= 0x7F for byte in name):
        raise ValueError("the name at 0x%08X is not printable ASCII" % pointer)
    return name.decode("ascii")


def decode(image):
    rows, offsets = [], {}
    for index in range(ROWS):
        at = BASE - ROM_BASE + index * STRIDE
        record = {"index": index, "name": ""}
        for name, offset, width, signed in FIELDS:
            record[name] = int.from_bytes(image[at + offset:at + offset + width], "little",
                                          signed=signed)
        pointer = word(image, BASE + index * STRIDE + 4)
        if pointer:
            record["name"] = name_at(image, pointer)
            offsets.setdefault(record["name"], pointer)
        rows.append(record)
    return rows, offsets


def rebuild(rows):
    order = []
    for row in sorted(rows, key=lambda row: row["index"]):
        if row["name"] and row["name"] not in order:
            order.append(row["name"])
    starts, cursor = {}, POOL
    for name in order:
        starts[name] = cursor
        cursor += len(name) + 1
    if cursor > END:
        raise ValueError("the names end at 0x%08X, past the family's end" % cursor)
    body = bytearray(END - BASE)
    for row in rows:
        at = row["index"] * STRIDE
        for name, offset, width, signed in FIELDS:
            body[at + offset:at + offset + width] = int(row[name]).to_bytes(
                width, "little", signed=signed)
        if row["name"]:
            body[at + 4:at + 8] = struct.pack("<I", starts[row["name"]])
    for name in order:
        at = starts[name] - BASE
        body[at:at + len(name) + 1] = name.encode("ascii") + b"\0"
    return bytes(body)


def census(image):
    bounds(image)
    trouble = problem(image)
    if trouble:
        raise ValueError(trouble)
    rows, offsets = decode(image)
    blob = rebuild(rows)
    if blob != image[BASE - ROM_BASE:END - ROM_BASE]:
        raise ValueError("the family at 0x%08X does not re-encode from its rows" % BASE)
    return {"rows": len(rows), "named": sum(1 for row in rows if row["name"]),
            "names": len(offsets), "bytes": len(blob), "row_list": rows}


def run_name(begin, stop):
    return "..\\build\\actors\\stream_0x%x_0x%x.bin" % (begin, stop)


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
    return "rows=%d named=%d names=%d bytes=%d" % (
        measured["rows"], measured["named"], measured["names"], measured["bytes"])


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
        print("ACTORS FAIL: asm\\remainder.s is not the run list this image derives")
        return 1
    held(run_file(first, last), image[first:last])
    print(summary(measured))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["--write"], ["--check"]):
        print("usage: python tools\\research\\actor_rows.py [--write|--check]")
        return 2
    if not os.path.exists(ROM):
        print("the row generator needs the retail image at %s" % ROM)
        return 1
    image = open(ROM, "rb").read()
    try:
        if argv == ["--check"]:
            return check(image)
        print(summary(build(image)))
    except ValueError as error:
        print("ACTORS FAIL: %s" % error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
