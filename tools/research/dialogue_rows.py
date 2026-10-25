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
OUT = os.path.join(ROOT, "build", "dialogue")
ROM_BASE = 0x08000000
ROM_SIZE = 8388608
GAME_CODE = b"ALGE"
BASE = 0x0815BF28
ROWS = 80
STRIDE = 4
NODE = 8
FIRST = BASE + ROWS * STRIDE
END = 0x08166731
TERMINATOR = 0xFF
CITED = (("base", 0x080051D2, "LDR", "r2, [pc, #0x1EC]"),
         ("stride", 0x080051D4, "LSL", "r1, r0, #0x2"),
         ("row", 0x080051D6, "LDR", "r1, [r2, r1]"),
         ("node", 0x08005208, "LSL", "r0, r0, #0x3"),
         ("entry", 0x0800520A, "ADD", "r4, r0, r1"),
         ("next", 0x0800520C, "LDRB", "r0, [r4, #0x1]"),
         ("kind", 0x08005212, "LDRB", "r0, [r4, #0x0]"),
         ("exit", 0x08005214, "CMP", "r0, #0xFF"),
         ("text", 0x080052B2, "LDR", "r1, [r4, #0x4]"))
TEXT_CITED = (("pointer", 0x08009350, "LDR", "r0, [r4, #0x14]"),
              ("byte", 0x08009358, "LDRB", "r0, [r0, #0x0]"),
              ("stop", 0x0800935A, "CMP", "r0, #0x0"))
SLICE = re.compile(r"baserom\.gba_0x([0-9a-f]+)_0x([0-9a-f]+)\.extracted")


def inside(address, length=1):
    return ROM_BASE <= address and address + length <= ROM_BASE + ROM_SIZE


def word(image, address):
    if not inside(address, 4):
        raise ValueError("the word at 0x%08X is outside the image" % address)
    return int.from_bytes(image[address - ROM_BASE:address - ROM_BASE + 4], "little")


def halfword(image, address):
    return int.from_bytes(image[address - ROM_BASE:address - ROM_BASE + 2], "little")


def immediate(operands):
    return int(operands.split("#", 1)[1].rstrip("]"), 16)


def pool(address, offset):
    return ((address + 4) & ~3) + offset


def cited(image, table):
    seen = {}
    for role, address, mnemonic, text in table:
        found = emit_code.decode(image, address, "thumb")
        if found != (mnemonic, text, 2):
            raise ValueError("the code at 0x%08X is %r, not %s %s"
                             % (address, found, mnemonic, text))
        seen[role] = (address, text)
    return seen


def bounds(image):
    seen = cited(image, CITED)
    base = word(image, pool(seen["base"][0], immediate(seen["base"][1])))
    stride = 1 << immediate(seen["stride"][1])
    node = 1 << immediate(seen["node"][1])
    rows = 0
    while inside(base + stride * rows, STRIDE) and \
            ROM_BASE <= word(image, base + stride * rows) < ROM_BASE + ROM_SIZE:
        rows += 1
    if (base, stride, node, rows) != (BASE, STRIDE, NODE, ROWS):
        raise ValueError("the code bounds the table at 0x%08X stride 0x%X node 0x%X rows %d, "
                         "not 0x%08X 0x%X 0x%X %d"
                         % (base, stride, node, rows, BASE, STRIDE, NODE, ROWS))
    return base, stride, node, rows


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


def nodes_of(image, base, stop):
    nodes, at = [], base
    while stop is None or at + NODE <= stop:
        kind = image[at - ROM_BASE]
        step = image[at - ROM_BASE + 1]
        if halfword(image, at + 2):
            break
        pointer = word(image, at + 4)
        if kind == TERMINATOR and pointer == 0:
            nodes.append((kind, step, None))
            at += NODE
            continue
        if inside(pointer, 1) and pointer >= base and pointer < END:
            nodes.append((kind, step, pointer))
            at += NODE
            continue
        break
    return nodes, at


def strings_of(image, start, stop):
    names, at = [], start
    while stop is None or at < stop:
        end = image.index(b"\0", at - ROM_BASE)
        if stop is not None and ROM_BASE + end >= stop:
            raise ValueError("the text at 0x%08X runs past the pool's end" % start)
        names.append(image[at - ROM_BASE:end])
        at = ROM_BASE + end + 1
        if stop is None and at < ROM_BASE + ROM_SIZE and image[at - ROM_BASE] == 0:
            break
    return names, at


