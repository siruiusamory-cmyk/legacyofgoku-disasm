from __future__ import annotations

import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ROM = os.path.join(ROOT, "baserom.gba")
CENSUS = os.path.join(ROOT, "tools", "code", "CENSUS_EVIDENCE.csv")
OUT = os.path.join(ROOT, "build", "code")
REMAINDER = os.path.join(ROOT, "asm", "remainder.s")
ROM_BASE = 0x08000000
ROM_SIZE = 8388608
ROM_END = ROM_BASE + ROM_SIZE
IMAGE_START = 0x08000138
MODES = ("thumb", "arm")
SLICE = re.compile(r"^baserom\.gba_0x([0-9a-fA-F]+)_0x([0-9a-fA-F]+)\.extracted$")
REGISTERS = ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7",
             "r8", "r9", "r10", "r11", "r12", "sp", "lr", "pc")
CONDITIONS = ("eq", "ne", "cs", "cc", "mi", "pl", "vs", "vc", "hi", "ls", "ge", "lt", "gt", "le")
THUMB_ALU = ("AND", "EOR", "LSL", "LSR", "ASR", "ADC", "SBC", "ROR",
             "TST", "NEG", "CMP", "CMN", "ORR", "MUL", "BIC", "MVN")
THUMB_HI = ("ADD", "CMP", "MOV")
THUMB_MEMORY = ("STR", "STRH", "STRB", "LDRSB", "LDR", "LDRH", "LDRB", "LDRSH")
DATA_PROCESSING = ("AND", "EOR", "SUB", "RSB", "ADD", "ADC", "SBC", "RSC",
                   "TST", "TEQ", "CMP", "CMN", "ORR", "MOV", "BIC", "MVN")
NO_DESTINATION = (8, 9, 10, 11)
NO_SOURCE = (13, 15)


def register(number):
    return REGISTERS[number]


def label(address):
    return "|loc_%08X|" % address


def halfwords(rom, address):
    return int.from_bytes(rom[address - ROM_BASE:address - ROM_BASE + 2], "little")


def word(rom, address):
    return int.from_bytes(rom[address - ROM_BASE:address - ROM_BASE + 4], "little")


def rotate_right(value, amount):
    amount %= 32
    return ((value >> amount) | (value << (32 - amount))) & 0xFFFFFFFF if amount else value


def thumb_branch(address, half):
    offset = half & 0x7FF
    if offset & 0x400:
        offset -= 0x800
    return (address + 4 + (offset << 1)) & 0xFFFFFFFF


def thumb_conditional(address, half):
    offset = half & 0xFF
    if offset & 0x80:
        offset -= 0x100
    return (address + 4 + (offset << 1)) & 0xFFFFFFFF


def thumb_call(high, low):
    offset = ((high & 0x7FF) << 11) | (low & 0x7FF)
    if high & 0x400:
        offset -= 1 << 22
    return offset << 1


def arm_branch(address, instruction):
    offset = instruction & 0xFFFFFF
    if offset & 0x800000:
        offset -= 0x1000000
    return (address + 8 + (offset << 2)) & 0xFFFFFFFF


def arm_operand2(instruction):
    if instruction & (1 << 25):
        imm8 = instruction & 0xFF
        rotate = ((instruction >> 8) & 0xF) * 2
        return "#0x%X" % rotate_right(imm8, rotate)
    register_number = instruction & 0xF
    if instruction & 0x10:
        return "%s, %s %s" % (register(register_number),
                              ("LSL", "LSR", "ASR", "ROR")[(instruction >> 5) & 3],
                              register((instruction >> 8) & 0xF))
    kind = (instruction >> 5) & 3
    amount = (instruction >> 7) & 0x1F
    if kind == 0 and amount == 0:
        return register(register_number)
    if kind == 3 and amount == 0:
        return register(register_number) + ", RRX"
    return "%s, %s #0x%X" % (register(register_number), ("LSL", "LSR", "ASR", "ROR")[kind],
                             amount or 32)


