from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "code"))

import emit_code

ROM = os.path.join(ROOT, "baserom.gba")
ASM = os.path.join(ROOT, "asm", "remainder.s")
SHA1 = os.path.join(ROOT, "baserom.sha1")
OUT = os.path.join(ROOT, "build", "messages")
ROM_BASE = 0x08000000
ROM_SIZE = 8388608
GAME_CODE = b"ALGE"
MESSAGES = 0x085C2DE2
MESSAGES_END = 0x085C2F86
MESSAGE_COUNT = 6
TABLE = 0x085C2FB8
ROWS = 31
STRIDE = 4
TABLE_END = 0x085C31EC
LOW, HIGH = 0x20, 0x7E
MESSAGE_CITED = (("message", 0x08004ABE, "LDR", "r1, [pc, #0x44]"),
                 ("message", 0x08004B20, "LDR", "r1, [pc, #0x10]"),
                 ("message", 0x08000FC0, "LDR", "r1, [pc, #0x90]"),
                 ("message", 0x08005BC8, "LDR", "r1, [pc, #0x120]"),
                 ("message", 0x0800D0C0, "LDR", "r1, [pc, #0x184]"),
                 ("message", 0x0800D0BA, "LDR", "r1, [pc, #0x188]"))
TABLE_CITED = (("base", 0x08004A8A, "LDR", "r1, [pc, #0x1C]"),
               ("base", 0x0800D1D4, "LDR", "r1, [pc, #0x88]"),
               ("base", 0x0800D1F8, "LDR", "r1, [pc, #0x64]"),
               ("stride", 0x08004A8C, "LSL", "r0, r0, #0x2"),
               ("stride", 0x0800D1D2, "LSL", "r0, r1, #0x2"),
               ("stride", 0x0800D1F6, "LSL", "r0, r1, #0x2"),
               ("row", 0x08004A8E, "LDR", "r1, [r1, r0]"),
               ("row", 0x0800D1D6, "LDR", "r1, [r1, r0]"),
               ("row", 0x0800D1FA, "LDR", "r1, [r1, r0]"),
               ("end", 0x080010EA, "LDR", "r0, [pc, #0x19C]"),
               ("end", 0x08001182, "LDR", "r0, [pc, #0x104]"),
               ("end", 0x080051E8, "LDR", "r0, [pc, #0x1D8]"),
               ("end", 0x08004E5E, "LDR", "r0, [pc, #0x78]"))
SLICE = re.compile(r"baserom\.gba_0x([0-9a-f]+)_0x([0-9a-f]+)\.extracted")
SPANS = ((MESSAGES, MESSAGES_END), (TABLE, TABLE_END))


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


def cited(image, table):
    seen = {}
    for role, address, mnemonic, text in table:
        found = emit_code.decode(image, address, "thumb")
        if found != (mnemonic, text, 2):
            raise ValueError("the code at 0x%08X is %r, not %s %s"
                             % (address, found, mnemonic, text))
        if "[pc," in text:
            seen.setdefault(role, []).append(word(image, pool(address, immediate(text))))
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


def strings_of(image, start, stop):
    names, at = [], start
    while at < stop:
        end = image.index(b"\0", at - ROM_BASE)
        if ROM_BASE + end >= stop:
            raise ValueError("the text at 0x%08X runs past 0x%08X" % (at, stop))
        name = image[at - ROM_BASE:end]
        if not name or any(byte < LOW or byte > HIGH for byte in name):
            raise ValueError("the text at 0x%08X is not printable text" % at)
        names.append(name)
        at = ROM_BASE + end + 1
    return names


