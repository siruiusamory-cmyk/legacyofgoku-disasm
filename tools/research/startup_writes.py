from __future__ import annotations

import struct
import sys

ROM_BASE = 0x08000000
ROM_SIZE = 0x800000
DMA_BASE = 0x040000B0
DMA_STOP = 0x040000E0
DMA_FIELDS = {0: "sad", 4: "dad", 8: "cnt_l", 10: "cnt_h"}
IWRAM = (0x03000000, 0x03008000)
EWRAM = (0x02000000, 0x02040000)
THUMB = 1
ARM = 2
ROOTS = ((0x08000274, THUMB), (0x08000138, ARM))
WALK_CAP = 0x800
START_CAP = 0x1000
UNDEFINED = ((0x4780, 0x47FF), (0xB100, 0xB3FF), (0xB600, 0xBBFF), (0xBE00, 0xBFFF),
             (0xDE00, 0xDEFF), (0xE800, 0xEFFF))
SHIFT_OPS = ("lsl", "lsr", "asr", "ror")
ARM_OPS = {0: "and", 1: "eor", 2: "sub", 4: "add", 12: "orr", 14: "bic"}
THUMB_OPS = {0: "and", 1: "eor", 5: "add", 6: "sub", 12: "orr", 14: "bic"}


def word(rom, addr):
    return struct.unpack_from("<I", rom, addr - ROM_BASE)[0]


def half(rom, addr):
    return struct.unpack_from("<H", rom, addr - ROM_BASE)[0]


def in_image(rom, addr):
    return ROM_BASE <= addr < ROM_BASE + len(rom)


def signed(value, bits):
    top = 1 << (bits - 1)
    return (value & (top - 1)) - (value & top)


def rotate(value, bits):
    bits &= 31
    if bits == 0:
        return value & 0xFFFFFFFF
    value &= 0xFFFFFFFF
    return ((value >> bits) | (value << (32 - bits))) & 0xFFFFFFFF


def shifted(value, kind, amount):
    value &= 0xFFFFFFFF
    if kind == "lsr":
        return value >> amount
    if kind == "asr":
        return signed(value, 32) >> amount
    if kind == "ror":
        return rotate(value, amount)
    return (value << amount) & 0xFFFFFFFF


def computed(op, left, right):
    if op == "mov":
        return right & 0xFFFFFFFF
    if left is None or right is None:
        return None
    if op == "add":
        return (left + right) & 0xFFFFFFFF
    if op == "sub":
        return (left - right) & 0xFFFFFFFF
    if op == "orr":
        return left | right
    if op == "and":
        return left & right
    if op == "eor":
        return left ^ right
    if op == "bic":
        return left & ~right & 0xFFFFFFFF
    if op in SHIFT_OPS:
        return shifted(left, op, right & 0xFF)
    return None


def alu_value(alu, const):
    left = alu.get("left_imm")
    if left is None and alu.get("left") is not None:
        left = const.get(alu["left"])
    right = alu.get("right_imm")
    if right is None and alu.get("right") is not None:
        right = const.get(alu["right"])
        if right is not None and alu.get("shift"):
            right = shifted(right, alu["shift"][0], alu["shift"][1])
    if alu["op"] == "mov":
        return None if right is None else right & 0xFFFFFFFF
    return computed(alu["op"], left, right)


def alu(rd, op, left=None, right=None, left_imm=None, right_imm=None, shift=None):
    return {"rd": rd, "op": op, "left": left, "right": right, "left_imm": left_imm,
            "right_imm": right_imm, "shift": shift}


def resolved(kick):
    return sum(1 for field in ("sad", "dad", "cnt_l", "cnt_h") if kick.get(field))


def hold(kicks, entry):
    for index, kick in enumerate(kicks):
        if kick["site"] == entry["site"] and kick["channel"] == entry["channel"]:
            if resolved(entry) > resolved(kick):
                kicks[index] = entry
            return
    kicks.append(entry)


def ins_new(addr, size, mode):
    return {"addr": addr, "size": size, "mode": mode, "mn": "other", "target": None,
            "literal": None, "store": None, "swi": None, "block": None, "call": None,
            "alu": None, "return_": False}