def thumb_text(rom, address):
    half = halfwords(rom, address)
    if half >= 0xF000:
        low = halfwords(rom, address + 2)
        if half >= 0xF800 or low < 0xF800:
            return None
        target = (address + 4 + thumb_call(half, low)) & 0xFFFFFFFF
        return "BL", label(target), 4
    if (half & 0xF800) == 0xE000:
        return "B", label(thumb_branch(address, half)), 2
    if (half & 0xF000) == 0xD000:
        condition = (half >> 8) & 0xF
        if condition == 0xE:
            return None
        if condition == 0xF:
            return "SWI", "0x%X" % (half & 0xFF), 2
        return "B" + CONDITIONS[condition].upper(), label(thumb_conditional(address, half)), 2
    if (half & 0xF800) == 0x0000:
        return "LSL", "%s, %s, #0x%X" % (register(half & 7), register((half >> 3) & 7),
                                         (half >> 6) & 0x1F), 2
    if (half & 0xF800) == 0x0800:
        amount = (half >> 6) & 0x1F
        return "LSR", "%s, %s, #0x%X" % (register(half & 7), register((half >> 3) & 7),
                                         amount or 32), 2
    if (half & 0xF800) == 0x1000:
        amount = (half >> 6) & 0x1F
        return "ASR", "%s, %s, #0x%X" % (register(half & 7), register((half >> 3) & 7),
                                         amount or 32), 2
    if (half & 0xF800) == 0x1800:
        operation = "SUB" if half & 0x0200 else "ADD"
        if half & 0x0400:
            return operation, "%s, %s, #0x%X" % (register(half & 7),
                                                 register((half >> 3) & 7),
                                                 (half >> 6) & 7), 2
        return operation, "%s, %s, %s" % (register(half & 7), register((half >> 3) & 7),
                                          register((half >> 6) & 7)), 2
    if (half & 0xE000) == 0x2000:
        operation = ("MOV", "CMP", "ADD", "SUB")[(half >> 11) & 3]
        return operation, "%s, #0x%X" % (register((half >> 8) & 7), half & 0xFF), 2
    if (half & 0xFC00) == 0x4000:
        operation = THUMB_ALU[(half >> 6) & 0xF]
        return operation, "%s, %s" % (register(half & 7), register((half >> 3) & 7)), 2
    if (half & 0xFC00) == 0x4400:
        kind = (half >> 8) & 3
        if kind == 3:
            return "BX", register((half >> 3) & 0xF), 2
        if (half & 0xC0) == 0:
            return None
        destination = (half & 7) | ((half >> 4) & 8)
        source = (half >> 3) & 0xF
        return THUMB_HI[kind], "%s, %s" % (register(destination), register(source)), 2
    if (half & 0xF800) == 0x4800:
        return "LDR", "%s, [pc, #0x%X]" % (register((half >> 8) & 7), (half & 0xFF) * 4), 2
    if (half & 0xF000) == 0x5000:
        operation = THUMB_MEMORY[(half >> 9) & 7]
        return operation, "%s, [%s, %s]" % (register(half & 7), register((half >> 3) & 7),
                                            register((half >> 6) & 7)), 2
    if (half & 0xF000) in (0x6000, 0x7000, 0x8000):
        top = half & 0xF000
        if top == 0x6000:
            operation, step = ("LDR", 4) if half & 0x0800 else ("STR", 4)
        elif top == 0x7000:
            operation, step = ("LDRB", 1) if half & 0x0800 else ("STRB", 1)
        else:
            operation, step = ("LDRH", 2) if half & 0x0800 else ("STRH", 2)
        return operation, "%s, [%s, #0x%X]" % (register(half & 7), register((half >> 3) & 7),
                                               ((half >> 6) & 0x1F) * step), 2
    if (half & 0xF000) == 0x9000:
        operation = "LDR" if half & 0x0800 else "STR"
        return operation, "%s, [sp, #0x%X]" % (register((half >> 8) & 7), (half & 0xFF) * 4), 2
    if (half & 0xF000) == 0xA000:
        base = "sp" if half & 0x0800 else "pc"
        return "ADD", "%s, %s, #0x%X" % (register((half >> 8) & 7), base, (half & 0xFF) * 4), 2
    if (half & 0xFF00) in (0xB000, 0xB080):
        operation = "SUB" if half & 0x80 else "ADD"
        return operation, "sp, #0x%X" % ((half & 0x7F) * 4), 2
    if (half & 0xFE00) == 0xB400:
        names = thumb_list(half, "lr")
        return None if names is None else ("PUSH", names, 2)
    if (half & 0xFE00) == 0xBC00:
        names = thumb_list(half, "pc")
        return None if names is None else ("POP", names, 2)
    if (half & 0xF000) == 0xC000:
        operation = "LDMIA" if half & 0x0800 else "STMIA"
        names = thumb_list(half, None)
        if names is None:
            return None
        return operation, "%s!, %s" % (register((half >> 8) & 7), names), 2
    return None


def thumb_list(half, ninth):
    names = [register(number) for number in range(8) if half & (1 << number)]
    if ninth and half & 0x100:
        names.append(ninth)
    if not names:
        return None
    return "{" + ", ".join(names) + "}"


