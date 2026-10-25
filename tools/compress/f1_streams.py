from __future__ import annotations

import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "research"))

import f1_population

ROM = os.path.join(ROOT, "baserom.gba")
ASM = os.path.join(ROOT, "asm", "remainder.s")
OUT = os.path.join(ROOT, "build", "f1")
ROM_BASE = 0x08000000
HEADERS = (0x081CA168, 0x08337248, 0x084E4F44)
RECORD_HEADER = f1_population.RECORD_HEADER
ENTRY_HEADER = f1_population.ENTRY_HEADER
ROW_STREAM = f1_population.ROW_STREAM
LIST_TAG = f1_population.LIST_TAG
REPEAT_UNIT = f1_population.REPEAT_UNIT
SLICE = re.compile(r"baserom\.gba_0x([0-9a-f]+)_0x([0-9a-f]+)\.extracted")


def gap_name(start, stop):
    return "baserom.gba_0x%x_0x%x.extracted" % (start, stop)


def run_name(start, stop):
    return "..\\build\\f1\\stream_0x%x_0x%x.bin" % (start, stop)


def run_file(start, stop):
    return os.path.join(OUT, "stream_0x%x_0x%x.bin" % (start, stop))


def encode(rom, body):
    out = bytearray(struct.pack("<HH", f1_population.half(rom, body),
                                f1_population.half(rom, body + 2)))
    for tokens in f1_population.token_rows(rom, body):
        out.append(len(tokens))
        for skip, kind, chunk in tokens:
            out.append(skip)
            if kind == "lit":
                out.append(len(chunk))
                out += chunk
            else:
                out.append(REPEAT_UNIT - len(chunk))
                out += chunk[:1]
    return bytes(out)


def record(rom, start, size):
    rebuilt = bytearray(struct.pack("<IHH", size, LIST_TAG,
                                    f1_population.half(rom, start + 6)) + b"\0" * 8)
    for at, entry_size, kind in f1_population.entries(rom, start, size):
        if kind != ROW_STREAM:
            return None, "type %d at 0x%08X is not a row stream" % (kind, at)
        body = at + ENTRY_HEADER
        stream = f1_population.decode(rom, body)
        if stream["consumed"] != entry_size - ENTRY_HEADER:
            return None, ("the stream at 0x%08X consumes %d of %d"
                          % (body, stream["consumed"], entry_size - ENTRY_HEADER))
        encoded = encode(rom, body)
        if encoded != rom[body - ROM_BASE:at - ROM_BASE + entry_size]:
            return None, "the stream at 0x%08X is not re-encoded byte for byte" % body
        rebuilt += struct.pack("<IH", entry_size, kind) + encoded
    if bytes(rebuilt) != rom[start - ROM_BASE:start - ROM_BASE + size]:
        return None, "the record at 0x%08X is not rebuilt from its fields" % start
    return bytes(rebuilt), None


def census(rom):
    measured = []
    for header in HEADERS:
        found = f1_population.walk(rom, header)
        if len(found["records"]) != found["count"]:
            raise ValueError("the list at 0x%08X stops after %d of %d records"
                             % (header, len(found["records"]), found["count"]))
        rebuilt, left = [], []
        for start, size in found["records"]:
            try:
                blob, reason = record(rom, start, size)
            except ValueError as problem:
                blob, reason = None, str(problem)
            if blob is None:
                left.append((start, size, reason))
            else:
                rebuilt.append((start, size, blob))
        measured.append({"header": header, "walk": found, "rebuilt": rebuilt, "left": left})
    return measured


def promoted(measured):
    out = []
    for row in measured:
        for start, size, _blob in row["rebuilt"]:
            if out and out[-1][1] == start:
                out[-1][1] = start + size
            else:
                out.append([start, start + size])
    return [tuple(run) for run in out]


def pieces(start, stop, runs):
    marks = {start, stop}
    for first, last in runs:
        for edge in (first, last):
            if start < edge < stop:
                marks.add(edge)
    ordered = sorted(marks)
    out = []
    for first, last in zip(ordered, ordered[1:]):
        inside = any(begin <= first and last <= end for begin, end in runs)
        out.append((first, last, "run" if inside else "gap"))
    return out


def rewrite(text, runs):
    lines, slices = [], []
    for line in text.splitlines():
        found = SLICE.search(line)
        if not found or "INCBIN" not in line:
            lines.append(line)
            continue
        first, last = int(found.group(1), 16), int(found.group(2), 16)
        if not any(begin < last and first < end for begin, end in runs):
            lines.append(line)
            continue
        for begin, stop, kind in pieces(first, last, runs):
            if kind == "run":
                lines.append("\tINCBIN\t" + run_name(begin, stop))
            else:
                lines.append("\tINCBIN\t" + gap_name(begin, stop))
                slices.append((begin, stop))
    return "\n".join(lines) + "\n", slices


def held(path, blob):
    if not os.path.exists(path):
        raise ValueError("%s is absent" % path)
    if open(path, "rb").read() != blob:
        raise ValueError("%s does not hold its bytes" % path)


def build(image):
    measured = census(image)
    runs = [(first - ROM_BASE, last - ROM_BASE) for first, last in promoted(measured)]
    text, slices = rewrite(open(ASM, encoding="utf-8", newline="").read(), runs)
    os.makedirs(OUT, exist_ok=True)
    for first, last in slices:
        path = os.path.join(ROOT, gap_name(first, last))
        with open(path, "wb") as handle:
            handle.write(image[first:last])
        held(path, image[first:last])
    blobs = {}
    for row in measured:
        for start, _size, blob in row["rebuilt"]:
            blobs[start - ROM_BASE] = blob
    for first, last in runs:
        blob = b"".join(blobs[at] for at in sorted(blobs) if first <= at < last)
        if blob != image[first:last]:
            raise ValueError("the rebuilt run 0x%X..0x%X is not the image's bytes" % (first, last))
        path = run_file(first, last)
        with open(path, "wb") as handle:
            handle.write(blob)
        held(path, blob)
    return measured, runs, text


def summary(measured, runs):
    records = sum(len(row["walk"]["records"]) for row in measured)
    rebuilt = sum(len(row["rebuilt"]) for row in measured)
    kept = sum(size for row in measured for _start, size, _blob in row["rebuilt"])
    left = sum(len(row["left"]) for row in measured)
    return ("lists=%d records=%d rebuilt=%d bytes=%d left=%d runs=%d"
            % (len(measured), records, rebuilt, kept, left, len(runs)))


def refusals(measured):
    return ["left %08X %6d B  %s" % (start, size, reason)
            for row in measured for start, size, reason in row["left"]]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["--write"], ["--check"]):
        print("usage: python tools\\compress\\f1_streams.py [--write|--check]")
        return 2
    if not os.path.exists(ROM):
        print("the stream generator needs the retail image at %s" % ROM)
        return 1
    image = open(ROM, "rb").read()
    if argv == ["--check"]:
        measured = census(image)
        runs = [(first - ROM_BASE, last - ROM_BASE) for first, last in promoted(measured)]
        text, slices = rewrite(open(ASM, encoding="utf-8", newline="").read(), runs)
        if open(ASM, encoding="utf-8", newline="").read() != text:
            print("STREAMS FAIL: asm\\remainder.s is not the token list this image derives")
            return 1
        for first, last in slices:
            held(os.path.join(ROOT, gap_name(first, last)), image[first:last])
        for first, last in runs:
            held(run_file(first, last), image[first:last])
        print(summary(measured, runs))
        return 0
    measured, runs, text = build(image)
    with open(ASM, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(summary(measured, runs))
    for line in refusals(measured):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