def messages(image):
    starts = sorted(cited(image, MESSAGE_CITED)["message"])
    if len(starts) != MESSAGE_COUNT or starts[0] != MESSAGES:
        raise ValueError("the code names %d messages at 0x%08X, not %d at 0x%08X"
                         % (len(starts), starts[0], MESSAGE_COUNT, MESSAGES))
    names = []
    for index, start in enumerate(starts):
        stop = starts[index + 1] if index + 1 < len(starts) else MESSAGES_END
        found = strings_of(image, start, stop)
        if len(found) != 1:
            raise ValueError("the message at 0x%08X is %d strings, not one" % (start, len(found)))
        names.append((start, found[0]))
    if starts[-1] + len(names[-1][1]) + 1 != MESSAGES_END:
        raise ValueError("the last message ends at 0x%08X, not 0x%08X"
                         % (starts[-1] + len(names[-1][1]) + 1, MESSAGES_END))
    return names


def table(image):
    seen = cited(image, TABLE_CITED)
    if set(seen["base"]) != {TABLE}:
        raise ValueError("the code names the table at %s, not 0x%08X"
                         % (["0x%08X" % base for base in seen["base"]], TABLE))
    if {1 << immediate(text) for _role, _address, mnemonic, text
            in TABLE_CITED if mnemonic == "LSL"} != {STRIDE}:
        raise ValueError("the code scales a row by something other than %d" % STRIDE)
    rows, at = [], TABLE
    while inside(at, STRIDE) and inside(word(image, at), 1):
        rows.append(word(image, at))
        at += STRIDE
    if len(rows) != ROWS:
        raise ValueError("the pointer run at 0x%08X is %d rows, not %d" % (TABLE, len(rows), ROWS))
    if rows != sorted(rows):
        raise ValueError("the rows at 0x%08X do not ascend" % TABLE)
    pad = rows[0] - (TABLE + ROWS * STRIDE)
    if not 0 <= pad <= 0x10 or any(image[TABLE + ROWS * STRIDE - ROM_BASE:
                                      TABLE + ROWS * STRIDE + pad - ROM_BASE]):
        raise ValueError("the table at 0x%08X does not clear %d B before its pool" % (TABLE, pad))
    starts = sorted(set(rows))
    if starts[0] != rows[0]:
        raise ValueError("the table's first row 0x%08X is not the pool's first string 0x%08X"
                         % (rows[0], starts[0]))
    pool_names = []
    for index, start in enumerate(starts):
        stop = starts[index + 1] if index + 1 < len(starts) else TABLE_END
        found = strings_of(image, start, stop)
        if len(found) != 1:
            raise ValueError("the row target 0x%08X is %d strings, not one" % (start, len(found)))
        pool_names.append((start, found[0]))
    if starts[-1] + len(pool_names[-1][1]) + 1 != TABLE_END:
        raise ValueError("the pool ends at 0x%08X, not 0x%08X"
                         % (starts[-1] + len(pool_names[-1][1]) + 1, TABLE_END))
    order = [starts.index(row) for row in rows]
    return {"rows": order, "pool": pool_names, "pad": pad}


def rebuild_messages(names):
    out = bytearray()
    for start, name in names:
        if start != MESSAGES + len(out):
            raise ValueError("the message at 0x%08X does not start at 0x%08X"
                             % (start, MESSAGES + len(out)))
        out += name + b"\0"
    if MESSAGES + len(out) != MESSAGES_END:
        raise ValueError("the messages end at 0x%08X, not 0x%08X"
                         % (MESSAGES + len(out), MESSAGES_END))
    return bytes(out)


def rebuild_table(measured):
    rows, out = measured["rows"], bytearray()
    for _start, name in measured["pool"]:
        out += name + b"\0"
    starts, at = [], TABLE + ROWS * STRIDE + measured["pad"]
    for _start, name in measured["pool"]:
        starts.append(at)
        at += len(name) + 1
    head = bytearray()
    for index in rows:
        head += int(starts[index]).to_bytes(4, "little")
    blob = bytes(head) + bytes(measured["pad"]) + bytes(out)
    if TABLE + len(blob) != TABLE_END:
        raise ValueError("the table family ends at 0x%08X, not 0x%08X"
                         % (TABLE + len(blob), TABLE_END))
    return blob