def arm_text(rom, address):
    instruction = word(rom, address)
    if instruction >> 28 == 0xF:
        return None
    suffix = "" if instruction >> 28 == 0xE else CONDITIONS[instruction >> 28].upper()
    if (instruction & 0x0FBF0FFF) == 0x010F0000:
        special = "SPSR" if instruction & 0x00400000 else "CPSR"
        return "MRS" + suffix, "%s, %s" % (register((instruction >> 12) & 0xF), special), 4
    if (instruction & 0x0FB0FFF0) == 0x0120F000:
        fields = arm_fields(instruction)
        if fields is None:
            return None
        return "MSR" + suffix, "%s, %s" % (fields, register(instruction & 0xF)), 4
    if (instruction & 0x0FB0F000) == 0x0320F000:
        fields = arm_fields(instruction)
        if fields is None:
            return None
        return "MSR" + suffix, "%s, %s" % (fields, arm_operand2(instruction)), 4
    if (instruction & 0x0FFFFFF0) == 0x012FFF10:
        return "BX" + suffix, register(instruction & 0xF), 4
    if (instruction & 0x0E000090) == 0x00000090:
        if instruction & 0x60:
            return arm_halfword(instruction, suffix)
        if instruction & 0x00800000:
            return None
        return arm_multiply(instruction, suffix)
    operation = (instruction >> 25) & 7
    if operation in (0, 1):
        return arm_data_processing(instruction, suffix)
    if operation in (2, 3):
        return arm_transfer(instruction, suffix)
    if operation == 4:
        return arm_block(instruction, suffix)
    if operation == 5:
        return ("BL" if instruction & (1 << 24) else "B") + suffix, label(
            arm_branch(address, instruction)), 4
    if operation == 15:
        return "SWI" + suffix, "0x%X" % (instruction & 0xFFFFFF), 4
    return None


def arm_fields(instruction):
    names = []
    if instruction & 0x00010000:
        names.append("c")
    if instruction & 0x00020000:
        names.append("x")
    if instruction & 0x00040000:
        names.append("s")
    if instruction & 0x00080000:
        names.append("f")
    if not names:
        return None
    return ("SPSR_" if instruction & 0x00400000 else "CPSR_") + "".join(names)


def arm_data_processing(instruction, suffix):
    opcode = (instruction >> 21) & 0xF
    storing = instruction & (1 << 20)
    source = (instruction >> 16) & 0xF
    destination = (instruction >> 12) & 0xF
    operand = arm_operand2(instruction)
    name = DATA_PROCESSING[opcode]
    if opcode in NO_DESTINATION:
        if not storing:
            return None
        return name + suffix, "%s, %s" % (register(source), operand), 4
    if opcode in NO_SOURCE:
        return name + suffix + ("S" if storing else ""), "%s, %s" % (register(destination),
                                                                    operand), 4
    return (name + suffix + ("S" if storing else ""),
            "%s, %s, %s" % (register(destination), register(source), operand), 4)


def arm_shift(instruction):
    kind = (instruction >> 5) & 3
    if instruction & 0x10:
        return "%s %s" % (("LSL", "LSR", "ASR", "ROR")[kind], register((instruction >> 8) & 0xF))
    amount = (instruction >> 7) & 0x1F
    if kind == 0 and amount == 0:
        return None
    if kind == 3 and amount == 0:
        return "RRX"
    return "%s #0x%X" % (("LSL", "LSR", "ASR", "ROR")[kind], amount or 32)


def arm_transfer(instruction, suffix):
    register_offset = instruction & (1 << 25)
    pre = instruction & (1 << 24)
    up = "U" if instruction & (1 << 23) else ""
    byte = "B" if instruction & (1 << 22) else ""
    write = instruction & (1 << 21)
    load = instruction & (1 << 20)
    source = (instruction >> 16) & 0xF
    destination = (instruction >> 12) & 0xF
    if register_offset:
        if not up:
            return None
        shift = arm_shift(instruction)
        offset = register(instruction & 0xF) + (", " + shift if shift else "")
    else:
        value = instruction & 0xFFF
        offset = ("#0x%X" % value) if up else ("#-0x%X" % value if value else "#0")
    name = ("LDR" if load else "STR") + suffix + byte
    if pre and write:
        return name, "%s, [%s, %s]!" % (register(destination), register(source), offset), 4
    if pre:
        return name, "%s, [%s, %s]" % (register(destination), register(source), offset), 4
    if write:
        return name, "%s, [%s], %s" % (register(destination), register(source), offset), 4
    return None


