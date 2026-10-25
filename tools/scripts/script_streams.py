from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ROM = os.path.join(ROOT, "baserom.gba")
ASM = os.path.join(ROOT, "asm", "remainder.s")
OUT = os.path.join(ROOT, "build", "script")
TABLE = os.path.join(ROOT, "tools", "scripts", "SCRIPT_RECORDS.csv")
OPS = os.path.join(ROOT, "tools", "scripts", "SCRIPT_OPS.csv")
ROM_BASE = 0x08000000
ROM_SIZE = 8388608
DESCRIPTORS = 0x08591F3C
STRIDE = 12
FLAGS = 0x08142386
SLOTS = 15
RECORD_FIELDS = "address,frames,bytes"
OPS_FIELDS = "segment,slot,mode,flags,f1a,f1b,f1c,f1d,f1e"
SLICE = re.compile(r"baserom\.gba_0x([0-9a-f]+)_0x([0-9a-f]+)\.extracted")


def inside(address, length=1):
    return ROM_BASE <= address and address + length <= ROM_BASE + ROM_SIZE


def byte_at(image, address):
    return image[address - ROM_BASE]


def word_at(image, address):
    at = address - ROM_BASE
    return image[at] | image[at + 1] << 8 | image[at + 2] << 16 | image[at + 3] << 24


def byte_table(image, address):
    out = []
    while inside(address) and len(out) <= 256:
        value = byte_at(image, address)
        address += 1
        if value == 0xFF:
            return out
        out.append(value)
    return None


def descriptor_rows(image):
    out = []
    index = 0
    while True:
        at = DESCRIPTORS + STRIDE * index
        if not inside(at, STRIDE):
            break
        table, selectors = word_at(image, at), word_at(image, at + 4)
        if not (inside(table, 4) and inside(selectors)):
            break
        chosen = byte_table(image, selectors)
        if not chosen:
            break
        width = max(chosen) + 1
        starts = [word_at(image, table + 4 * i) for i in range(width)]
        if not all(inside(start, 2) for start in starts):
            break
        out.append({"index": index, "address": at, "table": table, "selectors": selectors,
                    "width": width, "starts": starts})
        index += 1
    return out


def decode(image, start):
    frames = byte_at(image, start)
    if frames == 0:
        raise ValueError("the record at 0x%08X has no frame count" % start)
    at = start + 1
    stored = [None] * SLOTS
    segments = []
    for segment in range(frames):
        rows = []
        while True:
            if not inside(at):
                raise ValueError("the record at 0x%08X leaves the image at 0x%08X" % (start, at))
            opcode = byte_at(image, at)
            at += 1
            if opcode == 0:
                break
            slot, mode = (opcode & 0xF) - 1, opcode >> 4
            if slot < 0:
                raise ValueError("the opcode at 0x%08X names no slot" % (at - 1))
            flags = None
            if mode == 0:
                flags = byte_at(image, at)
                at += 1
                stored[slot] = flags
            elif mode == 1:
                flags = stored[slot]
                if flags is None:
                    raise ValueError("the opcode at 0x%08X inherits from no slot" % (at - 1))
            else:
                flags = byte_at(image, FLAGS + mode)
            fields = [None] * 5
            for bit in range(4):
                if not flags & (1 << bit):
                    continue
                if bit < 3:
                    fields[bit] = byte_at(image, at)
                    at += 1
                else:
                    fields[3] = byte_at(image, at)
                    fields[4] = byte_at(image, at + 1)
                    at += 2
            rows.append((segment, slot, mode, flags, tuple(fields)))
        segments.append(rows)
    return {"address": start, "frames": frames, "stop": at, "segments": segments}


def encode(record):
    out = bytearray([record["frames"]])
    for rows in record["segments"]:
        for segment, slot, mode, flags, fields in rows:
            if not 0 <= slot < SLOTS or not 0 <= mode <= 0xF or not 0 <= flags <= 0xFF:
                raise ValueError("the row at 0x%08X names no opcode" % record["address"])
            out.append(mode << 4 | slot + 1)
            if mode == 0:
                out.append(flags)
            for bit in range(4):
                wanted = bool(flags & (1 << bit))
                filled = fields[bit] is not None if bit < 3 else fields[3] is not None
                if filled != wanted:
                    raise ValueError("the row %r carries %d fields for flags %d"
                                     % (rows, sum(1 for field in fields if field is not None),
                                        flags))
                if not wanted:
                    continue
                if bit < 3:
                    out.append(fields[bit])
                else:
                    out += bytes(fields[3:5])
        out.append(0)
    return bytes(out)