def census(image):
    trouble = problem(image)
    if trouble:
        raise ValueError(trouble)
    names = messages(image)
    measured = table(image)
    first, second = rebuild_messages(names), rebuild_table(measured)
    if first != image[MESSAGES - ROM_BASE:MESSAGES_END - ROM_BASE]:
        raise ValueError("the messages at 0x%08X do not re-encode from their rows" % MESSAGES)
    if second != image[TABLE - ROM_BASE:TABLE_END - ROM_BASE]:
        raise ValueError("the table at 0x%08X does not re-encode from its rows" % TABLE)
    return {"messages": len(names), "rows": len(measured["rows"]),
            "strings": len(measured["pool"]), "bytes": len(first) + len(second)}


def run_name(begin, stop):
    return "..\\build\\messages\\stream_0x%x_0x%x.bin" % (begin, stop)


def run_file(begin, stop):
    return os.path.join(OUT, "stream_0x%x_0x%x.bin" % (begin, stop))


def gap_name(begin, stop):
    return "baserom.gba_0x%x_0x%x.extracted" % (begin, stop)


def place(text, begin, stop):
    lines = text.splitlines()
    if any(os.path.basename(run_name(begin, stop)) in line for line in lines):
        return text, []
    for index, line in enumerate(lines):
        found = SLICE.search(line)
        if not found or "INCBIN" not in line:
            continue
        low, high = int(found.group(1), 16), int(found.group(2), 16)
        if low <= begin and stop <= high:
            parts, gaps = [], []
            if low < begin:
                parts.append("\tINCBIN\t" + gap_name(low, begin))
                gaps.append((low, begin))
            parts.append("\tINCBIN\t" + run_name(begin, stop))
            if stop < high:
                parts.append("\tINCBIN\t" + gap_name(stop, high))
                gaps.append((stop, high))
            lines[index:index + 1] = parts
            return "\n".join(lines) + "\n", gaps
    raise ValueError("no INCBIN slice carries 0x%08X..0x%08X" % (begin, stop))


def held(path, blob):
    if not os.path.exists(path):
        raise ValueError("%s is absent" % path)
    if open(path, "rb").read() != blob:
        raise ValueError("%s does not hold its bytes" % path)


def derived(text):
    gaps = []
    for begin, stop in SPANS:
        text, found = place(text, begin - ROM_BASE, stop - ROM_BASE)
        gaps += found
    return text, gaps


def summary(measured):
    return "messages=%d rows=%d strings=%d bytes=%d" % (
        measured["messages"], measured["rows"], measured["strings"], measured["bytes"])


def build(image):
    measured = census(image)
    text, gaps = derived(open(ASM, encoding="utf-8", newline="").read())
    os.makedirs(OUT, exist_ok=True)
    for low, high in gaps:
        path = os.path.join(ROOT, gap_name(low, high))
        with open(path, "wb") as handle:
            handle.write(image[low:high])
        held(path, image[low:high])
    for begin, stop in SPANS:
        path = run_file(begin - ROM_BASE, stop - ROM_BASE)
        with open(path, "wb") as handle:
            handle.write(image[begin - ROM_BASE:stop - ROM_BASE])
        held(path, image[begin - ROM_BASE:stop - ROM_BASE])
    with open(ASM, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return measured


def check(image):
    measured = census(image)
    text = open(ASM, encoding="utf-8", newline="").read()
    if text != derived(text)[0]:
        print("MESSAGES FAIL: asm\\remainder.s is not the run list this image derives")
        return 1
    for begin, stop in SPANS:
        held(run_file(begin - ROM_BASE, stop - ROM_BASE),
             image[begin - ROM_BASE:stop - ROM_BASE])
    print(summary(measured))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["--write"], ["--check"]):
        print("usage: python tools\\research\\message_rows.py [--write|--check]")
        return 2
    if not os.path.exists(ROM):
        print("the message generator needs the retail image at %s" % ROM)
        return 1
    image = open(ROM, "rb").read()
    try:
        if argv == ["--check"]:
            return check(image)
        print(summary(build(image)))
    except ValueError as error:
        print("MESSAGES FAIL: %s" % error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