def decode_thumb(rom, addr):
    value = half(rom, addr)
    if any(low <= value <= high for low, high in UNDEFINED):
        return None
    ins = ins_new(addr, 2, THUMB)
    if 0xF000 <= value < 0xF800:
        ins["size"] = 4
        ins["mn"] = "bl"
        second = half(rom, addr + 2)
        if 0xF800 <= second <= 0xFFFF:
            offset = signed(((value & 0x7FF) << 12) | ((second & 0x7FF) << 1), 23)
            ins["target"] = ins["call"] = addr + 4 + offset
        return ins
    if value < 0x0800:
        ins.update(mn="lsl", alu=alu(value & 7, "lsl", left=(value >> 3) & 7,
                                    right_imm=(value >> 6) & 0x1F))
        return ins
    if value < 0x1000:
        ins.update(mn="lsr", alu=alu(value & 7, "lsr", left=(value >> 3) & 7,
                                    right_imm=((value >> 6) & 0x1F) or 32))
        return ins
    if value < 0x1800:
        ins.update(mn="asr", alu=alu(value & 7, "asr", left=(value >> 3) & 7,
                                    right_imm=((value >> 6) & 0x1F) or 32))
        return ins
    if value < 0x1C00:
        op = "sub" if value & 0x0200 else "add"
        ins.update(mn="add-sub-reg", alu=alu(value & 7, op, left=(value >> 3) & 7,
                                            right=(value >> 6) & 7))
        return ins
    if value < 0x2000:
        op = "sub" if value & 0x0200 else "add"
        ins.update(mn="add-sub-imm", alu=alu(value & 7, op, left=(value >> 3) & 7,
                                            right_imm=(value >> 6) & 7))
        return ins
    if value < 0x2800:
        ins.update(mn="mov-imm", alu=alu((value >> 8) & 7, "mov", right_imm=value & 0xFF))
        return ins
    if value < 0x3000:
        ins.update(mn="cmp-imm")
        return ins
    if value < 0x3800:
        ins.update(mn="add-imm", alu=alu((value >> 8) & 7, "add", left=(value >> 8) & 7,
                                        right_imm=value & 0xFF))
        return ins
    if value < 0x4000:
        ins.update(mn="sub-imm", alu=alu((value >> 8) & 7, "sub", left=(value >> 8) & 7,
                                        right_imm=value & 0xFF))
        return ins
    if value < 0x4400:
        op, rd, rs = (value >> 6) & 0xF, value & 7, (value >> 3) & 7
        if op in (8, 10, 11):
            ins.update(mn="test")
        elif op in (2, 3, 4, 7):
            ins.update(mn="shift-reg", alu=alu(rd, {2: "lsl", 3: "lsr", 4: "asr",
                                                    7: "ror"}[op], left=rd, right=rs))
        elif op == 9:
            ins.update(mn="neg", alu=alu(rd, "sub", left_imm=0, right=rs))
        else:
            ins.update(mn="alu-reg", alu=alu(rd, THUMB_OPS.get(op, "?"), left=rd, right=rs))
        return ins
    if value < 0x4700:
        rd = (value & 7) | ((value >> 4) & 8)
        rs = (value >> 3) & 0xF
        if value & 0x0200:
            ins.update(mn="cmp-reg")
        else:
            ins.update(mn="hi-mov", alu=alu(rd, "mov", right=rs))
        return ins
    if value < 0x4780:
        ins.update(mn="bx", return_=(value >> 3) & 0xF in (0xE, 0xF))
        return ins
    if value < 0x4800:
        return None
    if value < 0x5000:
        reg, offset = (value >> 8) & 7, (value & 0xFF) * 4
        ins.update(mn="ldr-literal", literal=(reg, ((addr + 4) & ~3) + offset))
        return ins
    if value < 0x6000:
        reg = value & 7
        width = "b" if value & 0x0400 else "w"
        ins.update(mn=("ldr" if value & 0x0800 else "str") + "-reg-" + width,
                   writes=(reg,) if value & 0x0800 else ())
        return ins
    if value < 0x9000:
        rb, rd = (value >> 3) & 7, value & 7
        width = {12: "w", 13: "w", 14: "b", 15: "b", 16: "h", 17: "h"}.get((value >> 11) & 0x1F)
        if width is None:
            return None
        offset = ((value >> 6) & 0x1F) * {"b": 1, "h": 2, "w": 4}[width]
        if width == "w" and (value >> 11) & 0x1F == 13:
            ins.update(mn="ldr-w", writes=(rd,))
        elif width != "w" and (value >> 11) & 1:
            ins.update(mn="ldr-" + width, writes=(rd,))
        else:
            ins.update(mn="str-" + width, store=(rb, offset, width, rd))
        return ins
    if value < 0xA000:
        reg, offset = (value >> 8) & 7, (value & 0xFF) * 4
        if value & 0x0800:
            ins.update(mn="ldr-sp", writes=(reg,))
        else:
            ins.update(mn="str-sp")
        return ins
    if value < 0xB000:
        ins.update(mn="adr", writes=((value >> 8) & 7,))
        return ins
    if value < 0xB100:
        ins.update(mn="sp-adjust")
        return ins
    if 0xB400 <= value < 0xB600:
        ins.update(mn="push")
        return ins
    if 0xBC00 <= value < 0xBE00:
        ins.update(mn="pop", return_=bool(value & 0x0100))
        return ins
    if 0xC000 <= value < 0xD000:
        rb, regs = (value >> 8) & 7, value & 0xFF
        ins.update(mn="ldm" if value & 0x0800 else "stm", block=(rb, regs, bool(value & 0x0800)))
        return ins
    if value < 0xDF00:
        ins.update(mn="bcond", target=addr + 4 + (signed(value & 0xFF, 8) << 1))
        return ins
    if value < 0xE000:
        ins.update(mn="swi", swi=value & 0xFF)
        return ins
    ins.update(mn="b", target=addr + 4 + (signed(value & 0x7FF, 11) << 1))
    return ins


