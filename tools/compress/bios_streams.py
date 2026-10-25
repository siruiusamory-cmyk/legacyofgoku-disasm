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
HUFFMAN = (0x0815B2FC, 0x0819AC74, 0x0819BCE8, 0x081B3520, 0x084DEDE4,
           0x0853E34C, 0x08541DB8, 0x085C31F8, 0x085C3888, 0x085C4A0C)
REFUSED = (0x0818A3A8,)
DESCRIPTOR_STRIDE = 12
SLICE = re.compile(r"baserom\.gba_0x([0-9a-f]+)_0x([0-9a-f]+)\.extracted")


def lz77_decode(rom, start):
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


def lz77_encode(body):
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


def huffman_header(rom, start):
    offset = start - ROM_BASE
    kind = rom[offset] & 0xF
    if kind not in (4, 8) or rom[offset] not in (0x24, 0x28):
        raise ValueError("the stream at 0x%08X is not Huffman" % start)
    size = rom[offset + 1] | rom[offset + 2] << 8 | rom[offset + 3] << 16
    return kind, size, rom[offset + 4]


def huffman_counts(rom, start):
    kind, size, b4 = huffman_header(rom, start)
    return kind, size, 8 if kind == 4 else 4


def huffman_symbols(rom, start):
    kind, size, b4 = huffman_header(rom, start)
    root = start - ROM_BASE + 5
    cursor = start - ROM_BASE + 4 + 2 * (b4 + 1)
    out = []
    word, used, node = 0, 32, root
    need = size * 2 if kind == 4 else size
    while len(out) < need:
        if used == 32:
            word = int.from_bytes(rom[cursor:cursor + 4], "little")
            cursor += 4
            used = 0
        bit = word >> 31
        word = (word << 1) & 0xFFFFFFFF
        used += 1
        byte = rom[node]
        child = (node & ~1) + ((byte & 0x3F) + 1) * 2 + bit
        if (byte << bit) & 0x80:
            out.append(rom[child] & (0xFF if kind == 8 else 0xF))
            node = root
        else:
            node = child
    return out, cursor - (start - ROM_BASE)


def huffman_codes(rom, start):
    kind, _size, b4 = huffman_header(rom, start)
    root = start - ROM_BASE + 5
    table = {}
    parents = {}
    stack = [(root, 0, 0)]
    while stack:
        node, path, depth = stack.pop()
        byte = rom[node]
        for bit in (0, 1):
            child = (node & ~1) + ((byte & 0x3F) + 1) * 2 + bit
            parents[child] = parents.get(child, 0) + 1
            if byte << bit & 0x80:
                table.setdefault(rom[child] & (0xFF if kind == 8 else 0xF),
                                 (path << 1 | bit, depth + 1))
            else:
                stack.append((child, path << 1 | bit, depth + 1))
    if any(count > 1 for count in parents.values()):
        raise ValueError("the tree at 0x%08X shares a node, so no symbol has one code" % start)
    return table


def huffman_pack(kind, symbols):
    width = 4 if kind == 4 else 8
    group = 8 if kind == 4 else 4
    out = bytearray()
    for at in range(0, len(symbols), group):
        word = 0
        for symbol in symbols[at:at + group]:
            word = (word << width) | symbol
        out += word.to_bytes(4, "little")
    return bytes(out)


def huffman_unpack(kind, body):
    width = 4 if kind == 4 else 8
    out = []
    for at in range(0, len(body), 4):
        word = int.from_bytes(body[at:at + 4], "little")
        for shift in range(32 - width, -1, -width):
            out.append((word >> shift) & ((1 << width) - 1))
    return out


def huffman_encode(rom, start, body):
    kind, size, b4 = huffman_header(rom, start)
    if len(body) != size:
        raise ValueError("the decoded size at 0x%08X is not its header's" % start)
    table = huffman_codes(rom, start)
    bits = []
    for symbol in huffman_unpack(kind, body):
        code, length = table[symbol]
        bits.extend((code >> shift) & 1 for shift in range(length - 1, -1, -1))
    head = rom[start - ROM_BASE:start - ROM_BASE + 5 + 2 * b4 + 1]
    out = bytearray(head)
    word, used = 0, 0
    for bit in bits:
        word = (word << 1) | bit
        used += 1
        if used == 32:
            out += word.to_bytes(4, "little")
            word, used = 0, 0
    if used:
        out += (word << (32 - used)).to_bytes(4, "little")
    return bytes(out)


def decode(rom, start):
    if rom[start - ROM_BASE] == 0x10:
        return lz77_decode(rom, start)
    kind, _size, _per = huffman_counts(rom, start)
    symbols, stored = huffman_symbols(rom, start)
    return huffman_pack(kind, symbols), stored


def encode(rom, start, body):
    if rom[start - ROM_BASE] == 0x10:
        return lz77_encode(body)
    return huffman_encode(rom, start, body)


def population():
    return STREAMS + HUFFMAN


def gap_name(start, stop):
    return "baserom.gba_0x%x_0x%x.extracted" % (start, stop)


def run_name(start, stop):
    return "..\\build\\bios\\stream_0x%x_0x%x.bin" % (start, stop)


def run_file(start, stop):
    return os.path.join(OUT, "stream_0x%x_0x%x.bin" % (start, stop))


def measured(image):
    rows = []
    for start in population():
        body, stored = decode(image, start)
        again = encode(image, start, body)
        if again != image[start - ROM_BASE:start - ROM_BASE + stored]:
            raise ValueError("the stream at 0x%08X is not re-encoded byte for byte" % start)
        rows.append({"start": start, "stop": start + stored, "body": again,
                     "decoded": len(body)})
    return rows


def refused(image):
    rows = []
    for start in REFUSED:
        body, stored = decode(image, start)
        rows.append({"start": start, "decoded": len(body), "consumed": stored,
                     "extent": extent(image, start)})
    return rows


def extent(image, start):
    word = struct.pack("<I", start)
    at = image.find(word)
    while at >= 0:
        if at % DESCRIPTOR_STRIDE == 0x0800FE4C - ROM_BASE:
            chain = int.from_bytes(image[at - 4:at], "little")
            return chain - start
        at = image.find(word, at + 1)
    return None


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
        for begin, end in runs:
            if begin < last and first < end and (begin < first or end > last):
                raise ValueError("the run at 0x%x straddles a slice edge" % (begin + ROM_BASE))
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
