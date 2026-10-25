from __future__ import annotations

import struct

ROM_BASE = 0x08000000
ROM_SIZE = 0x800000
HEADER = 0x08337248
LIST_TAG = 0xF1FA
SKIP_TAG = 0xF1F1
RECORD_HEADER = 0x10
ENTRY_HEADER = 6
ROW_BYTES = 120
BANK = 9600
ROW_STREAM = 12
LITERAL = 0x80
REPEAT_UNIT = 0x100
COUNT_FLOOR = 0


def word(rom, addr):
    return struct.unpack_from("<I", rom, addr - ROM_BASE)[0]


def half(rom, addr):
    return struct.unpack_from("<H", rom, addr - ROM_BASE)[0]


def byte(rom, addr):
    return rom[addr - ROM_BASE]


def walk(rom, header=HEADER):
    count = half(rom, header + 6)
    cursor = header + 0x80
    start = cursor
    records = []
    while len(records) < count:
        if half(rom, cursor + 4) != LIST_TAG:
            break
        size = word(rom, cursor)
        if size < RECORD_HEADER or cursor + size > ROM_BASE + ROM_SIZE:
            break
        records.append((cursor, size))
        cursor += size
    return {"header": header, "count": count, "start": start, "end": cursor,
            "bytes": cursor - start, "records": records}


def entries(rom, record, size):
    count = half(rom, record + 6)
    cursor = record + RECORD_HEADER
    out = []
    for _index in range(count):
        entry_size = word(rom, cursor)
        if entry_size < ENTRY_HEADER or cursor + entry_size > record + size:
            raise ValueError("entry at %08X of %d B leaves the record" % (cursor, entry_size))
        out.append((cursor, entry_size, half(rom, cursor + 4)))
        cursor += entry_size
    if cursor != record + size:
        raise ValueError("the entries of the record at %08X stop at %08X, not %08X"
                         % (record, cursor, record + size))
    return out