def decode_arm(rom, addr):
    value = word(rom, addr)
    ins = ins_new(addr, 4, ARM)
    condition = value >> 28
    if (value & 0x0E000000) == 0x0A000000:
        ins.update(mn="b" if condition == 0xE else "bcond",
                   target=addr + 8 + (signed(value & 0xFFFFFF, 24) << 2))
        return ins
    if (value & 0x0F000000) == 0x0B000000:
        ins.update(mn="bl", target=addr + 8 + (signed(value & 0xFFFFFF, 24) << 2))
        ins["call"] = ins["target"]
        return ins
    if (value & 0x0F000000) == 0x0F000000 and condition != 0xF:
        ins.update(mn="swi", swi=value & 0xFFFFFF)
        return ins
    if (value & 0x0E000000) == 0x08000000:
        load = bool(value & 0x00100000)
        rb, regs = (value >> 16) & 0xF, value & 0xFFFF
        ins.update(mn="ldm" if load else "stm", block=(rb, regs, load))
        ins["return_"] = bool(load and regs & 0x8000)
        return ins
    if (value & 0x0C000000) == 0x04000000:
        load, byte = bool(value & 0x00100000), bool(value & 0x00400000)
        rn, rd = (value >> 16) & 0xF, (value >> 12) & 0xF
        if value & 0x02000000:
            if load:
                ins.update(mn="ldr-reg", writes=(rd,))
            return ins
        offset = value & 0xFFF
        if not value & 0x00800000:
            offset = -offset
        if load and rn == 15 and not value & 0x00200000:
            ins.update(mn="ldr-literal", literal=(rd, addr + 8 + offset))
            return ins
        width = "b" if byte else "w"
        if load:
            ins.update(mn="ldr-" + width, writes=(rd,))
        else:
            ins.update(mn="str-" + width, store=(rn, offset, width, rd))
        return ins
    if (value & 0x0E000090) == 0x00000090:
        load, signed_form = bool(value & 0x00100000), bool(value & 0x40)
        rn, rd = (value >> 16) & 0xF, (value >> 12) & 0xF
        offset = ((value >> 4) & 0xF0) | (value & 0xF)
        if not value & 0x00800000:
            offset = -offset
        if signed_form:
            if load:
                ins.update(mn="ldr-sh", writes=(rd,))
            return ins
        if load:
            ins.update(mn="ldr-h", writes=(rd,))
        else:
            ins.update(mn="str-h", store=(rn, offset, "h", rd))
        return ins
    if (value & 0x0FFFFFF0) == 0x012FFF10:
        ins.update(mn="bx", return_=(value & 0xF) in (0xE, 0xF))
        return ins
    if (value & 0x0FFFFFFF) == 0x051FF004:
        ins.update(mn="ldr-pc", return_=True)
        return ins
    if (value & 0x0C000000) == 0:
        opcode = (value >> 21) & 0xF
        rd, rn = (value >> 12) & 0xF, (value >> 16) & 0xF
        if value & 0x02000000:
            record = alu(rd, "mov", right_imm=rotate(value & 0xFF, ((value >> 8) & 0xF) * 2))
            if opcode != 13:
                record = alu(rd, ARM_OPS.get(opcode, "?"), left=rn, right_imm=rotate(
                    value & 0xFF, ((value >> 8) & 0xF) * 2))
        else:
            if value & 0x10:
                ins.update(mn="ldr-reg" if False else "mov-reg-shift", writes=(rd,))
                return ins
            amount = (value >> 7) & 0x1F
            kind = ("lsl", "lsr", "asr", "ror")[(value >> 5) & 3]
            record = alu(rd, "mov", right=value & 0xF, shift=(kind, amount))
            if opcode != 13:
                record = alu(rd, ARM_OPS.get(opcode, "?"), left=rn, right=value & 0xF,
                             shift=(kind, amount))
        if opcode in (8, 9, 10, 11):
            ins.update(mn="test")
        elif opcode == 15:
            ins.update(mn="mvn", writes=(rd,))
        else:
            ins.update(mn=record["op"], alu=record)
        return ins
    return ins