def population(image):
    records = []
    for row in descriptor_rows(image):
        for start in sorted(row["starts"]):
            record = decode(image, start)
            blob = encode(record)
            record["blob"] = blob
            record["row"] = row["index"]
            record["span"] = record["stop"] - start
            if len(blob) != record["span"]:
                raise ValueError("the record at 0x%08X encodes %d of %d B"
                                 % (start, len(blob), record["span"]))
            if blob != image[start - ROM_BASE:record["stop"] - ROM_BASE]:
                raise ValueError("the record at 0x%08X is not re-encoded byte for byte" % start)
            records.append(record)
    return records


def order(records):
    return sorted(records, key=lambda record: record["address"])


def text(records):
    lines = [RECORD_FIELDS]
    for record in order(records):
        lines.append("%08x,%x,%x" % (record["address"], record["frames"], record["span"]))
    return "\n".join(lines) + "\n"


def ops_text(records):
    lines = [OPS_FIELDS]
    for record in order(records):
        for rows in record["segments"]:
            for segment, slot, mode, flags, fields in rows:
                lines.append(",".join(["%x" % segment, "%x" % slot, "%x" % mode, "%x" % flags]
                                      + ["" if field is None else "%02x" % field
                                         for field in fields]))
    return "\n".join(lines) + "\n"


def load_records(records_text, ops_text_in):
    records = []
    for line in records_text.splitlines()[1:]:
        if not line:
            continue
        address, frames, span = line.split(",")
        records.append({"address": int(address, 16), "frames": int(frames, 16),
                        "span": int(span, 16), "segments": []})
    flat = []
    for line in ops_text_in.splitlines()[1:]:
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 9:
            parts += [""] * (9 - len(parts))
        flat.append((int(parts[0], 16), int(parts[1], 16), int(parts[2], 16),
                     int(parts[3], 16),
                     tuple(int(part, 16) if part else None for part in parts[4:9])))
    at = 0
    for record in records:
        groups = [[] for _ in range(record["frames"])]
        size = 1 + record["frames"]
        while at < len(flat):
            segment, slot, mode, flags, fields = flat[at]
            if segment >= record["frames"]:
                raise ValueError("the record 0x%08X names segment %d"
                                 % (record["address"], segment))
            cost = 1 + (1 if mode == 0 else 0)
            for bit in range(4):
                if not flags & (1 << bit):
                    continue
                cost += 1 if bit < 3 else 2
            if size + cost > record["span"]:
                break
            groups[segment].append(flat[at])
            size += cost
            at += 1
        if size != record["span"]:
            raise ValueError("the record 0x%08X holds %d of %d B"
                             % (record["address"], size, record["span"]))
        record["segments"] = groups
        record["blob"] = encode(record)
        if len(record["blob"]) != record["span"]:
            raise ValueError("the record 0x%08X encodes %d of %d B"
                             % (record["address"], len(record["blob"]), record["span"]))
    if at != len(flat):
        raise ValueError("%d row(s) have no record" % (len(flat) - at))
    return records


def runs(records):
    out = []
    for record in order(records):
        if out and out[-1][1] == record["address"]:
            out[-1][1] = record["address"] + record["span"]
        else:
            out.append([record["address"], record["address"] + record["span"]])
    return [tuple(run) for run in out]


def gap_name(start, stop):
    return "baserom.gba_0x%x_0x%x.extracted" % (start, stop)


def run_name(start, stop):
    return "..\\build\\script\\stream_0x%x_0x%x.bin" % (start, stop)


def run_file(start, stop):
    return os.path.join(OUT, "stream_0x%x_0x%x.bin" % (start, stop))