def decode(rom, body):
    first_row = half(rom, body)
    rows = half(rom, body + 2)
    if rows == 0 or first_row + rows > BANK // ROW_BYTES:
        raise ValueError("the stream at %08X names rows %d..%d of %d"
                         % (body, first_row, first_row + rows, BANK // ROW_BYTES))
    cursor = body + 4
    covered = {}
    written = 0
    for row in range(rows):
        base = (first_row + row) * ROW_BYTES
        spans = byte(rom, cursor)
        cursor += 1
        position = base
        for _span in range(spans):
            position += byte(rom, cursor)
            cursor += 1
            length = byte(rom, cursor)
            cursor += 1
            if length == COUNT_FLOOR:
                raise ValueError("the stream at %08X carries a zero length" % body)
            if length < LITERAL:
                count = length
                cursor += length
            else:
                count = REPEAT_UNIT - length
                cursor += 1
            if position < base or position + count > base + ROW_BYTES:
                raise ValueError("the stream at %08X writes outside row %d" % (body, first_row + row))
            for spot in range(count):
                if position + spot in covered:
                    raise ValueError("the stream at %08X writes %d twice" % (body, position + spot))
                covered[position + spot] = True
            position += count
            written += count
    return {"rows": rows, "written": written, "consumed": cursor - body, "covered": len(covered)}


def census(rom):
    found = walk(rom)
    kinds = {}
    rows = 0
    decoded = 0
    consumed = 0
    refused = []
    for record, size in found["records"]:
        for at, entry_size, kind in entries(rom, record, size):
            kinds.setdefault(kind, {"entries": 0, "bytes": 0})
            kinds[kind]["entries"] += 1
            kinds[kind]["bytes"] += entry_size
            if kind != ROW_STREAM:
                continue
            body = at + ENTRY_HEADER
            try:
                stream = decode(rom, body)
            except ValueError as problem:
                refused.append(str(problem))
                continue
            if stream["consumed"] != entry_size - ENTRY_HEADER:
                refused.append("the stream at %08X consumes %d of %d"
                               % (body, stream["consumed"], entry_size - ENTRY_HEADER))
                continue
            rows += stream["rows"]
            decoded += stream["written"]
            consumed += stream["consumed"]
    return {"walk": found, "kinds": kinds, "rows": rows, "decoded": decoded,
            "consumed": consumed, "refused": refused}


def token_rows(rom, body):
    rows = half(rom, body + 2)
    cursor = body + 4
    out = []
    for _row in range(rows):
        spans = byte(rom, cursor)
        cursor += 1
        tokens = []
        for _span in range(spans):
            skip = byte(rom, cursor)
            cursor += 1
            length = byte(rom, cursor)
            cursor += 1
            if length < LITERAL:
                tokens.append((skip, "lit", rom[cursor - ROM_BASE:cursor - ROM_BASE + length]))
                cursor += length
            else:
                tokens.append((skip, "rep",
                               bytes((byte(rom, cursor),)) * (REPEAT_UNIT - length)))
                cursor += 1
        out.append(tokens)
    return out


def ambiguity(rom):
    found = walk(rom)
    seen = {}
    regions = 0
    for record, size in found["records"]:
        for at, entry_size, kind in entries(rom, record, size):
            if kind != ROW_STREAM:
                continue
            for tokens in token_rows(rom, at + ENTRY_HEADER):
                current = []
                for token in tokens:
                    if token[0] or not current:
                        if current:
                            regions += 1
                            remember(seen, current)
                        current = [token]
                    else:
                        current.append(token)
                if current:
                    regions += 1
                    remember(seen, current)
    ambiguous = sum(1 for plans in seen.values() if len(plans) > 1)
    return {"regions": regions, "contents": len(seen), "ambiguous": ambiguous}


def remember(seen, region):
    content = b"".join(chunk for _skip, _name, chunk in region)
    plan = tuple((name, len(chunk)) for _skip, name, chunk in region)
    seen.setdefault(content, set()).add(plan)


def permute(rom, start, stop, how):
    image = bytearray(rom)
    chunk = rom[start - ROM_BASE:stop - ROM_BASE]
    if how == "reversed":
        image[start - ROM_BASE:stop - ROM_BASE] = chunk[::-1]
    elif how == "halfword":
        swapped = bytearray(chunk)
        even = 2 * (len(chunk) // 2)
        swapped[0:even:2] = chunk[1:even:2]
        swapped[1:even:2] = chunk[0:even:2]
        image[start - ROM_BASE:stop - ROM_BASE] = swapped
    elif how == "rotated":
        middle = len(chunk) // 2
        image[start - ROM_BASE:stop - ROM_BASE] = chunk[middle:] + chunk[:middle]
    else:
        raise ValueError(how)
    return bytes(image)


def null(rom, found):
    start, stop = found["start"], found["end"]
    out = {}
    for how in ("reversed", "halfword", "rotated"):
        out[how] = len(walk(permute(rom, start, stop, how), found["header"])["records"])
    return out


def main():
    rom = open("baserom.gba", "rb").read()
    found = census(rom)["walk"]
    print("header %08X  list %08X..%08X  %d records  %d B"
          % (found["header"], found["start"], found["end"], len(found["records"]),
             found["bytes"]))
    measured = census(rom)
    for kind in sorted(measured["kinds"]):
        row = measured["kinds"][kind]
        print("type %2d  entries %3d  bytes %7d" % (kind, row["entries"], row["bytes"]))
    print("row streams %d rows, %d written bytes, %d consumed, %d refused"
          % (measured["rows"], measured["decoded"], measured["consumed"],
             len(measured["refused"])))
    for how, count in sorted(null(rom, found).items()):
        print("null %-8s %d records" % (how, count))
    plans = ambiguity(rom)
    print("token plans: %d regions, %d distinct contents, %d with two or more plans"
          % (plans["regions"], plans["contents"], plans["ambiguous"]))


if __name__ == "__main__":
    main()