def decode(rom, addr, mode):
    if not in_image(rom, addr):
        return None
    if addr + (4 if mode == ARM else 2) > ROM_BASE + len(rom):
        return None
    if mode == THUMB and half(rom, addr) >= 0xF000 and addr + 4 > ROM_BASE + len(rom):
        return None
    return decode_thumb(rom, addr) if mode == THUMB else decode_arm(rom, addr)


def census(rom, roots=ROOTS):
    seen = set()
    queue = list(roots)
    spans, kicks, swis, blocks, indirect, named, calls = [], [], [], [], [], [], []
    refused, starts = [], 0
    while queue:
        addr, mode = queue.pop(0)
        if addr in seen or not in_image(rom, addr):
            continue
        if starts >= START_CAP:
            refused.append(starts)
            break
        starts += 1
        seen.add(addr)
        start = addr
        const, dma, walked = {}, {}, set()
        count = 0
        while addr not in walked:
            walked.add(addr)
            ins = decode(rom, addr, mode)
            if ins is None:
                break
            count += 1
            if count > WALK_CAP:
                refused.append(start)
                break
            if ins.get("literal"):
                reg, pool = ins["literal"]
                const.pop(reg, None)
                if in_image(rom, pool) and (pool - ROM_BASE) % 4 == 0:
                    const[reg] = word(rom, pool)
            elif ins.get("alu"):
                record = ins["alu"]
                value = alu_value(record, const)
                if value is None:
                    const.pop(record["rd"], None)
                else:
                    const[record["rd"]] = value
            else:
                for reg in ins.get("writes", ()):
                    const.pop(reg, None)
            if ins.get("store"):
                rn, offset, width, rs = ins["store"]
                base = const.get(rn)
                value = const.get(rs)
                if base is not None:
                    target = base + offset
                    if value is not None and (IWRAM[0] <= value < IWRAM[1]
                                              or EWRAM[0] <= value < EWRAM[1]):
                        named.append((addr, value, target))
                    if DMA_BASE <= target < DMA_STOP:
                        channel, index = (target - DMA_BASE) // 12, (target - DMA_BASE) % 12
                        field = DMA_FIELDS.get(index)
                        state = dma.setdefault(channel, {})
                        if field is not None:
                            state[field] = (addr, value)
                        if field == "cnt_l" and width == "w" and value is not None:
                            state["cnt_l"] = (addr, value & 0xFFFF)
                            state["cnt_h"] = (addr, (value >> 16) & 0xFFFF)
                            field = "cnt_h"
                        if field == "cnt_h" and "sad" in state:
                            entry = {"site": addr, "channel": channel,
                                     "sad": state.get("sad"), "dad": state.get("dad"),
                                     "cnt_l": state.get("cnt_l"), "cnt_h": state.get("cnt_h")}
                            hold(kicks, entry)
            if ins.get("swi") is not None:
                swis.append((addr, ins["swi"], mode))
            if ins.get("block"):
                rb, regs, load = ins["block"]
                base = const.get(rb)
                if base is not None and (IWRAM[0] <= base < IWRAM[1]
                                         or EWRAM[0] <= base < EWRAM[1]):
                    blocks.append((addr, base, regs, load, mode))
            if ins.get("call") is not None and in_image(rom, ins["call"]):
                calls.append((addr, ins["call"]))
                queue.append((ins["call"], mode))
            if ins["mn"] in ("bx", "ldr-pc") and not ins["return_"]:
                indirect.append((addr, ins["mn"]))
            if ins.get("target") is not None and in_image(rom, ins["target"]) \
                    and start <= ins["target"] < start + WALK_CAP:
                queue.append((ins["target"], mode))
            if ins["return_"] or ins["mn"] in ("b", "bx", "ldr-pc"):
                break
            addr += ins["size"]
        spans.append((start, addr))
    return {"kicks": kicks, "swis": sorted(set(swis)), "blocks": sorted(set(blocks)),
            "indirect": sorted(set(indirect)), "named": sorted(set(named)),
            "calls": sorted(set(calls)), "spans": spans, "refused": refused, "starts": starts}