def arm_halfword(instruction, suffix):
    pre = instruction & (1 << 24)
    up = instruction & (1 << 23)
    immediate = instruction & (1 << 22)
    write = instruction & (1 << 21)
    load = instruction & (1 << 20)
    source = (instruction >> 16) & 0xF
    destination = (instruction >> 12) & 0xF
    kind = (instruction >> 5) & 3
    if not kind:
        return None
    name = ("LDR" if load else "STR") + ("H", "SB", "SH")[kind - 1]
    if immediate:
        value = ((instruction >> 4) & 0xF0) | (instruction & 0xF)
        offset = ("#0x%X" % value) if up else "#-0x%X" % value
        offset = offset if value else "#0"
    else:
        if not up:
            return None
        offset = register(instruction & 0xF)
    if not pre:
        return None
    return name + suffix, "%s, [%s, %s]%s" % (register(destination), register(source),
                                              offset, "!" if write else ""), 4


def arm_multiply(instruction, suffix):
    accumulate = instruction & (1 << 21)
    storing = instruction & (1 << 20)
    destination = (instruction >> 16) & 0xF
    accumulator = (instruction >> 12) & 0xF
    source = instruction & 0xF
    second = (instruction >> 8) & 0xF
    if accumulate:
        return "MLA" + suffix + ("S" if storing else ""), "%s, %s, %s, %s" % (
            register(destination), register(source), register(second), register(accumulator)), 4
    return "MUL" + suffix + ("S" if storing else ""), "%s, %s, %s" % (
        register(destination), register(source), register(second)), 4


def arm_block(instruction, suffix):
    pre = instruction & (1 << 24)
    up = instruction & (1 << 23)
    write = instruction & (1 << 21)
    load = instruction & (1 << 20)
    source = (instruction >> 16) & 0xF
    names = [register(number) for number in range(16) if instruction & (1 << number)]
    if not names:
        return None
    if pre and up:
        mode = "IB"
    elif pre:
        mode = "DB"
    elif up:
        mode = "IA"
    else:
        mode = "DA"
    return ("LDM" if load else "STM") + suffix + mode, "%s%s, {%s}" % (
        register(source), "!" if write else "", ", ".join(names)), 4


def decode(rom, address, mode):
    if mode == "thumb":
        half = halfwords(rom, address)
        size = 4 if half >= 0xF000 else 2
        text = thumb_text(rom, address)
        if text is None or text[0] is None or text[1] is None:
            return None
        return text[0], text[1], size
    text = arm_text(rom, address)
    if text is None or text[0] is None or text[1] is None:
        return None
    return text[0], text[1], text[2]


def census_rows(path=CENSUS):
    rows = []
    for row in csv.DictReader(open(path, encoding="utf-8")):
        rows.append({"address": int(row["address"], 16),
                     "kind": row["kind"],
                     "channel": row["channel"],
                     "mode": row["mode"],
                     "end": None if row["end"] == "-" else int(row["end"], 16),
                     "reason": row["reason"],
                     "flags": [flag for flag in row["flags"].split("+") if flag != "-"]})
    return rows


def code_rows(rows):
    return [row for row in rows
            if row["kind"] == "start" and row["channel"] != "pool"
            and "data" not in row["flags"] and row["end"] is not None
            and row["address"] >= IMAGE_START and row["end"] <= ROM_END]


def raw_bytes(rows, ranges):
    found = []
    for row in code_rows(rows):
        hit = 0
        for start, length in ranges:
            low, high = max(row["address"], start), min(row["end"], start + length)
            if low < high:
                hit += high - low
        if hit:
            found.append((row["address"], hit))
    return found


def modeless(rows):
    return [row["address"] for row in code_rows(rows) if row["mode"] not in MODES]


def slices(first, last, taken):
    out = []
    position = first
    for start, length in sorted(taken):
        stop = start + length
        if stop <= position or start >= last:
            continue
        if start > position:
            out.append((position, start))
        position = max(position, stop)
    if position < last:
        out.append((position, last))
    return out


def emitted(rom, rows):
    texts, targets, unreadable = {}, set(), []
    for row in sorted(code_rows(rows), key=lambda item: item["address"]):
        lines, position = [], row["address"]
        while position < row["end"]:
            step = decode(rom, position, row["mode"])
            if step is None:
                size = 4 if row["mode"] == "arm" or halfwords(rom, position) >= 0xF000 else 2
                unreadable.append((position, size, row["mode"]))
                words = "\tDCD\t0x%08X" % word(rom, position) if size == 4 else (
                    "\tDCW\t0x%04X" % halfwords(rom, position))
                lines.append((position, words, size))
                position += size
                continue
            operation, operands, size = step
            if operands.startswith("|loc_"):
                targets.add(int(operands[5:13], 16))
            lines.append((position, "\t%s\t%s" % (operation, operands), size))
            position += size
        texts[row["address"]] = (row["mode"], lines)
    return texts, targets, unreadable


