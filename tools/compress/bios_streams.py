from __future__ import annotations

import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ROM = os.path.join(ROOT, "baserom.gba")
ASM = os.path.join(ROOT, "asm", "remainder.s")
OUT = os.path.join(ROOT, "build", "bios")
ROM_BASE = 0x08000000
STREAMS = (0x081BDC1C,)
SLICE = re.compile(r"baserom\.gba_0x([0-9a-f]+)_0x([0-9a-f]+)\.extracted")


def decode(rom, start):
    cursor = start - ROM_BASE
    if rom[cursor] != 0x10:
        raise ValueError("the stream at 0x%08X is not LZ77" % start)
    size = rom[cursor + 1] | rom[cursor + 2] << 8 | rom[cursor + 3] << 16
    cursor += 4
    out = bytearray()
    while len(out) < size:
        flags = rom[cursor]
        cursor += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                pair = rom[cursor] << 8 | rom[cursor + 1]
                cursor += 2
                for _step in range((pair >> 12) + 3):
                    out.append(out[-((pair & 0xFFF) + 1)])
            else:
                out.append(rom[cursor])
                cursor += 1
    return bytes(out), cursor - (start - ROM_BASE)


def encode(body):
    out = bytearray(struct.pack("<B", 0x10) + len(body).to_bytes(3, "little"))
    at = 0
    while at < len(body):
        flag_at = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if at >= len(body):
                break
            length, distance = 0, 0
            for back in range(1, min(at, 4096) + 1):
                run = 0
                while (run < 18 and at + run < len(body)
                       and body[at + run] == body[at - back + run]):
                    run += 1
                if run > length:
                    length, distance = run, back
            if length >= 3:
                flags |= 0x80 >> bit
                out += struct.pack(">H", (length - 3) << 12 | (distance - 1))
                at += length
            else:
                out.append(body[at])
                at += 1
        out[flag_at] = flags
    return bytes(out)


def gap_name(start, stop):
    return "baserom.gba_0x%x_0x%x.extracted" % (start, stop)


def run_name(start, stop):
    return "..\\build\\bios\\stream_0x%x_0x%x.bin" % (start, stop)


def run_file(start, stop):
    return os.path.join(OUT, "stream_0x%x_0x%x.bin" % (start, stop))


def measured(image):
    rows = []
    for start in STREAMS:
        body, stored = decode(image, start)
        again = encode(body)
        if again != image[start - ROM_BASE:start - ROM_BASE + stored]:
            raise ValueError("the stream at 0x%08X is not re-encoded byte for byte" % start)
        rows.append({"start": start, "stop": start + stored, "body": again,
                     "decoded": len(body)})
    return rows


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
    rows = measured(image)
    runs = [(row["start"] - ROM_BASE, row["stop"] - ROM_BASE) for row in rows]
    text, slices = rewrite(open(ASM, encoding="utf-8", newline="").read(), runs)
    os.makedirs(OUT, exist_ok=True)
    for first, last in slices:
        path = os.path.join(ROOT, gap_name(first, last))
        with open(path, "wb") as handle:
            handle.write(image[first:last])
        held(path, image[first:last])
    for row in rows:
        blob = row["body"]
        if blob != image[row["start"] - ROM_BASE:row["stop"] - ROM_BASE]:
            raise ValueError("the run at 0x%08X is not the image's bytes" % row["start"])
        path = run_file(row["start"] - ROM_BASE, row["stop"] - ROM_BASE)
        with open(path, "wb") as handle:
            handle.write(blob)
        held(path, blob)
    return rows, runs, text


def summary(rows):
    return ("streams=%d decoded=%d stored=%d"
            % (len(rows), sum(row["decoded"] for row in rows),
               sum(row["stop"] - row["start"] for row in rows)))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["--write"], ["--check"]):
        print("usage: python tools\\compress\\bios_streams.py [--write|--check]")
        return 2
    if not os.path.exists(ROM):
        print("the BIOS stream generator needs the retail image at %s" % ROM)
        return 1
    image = open(ROM, "rb").read()
    if argv == ["--check"]:
        rows = measured(image)
        runs = [(row["start"] - ROM_BASE, row["stop"] - ROM_BASE) for row in rows]
        text, slices = rewrite(open(ASM, encoding="utf-8", newline="").read(), runs)
        if open(ASM, encoding="utf-8", newline="").read() != text:
            print("STREAMS FAIL: asm\\remainder.s is not the token list this image derives")
            return 1
        for first, last in slices:
            held(os.path.join(ROOT, gap_name(first, last)), image[first:last])
        for row in rows:
            held(run_file(row["start"] - ROM_BASE, row["stop"] - ROM_BASE),
                 image[row["start"] - ROM_BASE:row["stop"] - ROM_BASE])
        print(summary(rows))
        return 0
    rows, runs, text = build(image)
    with open(ASM, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(summary(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