def pieces(start, stop, spans):
    marks = {start, stop}
    for first, last in spans:
        for edge in (first, last):
            if start < edge < stop:
                marks.add(edge)
    ordered = sorted(marks)
    out = []
    for first, last in zip(ordered, ordered[1:]):
        covered = any(begin <= first and last <= end for begin, end in spans)
        out.append((first, last, "run" if covered else "gap"))
    return out


def rewrite(text_in, spans):
    lines, slices = [], []
    for line in text_in.splitlines():
        found = SLICE.search(line)
        if not found or "INCBIN" not in line:
            lines.append(line)
            continue
        first, last = int(found.group(1), 16), int(found.group(2), 16)
        if not any(begin < last and first < end for begin, end in spans):
            lines.append(line)
            continue
        for begin, end in spans:
            if begin < last and first < end and (begin < first or end > last):
                raise ValueError("the run at 0x%x straddles a slice edge" % (begin + ROM_BASE))
        for begin, stop, kind in pieces(first, last, spans):
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


def blob_of(records):
    return b"".join(record["blob"] for record in order(records))


def spans_of(records):
    return [(first - ROM_BASE, last - ROM_BASE) for first, last in runs(records)]


def build(image):
    records = population(image)
    spans = spans_of(records)
    text_out, slices = rewrite(open(ASM, encoding="utf-8", newline="").read(), spans)
    os.makedirs(OUT, exist_ok=True)
    for first, last in slices:
        path = os.path.join(ROOT, gap_name(first, last))
        with open(path, "wb") as handle:
            handle.write(image[first:last])
        held(path, image[first:last])
    for first, last in spans:
        blob = blob_of([record for record in order(records)
                        if first <= record["address"] - ROM_BASE < last])
        if blob != image[first:last]:
            raise ValueError("the rebuilt run 0x%X..0x%X is not the image's bytes" % (first, last))
        path = run_file(first, last)
        with open(path, "wb") as handle:
            handle.write(blob)
        held(path, blob)
    with open(ASM, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text_out)
    with open(TABLE, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text(records))
    with open(OPS, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(ops_text(records))
    return records, spans


def summary(records, spans):
    return ("records=%d segments=%d ops=%d bytes=%d rows=%d runs=%d"
            % (len(records), sum(record["frames"] for record in records),
               sum(len(rows) for record in records for rows in record["segments"]),
               sum(record["span"] for record in records),
               len(set(record["row"] for record in records)), len(spans)))


def check(image):
    records = population(image)
    spans = spans_of(records)
    text_out, slices = rewrite(open(ASM, encoding="utf-8", newline="").read(), spans)
    if open(ASM, encoding="utf-8", newline="").read() != text_out:
        print("SCRIPT FAIL: asm\\remainder.s is not the token list this image derives")
        return 1
    if open(TABLE, encoding="utf-8", newline="").read() != text(records):
        print("SCRIPT FAIL: %s is not the population this image derives" % TABLE)
        return 1
    if open(OPS, encoding="utf-8", newline="").read() != ops_text(records):
        print("SCRIPT FAIL: %s is not the rows this image derives" % OPS)
        return 1
    tracked = load_records(open(TABLE, encoding="utf-8", newline="").read(),
                           open(OPS, encoding="utf-8", newline="").read())
    if blob_of(tracked) != blob_of(records):
        print("SCRIPT FAIL: the tracked tables do not encode the image's records")
        return 1
    if [(record["address"], record["frames"], record["segments"]) for record in order(tracked)] \
            != [(record["address"], record["frames"], record["segments"])
                for record in order(records)]:
        print("SCRIPT FAIL: the tracked rows are not the rows the decoder reads")
        return 1
    for first, last in slices:
        held(os.path.join(ROOT, gap_name(first, last)), image[first:last])
    for first, last in spans:
        held(run_file(first, last), image[first:last])
    print(summary(records, spans))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["--write"], ["--check"]):
        print("usage: python tools\\scripts\\script_streams.py [--write|--check]")
        return 2
    if not os.path.exists(ROM):
        print("the script stream generator needs the retail image at %s" % ROM)
        return 1
    image = open(ROM, "rb").read()
    if argv == ["--check"]:
        return check(image)
    records, spans = build(image)
    print(summary(records, spans))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