def render(texts, targets):
    files, spans = {}, []
    for begin, (mode, lines) in sorted(texts.items()):
        text = ["\tCODE16" if mode == "thumb" else "\tCODE32"]
        for position, line, _size in lines:
            if position == begin or position in targets:
                text.append(label(position))
            text.append(line)
        name = "code_%08x.s" % begin
        files[name] = "\n".join(text) + "\n"
        spans.append((begin, sum(line[2] for line in lines), name))
    return files, spans


def split_labels(texts, targets):
    found = []
    for begin, (_mode, lines) in texts.items():
        positions = set(line[0] for line in lines)
        stop = begin + sum(line[2] for line in lines)
        found += [address for address in sorted(targets)
                  if begin <= address < stop and address not in positions]
    return found


def remainder_text(items, targets):
    lines = ["\tAREA\tRemainder, CODE, READONLY", ""]
    for begin, kind, payload in sorted(items):
        if kind == "code":
            lines.append("\tINCLUDE\t..\\build\\code\\%s" % payload)
        else:
            if begin in targets:
                lines.append(label(begin))
            lines.append("\tINCBIN\tbaserom.gba_0x%x_0x%x.extracted"
                         % (begin - ROM_BASE, payload - ROM_BASE))
    return "\n".join(lines) + "\n"


def slice_name(first, last):
    return "baserom.gba_0x%x_0x%x.extracted" % (first - ROM_BASE, last - ROM_BASE)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--out", default=OUT)
    parser.add_argument("--rom", default=ROM)
    arguments = parser.parse_args(argv)
    if not os.path.exists(arguments.rom):
        print("the code generator needs the retail image at %s" % arguments.rom)
        return 1
    rom = open(arguments.rom, "rb").read()
    rows = census_rows()
    missing = modeless(rows)
    if missing:
        print("the census has no mode for the start at 0x%08x" % missing[0])
        return 1
    texts, targets, unreadable = emitted(rom, rows)
    files, spans = render(texts, targets)
    late = split_labels(texts, targets)
    if late:
        print("the branch target at 0x%08x falls inside an instruction" % late[0])
        return 1
    gaps = slices(IMAGE_START, ROM_END,
                  [(start, length) for start, length, _name in spans]
                  + [(address, 0) for address in targets])
    items = [(start, "code", name) for start, _length, name in spans]
    items += [(start, "raw", stop) for start, stop in gaps]
    text = remainder_text(items, set(targets))
    written = sum(length for _start, length, _name in spans)
    print("emitted starts=%d files=%d bytes=%d" % (len(texts), len(files), written))
    print("raw slices=%d bytes=%d"
          % (len(gaps), sum(stop - start for start, stop in gaps)))
    print("branch labels=%d" % len(targets))
    for position, size, mode in unreadable:
        print("no %s source form at 0x%08x, %d B kept exact" % (mode, position, size))
    if arguments.write:
        os.makedirs(arguments.out, exist_ok=True)
        for name in os.listdir(arguments.out):
            if name.endswith(".s"):
                os.remove(os.path.join(arguments.out, name))
        for name in sorted(files):
            with open(os.path.join(arguments.out, name), "w", encoding="utf-8",
                      newline="\n") as handle:
                handle.write(files[name])
        for start, stop in gaps:
            with open(os.path.join(ROOT, slice_name(start, stop)), "wb") as handle:
                handle.write(rom[start - ROM_BASE:stop - ROM_BASE])
        with open(REMAINDER, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print("wrote %d file(s) and %d slice(s)" % (len(files), len(gaps)))
        return 0
    if arguments.check:
        if not os.path.exists(REMAINDER) or open(REMAINDER, encoding="utf-8",
                                                 newline="").read() != text:
            print("EMIT FAIL: %s is not the token list this image produces" % REMAINDER)
            return 1
        absent = [name for name in (slice_name(start, stop) for start, stop in gaps)
                  if not os.path.exists(os.path.join(ROOT, name))]
        if absent:
            print("EMIT FAIL: %d slice(s) absent, first %s" % (len(absent), absent[0]))
            return 1
        print("EMIT PASS slices=%d bytes=%d" % (len(gaps), written))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