def decode(image):
    cited(image, TEXT_CITED)
    table = [word(image, BASE + STRIDE * index) for index in range(ROWS)]
    bases = sorted(table)
    if len(set(table)) != ROWS:
        raise ValueError("the table names %d records, not %d" % (len(set(table)), ROWS))
    if bases[0] != FIRST:
        raise ValueError("the table's first record is at 0x%08X, not 0x%08X" % (bases[0], FIRST))
    records, rows = [], [bases.index(pointer) for pointer in table]
    for order, base in enumerate(bases):
        stop = bases[order + 1] if order + 1 < len(bases) else None
        nodes, text_start = nodes_of(image, base, stop)
        if not nodes:
            raise ValueError("the record at 0x%08X has no node" % base)
        if nodes[-1][0] != TERMINATOR:
            raise ValueError("the record at 0x%08X does not end its nodes on 0x%02X"
                             % (base, TERMINATOR))
        names, text_end = strings_of(image, text_start, stop)
        starts, cursor = [], text_start
        for name in names:
            starts.append(cursor)
            cursor += len(name) + 1
        if cursor != text_end:
            raise ValueError("the record at 0x%08X tiles 0x%08X, not 0x%08X"
                             % (base, cursor, text_end))
        entries = []
        for kind, step, pointer in nodes:
            if pointer is None:
                entries.append((kind, step, None))
                continue
            if pointer not in starts:
                raise ValueError("the text pointer 0x%08X is not a pool position" % pointer)
            if step >= len(nodes):
                raise ValueError("the node at 0x%08X steps to %d of %d nodes"
                                 % (base, step, len(nodes)))
            entries.append((kind, step, starts.index(pointer)))
        records.append({"base": base, "nodes": entries, "strings": names})
    if bases[-1] + NODE * len(records[-1]["nodes"]) + \
            sum(len(name) + 1 for name in records[-1]["strings"]) != END:
        raise ValueError("the record the last row names does not end at 0x%08X" % END)
    if sum(len(record["nodes"]) for record in records) < ROWS:
        raise ValueError("the family carries fewer nodes than rows")
    return {"rows": rows, "records": records,
            "nodes": sum(len(record["nodes"]) for record in records),
            "strings": sum(len(record["strings"]) for record in records)}


def rebuild(measured):
    records, out, base, placed = measured["records"], bytearray(), FIRST, []
    for record in records:
        if record["base"] != base:
            raise ValueError("the record at 0x%08X does not start at 0x%08X"
                             % (record["base"], base))
        starts, cursor = [], base + NODE * len(record["nodes"])
        for name in record["strings"]:
            starts.append(cursor)
            cursor += len(name) + 1
        nodes = bytearray()
        for kind, step, index in record["nodes"]:
            pointer = 0 if index is None else starts[index]
            nodes += struct.pack("<BBHI", kind, step, 0, pointer)
        out += nodes
        for name in record["strings"]:
            out += name + b"\0"
        placed.append(base)
        base = cursor
    if base != END:
        raise ValueError("the family ends at 0x%08X, not 0x%08X" % (base, END))
    table = bytearray()
    for row in measured["rows"]:
        table += struct.pack("<I", placed[row])
    return bytes(table + out)


def census(image):
    bounds(image)
    trouble = problem(image)
    if trouble:
        raise ValueError(trouble)
    measured = decode(image)
    blob = rebuild(measured)
    if blob != image[BASE - ROM_BASE:END - ROM_BASE]:
        raise ValueError("the family at 0x%08X does not re-encode from its rows" % BASE)
    return {"rows": len(measured["rows"]), "records": len(measured["records"]),
            "nodes": measured["nodes"], "strings": measured["strings"], "bytes": len(blob)}


def run_name(begin, stop):
    return "..\\build\\dialogue\\stream_0x%x_0x%x.bin" % (begin, stop)


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
    return "rows=%d records=%d nodes=%d strings=%d bytes=%d" % (
        measured["rows"], measured["records"], measured["nodes"],
        measured["strings"], measured["bytes"])


def build(image):
    measured = census(image)
    first, last = BASE - ROM_BASE, END - ROM_BASE
    text, gaps = rewrite(open(ASM, encoding="utf-8", newline="").read())
    blob = rebuild(decode(image))
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
        print("DIALOGUE FAIL: asm\\remainder.s is not the run list this image derives")
        return 1
    held(run_file(first, last), image[first:last])
    print(summary(measured))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["--write"], ["--check"]):
        print("usage: python tools\\research\\dialogue_rows.py [--write|--check]")
        return 2
    if not os.path.exists(ROM):
        print("the dialogue generator needs the retail image at %s" % ROM)
        return 1
    image = open(ROM, "rb").read()
    try:
        if argv == ["--check"]:
            return check(image)
        print(summary(build(image)))
    except ValueError as error:
        print("DIALOGUE FAIL: %s" % error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