def summary(rom, kick):
    sad, dad = kick["sad"], kick["dad"]
    cnt_l, cnt_h = kick["cnt_l"], kick["cnt_h"]
    control = cnt_h[1] if cnt_h else None
    count = cnt_l[1] if cnt_l else None
    unit = None if control is None else (4 if control & 0x0400 else 2)
    source = sad[1] if sad else None
    destination = dad[1] if dad else None
    return {"site": kick["site"], "channel": kick["channel"], "source": source,
            "destination": destination, "count": count, "control": control,
            "bytes": None if count is None or unit is None else count * unit,
            "enabled": bool(control is not None and control & 0x8000),
            "source_fixed": bool(control is not None and (control >> 7) & 3 == 2),
            "width": None if control is None else (4 if control & 0x0400 else 2),
            "source_sites": [sad[0] if sad else None, dad[0] if dad else None,
                             cnt_l[0] if cnt_l else None, cnt_h[0] if cnt_h else None]}


def code_of(rom, summary_row):
    source, destination = summary_row["source"], summary_row["destination"]
    if source is None or destination is None:
        return "unknown"
    if not in_image(rom, source):
        return "not-rom"
    return "rom"


def main(argv):
    if len(argv) != 2:
        print("usage: startup_writes.py <image>")
        return 2
    rom = open(argv[1], "rb").read()
    found = census(rom)
    print("steps=%d starts=%d indirect=%d refused=%d"
          % (len(found["spans"]), found["starts"], len(found["indirect"]),
             len(found["refused"])))
    for kick in found["kicks"]:
        row = summary(rom, kick)
        print("DMA%d site=0x%08X src=%s dst=%s count=%s control=%s bytes=%s fixed=%s"
              % (row["channel"], row["site"],
                 "-" if row["source"] is None else "0x%08X" % row["source"],
                 "-" if row["destination"] is None else "0x%08X" % row["destination"],
                 "-" if row["count"] is None else "0x%X" % row["count"],
                 "-" if row["control"] is None else "0x%04X" % row["control"],
                 "-" if row["bytes"] is None else "0x%X" % row["bytes"],
                 row["source_fixed"]))
    for site, immediate, mode in found["swis"]:
        print("SWI site=0x%08X immediate=0x%02X mode=%s"
              % (site, immediate, "thumb" if mode == THUMB else "arm"))
    for site, value, target in found["named"]:
        print("NAMED site=0x%08X value=0x%08X target=0x%08X" % (site, value, target))
    for site, base, regs, load, mode in found["blocks"]:
        print("BLOCK site=0x%08X base=0x%08X regs=0x%04X %s"
              % (site, base, regs, "ldm" if load else "stm"))
    for site, kind in found["indirect"]:
        print("INDIRECT site=0x%08X %s" % (site, kind))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))





