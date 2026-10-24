from __future__ import annotations

import argparse
import os
import struct
import sys

ROM_BASE = 0x08000000
ROM_SIZE = 8388608
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ROM = os.path.join(ROOT, "baserom.gba")
EVIDENCE = os.path.join(ROOT, "tools", "code", "CENSUS_EVIDENCE.csv")
DOC = os.path.join(ROOT, "docs", "CODE_SPLIT.md")
VECTOR = 0x08000000
CRT0 = 0x080000C0
IMAGE_START = 0x08000138
STEP_LIMIT = 0x10000
BLOCK = 0x10000
UNCLASSIFIED = 0
PROVEN = 1
FILTERED = 2
POOL = 3
TABLE = 5
CLASSES = (PROVEN, FILTERED, TABLE, POOL, UNCLASSIFIED)
CLASS_NAMES = {PROVEN: "proven code", FILTERED: "filtered pointer-entry code",
               TABLE: "table-held code", POOL: "literal pool",
               UNCLASSIFIED: "unclassified"}
STRENGTH = {PROVEN: 0, TABLE: 1, FILTERED: 2, POOL: 5, UNCLASSIFIED: 9}
MODE_NONE = 0
MODE_THUMB = 1
MODE_ARM = 2
MODE_NAMES = {MODE_THUMB: "thumb", MODE_ARM: "arm"}
FILTER_BRANCHES = 1
FACTORY_REPEATS = 4
CHANNEL_ROUNDS = 8
RUN = 8
PAD = 8
BODY_CAP = 0x400
CHANNELS = ("vector", "copy", "call", "pool", "table", "repeated")
CHANNEL_PRIORITY = ("vector", "copy", "call", "pool", "table", "repeated")
COPY_REGISTER = 0x040000D4
COPY_DEST = (0x03000000, 0x03008000)
COPY_SOURCE_CAP = 0x1000
COPY_SIZE_CAP = 0x1000
REASONS = ("-", "next-start", "pool", "no-return", "no-body")
FLAGS = ("data", "undecodable", "clobber")
HEADER = "address,kind,channel,mode,end,reason,flags,evidence"
THUMB_UNDEFINED = ((0x4780, 0x47FF), (0xB100, 0xB3FF), (0xB600, 0xBBFF), (0xBE00, 0xBFFF),
                   (0xDE00, 0xDEFF), (0xE800, 0xEFFF))
_UNDEFINED = bytes(
    1 if any(low <= half <= high for low, high in THUMB_UNDEFINED) else 0
    for half in range(0x10000))
_SIZE = bytes(0 if half >= 0xF800 or _UNDEFINED[half] else 4 if half >= 0xF000 else 2
              for half in range(0x10000))
_VIEWS = {}


def views_of(rom):
    found = _VIEWS.get(id(rom))
    if found is not None and found[0] is rom:
        return found
    if sys.byteorder != "little":
        raise SystemExit("this tree reads the retail image little-endian, and this host is "
                         "%s-endian" % sys.byteorder)
    halves = memoryview(rom)[:len(rom) - len(rom) % 2].cast("H")
    words = memoryview(rom)[:len(rom) - len(rom) % 4].cast("I")
    if len(_VIEWS) > 3:
        _VIEWS.clear()
    found = (rom, halves, words)
    _VIEWS[id(rom)] = found
    return found


def hw(rom, addr):
    offset = addr - ROM_BASE
    if offset & 1:
        return struct.unpack_from("<H", rom, offset)[0]
    return views_of(rom)[1][offset >> 1]


def word(rom, addr):
    offset = addr - ROM_BASE
    if offset & 3:
        return struct.unpack_from("<I", rom, offset)[0]
    return views_of(rom)[2][offset >> 2]


def in_image(rom, addr):
    return ROM_BASE <= addr < ROM_BASE + len(rom)


def has_word(rom, addr):
    return ROM_BASE <= addr and addr + 4 <= ROM_BASE + len(rom)


def thumb_size(view, index, count):
    if index + 1 > count:
        return None
    size = _SIZE[view[index]]
    if size == 4:
        return 4 if index + 2 <= count and view[index + 1] >= 0xF800 else None
    return size or None


def thumb_length(rom, addr):
    offset = addr - ROM_BASE
    if not offset & 1:
        view = views_of(rom)[1]
        return thumb_size(view, offset >> 1, len(view))
    if addr + 2 > ROM_BASE + len(rom):
        return None
    half = struct.unpack_from("<H", rom, offset)[0]
    if half >= 0xF000:
        if half >= 0xF800 or addr + 4 > ROM_BASE + len(rom):
            return None
        return 4 if struct.unpack_from("<H", rom, offset + 2)[0] >= 0xF800 else None
    return None if _UNDEFINED[half] else 2


def arm_branch_target(addr, instruction):
    offset = instruction & 0x00FFFFFF
    if offset & 0x00800000:
        offset -= 0x01000000
    return (addr + 8 + (offset << 2)) & 0xFFFFFFFF


def thumb_branch_target(addr, half):
    offset = half & 0x07FF
    if offset & 0x0400:
        offset -= 0x0800
    return (addr + 4 + (offset << 1)) & 0xFFFFFFFF


def thumb_call_target(rom, addr):
    high = hw(rom, addr)
    low = hw(rom, addr + 2)
    offset = ((high & 0x07FF) << 11) | (low & 0x07FF)
    if high & 0x0400:
        offset -= 1 << 22
    return (addr + 4 + (offset << 1)) & 0xFFFFFFFF


def literal_target(rom, addr):
    instruction = word(rom, addr)
    if (instruction & 0x0F7F0000) != 0x051F0000:
        return None
    offset = instruction & 0x0FFF
    if not instruction & 0x00800000:
        offset = -offset
    return ((addr + 8) & ~3) + offset


def mark(classes, modes, addr, size, value, mode):
    offset = addr - ROM_BASE
    strength = STRENGTH[value]
    for index in range(offset, offset + size):
        if STRENGTH[classes[index]] > strength:
            classes[index] = value
            modes[index] = mode


def thumb_dest(half):
    if half < 0x1800:
        return half & 0x07
    if half < 0x2000:
        return half & 0x07
    if half < 0x4000:
        return (half >> 8) & 0x07
    if half < 0x4400:
        operation = (half >> 6) & 0x0F
        return None if operation in (8, 10, 11) else half & 0x07
    if half < 0x4800:
        return (half & 0x07) | ((half >> 4) & 0x08)
    if half < 0x5000:
        return (half >> 8) & 0x07
    if half < 0x6000:
        return None if (half >> 11) & 1 else half & 0x07
    if half < 0x9000:
        return None if (half & 0x0800) == 0 and (half & 0x1000) else half & 0x07
    if half < 0xA000:
        return None if (half >> 11) & 1 else (half >> 8) & 0x07
    if half < 0xA800:
        return (half >> 8) & 0x07
    return None


def thumb_home(half):
    if 0x4400 <= half < 0x4800:
        return ((half >> 4) & 0x08) | (half >> 8) & 0x07, half & 0x0F
    return None


def arm_home(instruction):
    if (instruction & 0x0FE00000) == 0x01A00000:
        return (instruction >> 12) & 0x0F, instruction & 0x0F
    if (instruction & 0x0FE00000) == 0x00800000:
        return (instruction >> 12) & 0x0F, instruction & 0x0F
    return None


def thumb_step(rom, addr, classes, modes, value, last):
    view = views_of(rom)[1]
    index = (addr - ROM_BASE) >> 1
    size = thumb_size(view, index, len(view))
    if size is None:
        return addr, True, [], None, None, 0, None, []
    mark(classes, modes, addr, size, value, MODE_THUMB)
    half = view[index]
    if size == 4:
        target = thumb_call_target(rom, addr)
        calls = [(target, MODE_THUMB)] if in_image(rom, target) else []
        return addr + 4, False, [], None, None, 0, None, calls
    if (half & 0xFF87) in (0x4487, 0x4687):
        return addr + 2, True, [], None, None, 0, None, []
    if (half & 0xFF80) == 0x4700:
        entries = []
        register = half & 0x0F
        if register != 14 and last is not None and last[0] == register:
            if last[1] & 1 and in_image(rom, last[1] & ~1):
                entries.append((last[1] & ~1, MODE_THUMB))
        return addr + 2, True, entries, None, (half == 0x4770, half), 0, None, []
    if (half & 0xFF00) == 0xBD00:
        return addr + 2, True, [], None, (True, half), 0, None, []
    if (half & 0xFF00) == 0xDF00:
        return addr + 2, True, [], None, (True, half), 0, None, []
    if (half & 0xF800) == 0xE000:
        target = thumb_branch_target(addr, half)
        entries = [(target, MODE_THUMB)] if in_image(rom, target) else []
        return addr + 2, True, entries, None, (False, half), 0, None, []
    if (half & 0xF000) == 0xD000:
        offset = half & 0x00FF
        if offset & 0x80:
            offset -= 0x100
        target = addr + 4 + (offset << 1)
        entries = [(target, MODE_THUMB)] if in_image(rom, target) else []
        return addr + 2, False, entries, None, None, 1, None, []
    if (half & 0xF800) == 0x4800:
        pool = ((addr + 4) & ~3) + (half & 0x00FF) * 4
        last = ((half >> 8) & 0x07, word(rom, pool)) if has_word(rom, pool) else None
        return addr + 2, False, [], pool, None, 0, last, []
    return addr + 2, False, [], None, None, 0, None, []


def arm_step(rom, addr, classes, modes, value, last):
    if not has_word(rom, addr):
        return addr, True, [], None, None, 0, None, []
    instruction = word(rom, addr)
    if instruction >> 28 == 0x0F:
        return addr, True, [], None, None, 0, None, []
    mark(classes, modes, addr, 4, value, MODE_ARM)
    if instruction in (0xE12FFF1E, 0xE1A0F00E):
        return addr + 4, True, [], None, (True, instruction), 0, None, []
    if (instruction & 0x0FFF8000) == 0x08BD8000:
        return addr + 4, True, [], None, (True, instruction), 0, None, []
    if (instruction & 0x0FFFFFF0) == 0x012FFF10:
        entries = []
        register = instruction & 0x0F
        if register != 14 and last is not None and last[0] == register:
            if in_image(rom, last[1] & ~1):
                mode = MODE_THUMB if last[1] & 1 else MODE_ARM
                entries.append((last[1] & ~1, mode))
        return addr + 4, True, entries, None, (False, instruction), 0, None, []
    if (instruction & 0x0F000000) == 0x0B000000:
        target = arm_branch_target(addr, instruction)
        calls = [(target, MODE_ARM)] if in_image(rom, target) else []
        return addr + 4, False, [], None, None, 0, None, calls
    if (instruction & 0x0F000000) == 0x0A000000:
        target = arm_branch_target(addr, instruction)
        entries = [(target, MODE_ARM)] if in_image(rom, target) else []
        if instruction >> 28 == 0x0E:
            return addr + 4, True, entries, None, (False, instruction), 0, None, []
        return addr + 4, False, entries, None, None, 1, None, []
    if (instruction & 0x0F7F0000) == 0x051F0000:
        pool = literal_target(rom, addr)
        if not has_word(rom, pool):
            return addr + 4, False, [], None, None, 0, None, []
        loaded = word(rom, pool)
        register = (instruction >> 12) & 0x0F
        entries = []
        if register == 15:
            if in_image(rom, loaded & ~1):
                mode = MODE_THUMB if loaded & 1 else MODE_ARM
                entries.append((loaded & ~1, mode))
            return addr + 4, True, entries, pool, (True, instruction), 0, None, []
        if register == 14 and in_image(rom, loaded & ~1):
            mode = MODE_THUMB if loaded & 1 else MODE_ARM
            entries.append((loaded & ~1, mode))
        return addr + 4, False, entries, pool, None, 0, (register, loaded), []
    if (((instruction >> 12) & 0x0F) == 0x0F
            and (instruction & 0x0C000000) in (0x00000000, 0x04000000, 0x08000000)
            and (instruction & 0x0F800000) != 0x01000000):
        return addr + 4, True, [], None, (True, instruction), 0, None, []
    return addr + 4, False, [], None, None, 0, None, []


def walk(rom, roots, classes, modes, value):
    queue = list(roots)
    seen = set()
    spans = []
    pools = set()
    entries = set()
    calls = {}
    while queue:
        start, mode = queue.pop()
        if (start, mode) in seen:
            continue
        seen.add((start, mode))
        entries.add((start, mode))
        addr = start
        last = None
        steps = 0
        while steps < STEP_LIMIT:
            steps += 1
            if mode == MODE_THUMB:
                addr, ended, new, pool, _closed, _branches, last, called = thumb_step(
                    rom, addr, classes, modes, value, last)
            else:
                addr, ended, new, pool, _closed, _branches, last, called = arm_step(
                    rom, addr, classes, modes, value, last)
            for target, target_mode in new:
                queue.append((target, target_mode))
            for target, target_mode in called:
                queue.append((target, target_mode))
                calls.setdefault((target, target_mode), addr)
            if pool is not None:
                pools.add(pool)
            if ended or not in_image(rom, addr):
                break
        if addr > start:
            spans.append((start, addr, mode))
    return spans, pools, entries, calls


def probe(rom, entry):
    queue = [entry]
    seen = set()
    returned = False
    branches = 0
    view = views_of(rom)[1]
    count = len(view)
    while queue:
        addr = queue.pop()
        if addr in seen:
            continue
        seen.add(addr)
        index = (addr - ROM_BASE) >> 1
        steps = 0
        while steps < STEP_LIMIT:
            steps += 1
            size = thumb_size(view, index, count)
            if size is None:
                return False, False, 0
            half = view[index]
            if size == 4:
                target = thumb_call_target(rom, addr)
                if in_image(rom, target):
                    queue.append(target)
                addr += 4
                index += 2
                continue
            if (half & 0xFF80) == 0x4700:
                if half == 0x4770:
                    returned = True
                break
            if (half & 0xFF00) == 0xBD00:
                returned = True
                break
            if (half & 0xFF00) == 0xDF00:
                break
            if (half & 0xF800) == 0xE000:
                target = thumb_branch_target(addr, half)
                if in_image(rom, target):
                    queue.append(target)
                break
            if (half & 0xF000) == 0xD000:
                branches += 1
                offset = half & 0x00FF
                if offset & 0x80:
                    offset -= 0x100
                target = addr + 4 + (offset << 1)
                if in_image(rom, target):
                    queue.append(target)
                addr += 2
                index += 1
                continue
            addr += 2
            index += 1
        else:
            return False, False, 0
    return True, returned, branches


def closure(rom, entry):
    position = entry
    visited = set()
    targets = set()
    returned = False
    extent = entry
    steps = 0
    while steps < STEP_LIMIT:
        steps += 1
        if thumb_length(rom, position) is None:
            return "invalid", extent
        half = hw(rom, position)
        visited.add(position)
        after, ended, new, _pool, _closed, _branches, _last, called = thumb_step(
            rom, position, None, None, UNCLASSIFIED, None)
        extent = max(extent, after)
        for target, _mode in new + called:
            targets.add(target)
        if ended:
            if half == 0x4770 or half == 0x46F7 or (half & 0xFF00) == 0xBD00:
                returned = True
            break
        position = after
    else:
        return "step-limit", extent
    if returned:
        return "return", extent
    return "no-return", extent


def named_words(rom):
    values = views_of(rom)[2]
    end = ROM_BASE + len(rom)
    flags = bytearray(len(values))
    for index, value in enumerate(values):
        if value & 1 and ROM_BASE <= (value & ~1) < end:
            flags[index] = 1
    return values, flags


def thumb_entries(rom):
    targets = set()
    words = 0
    end = ROM_BASE + len(rom)
    for value in views_of(rom)[2]:
        if value & 1 and ROM_BASE <= value < end:
            words += 1
            targets.add(value & ~1)
    return targets, words


def pointer_runs(rom):
    values, flags = named_words(rom)
    runs = []
    current = []
    for index, hit in enumerate(flags):
        if hit:
            current.append((index * 4, values[index] & ~1))
        elif current:
            if len(current) > 1:
                runs.append(current)
            current = []
    if len(current) > 1:
        runs.append(current)
    return runs


def repeated_code_pointers(rom):
    values, flags = named_words(rom)
    counts = {}
    first = {}
    for index, hit in enumerate(flags):
        if hit:
            counts[values[index]] = counts.get(values[index], 0) + 1
            first.setdefault(values[index], index * 4)
    return {value: first[value] for value, count in counts.items() if count >= FACTORY_REPEATS}


def table_targets(runs, proven):
    out = {}
    for run in runs:
        if any(value in proven for _site, value in run):
            for site, value in run:
                out.setdefault(value, site)
    return out


def copy_descriptors(rom):
    found = []
    halves = views_of(rom)[1]
    for index in range(len(halves)):
        half = halves[index]
        if (half & 0xF800) != 0x4800:
            continue
        at = ROM_BASE + 2 * index
        pool = ((at + 4) & ~3) + (half & 0x00FF) * 4
        if not has_word(rom, pool) or word(rom, pool) != COPY_REGISTER:
            continue
        values = []
        probe = at + 2
        for _step in range(10):
            item = hw(rom, probe)
            if (item & 0xF800) == 0x4800:
                source = ((probe + 4) & ~3) + (item & 0x00FF) * 4
                if has_word(rom, source):
                    values.append((probe, word(rom, source)))
            probe += 2
        image = next((value for _site, value in values
                      if in_image(rom, value) and value < ROM_BASE + COPY_SOURCE_CAP), None)
        dest = next((value for _site, value in values
                     if COPY_DEST[0] <= value < COPY_DEST[1]), None)
        if image is None or dest is None:
            continue
        count = None
        probe = at + 2
        for _step in range(16):
            item = hw(rom, probe)
            if (item & 0xF800) == 0x2000:
                register = (item >> 8) & 0x07
                for forward in range(1, 5):
                    store = hw(rom, probe + 2 * forward)
                    if ((store & 0xF800) == 0x8000 and ((store >> 6) & 0x1F) == 4
                            and (store & 0x07) == register):
                        count = item & 0x00FF
                        break
            if count is not None:
                break
            probe += 2
        if count is None:
            continue
        size = count * 4
        if not 0 < size <= COPY_SIZE_CAP or not has_word(rom, image + size - 4):
            continue
        found.append({"site": at, "source": image, "dest": dest, "size": size,
                      "declared": count})
    return found


def copy_mode(rom, source):
    if (word(rom, source) >> 28) != 0x0F:
        return MODE_ARM
    return MODE_THUMB


def pointer_words(rom, addresses):
    found = {}
    for address in sorted(addresses):
        if address % 4 or not has_word(rom, address):
            continue
        value = word(rom, address)
        if value & 1 and in_image(rom, value & ~1):
            found.setdefault(value & ~1, address)
    return found


def class_runs(classes, value):
    out = []
    pos = 0
    total = len(classes)
    while pos < total:
        start = classes.find(value, pos)
        if start < 0:
            break
        stop = start
        while stop < total and classes[stop] == value:
            stop += 1
        out.append((start, stop))
        pos = stop
    return out


def permute(rom):
    out = bytearray(rom)
    for base in range(0, len(out), BLOCK):
        block = bytes(out[base:base + BLOCK])
        pairs = [block[index:index + 2] for index in range(0, len(block) - 1, 2)]
        pairs.reverse()
        out[base:base + len(block)] = b"".join(pairs)
    return bytes(out)


def census(rom, channels=CHANNELS):
    channels = tuple(name for name in CHANNEL_PRIORITY if name in set(channels))
    if "vector" not in channels:
        raise ValueError("the census reads no byte without its roots")
    classes = bytearray(len(rom))
    modes = bytearray(len(rom))
    spans, pools, proven_entries, calls = walk(
        rom, [(VECTOR, MODE_ARM), (CRT0, MODE_ARM)], classes, modes, PROVEN)
    copies = copy_descriptors(rom) if "copy" in channels else []
    for copy in copies:
        mode = copy_mode(rom, copy["source"])
        modes_span, more, entries, made = walk(
            rom, [(copy["source"], mode)], classes, modes, PROVEN)
        spans += modes_span
        pools.update(more)
        proven_entries.update(entries)
        for target in made:
            calls.setdefault(target, None)
    taken, taken_words = thumb_entries(rom)
    runs = pointer_runs(rom) if "table" in channels else []
    verdicts = {}
    accepted = {}
    order = []
    walked = {}
    walks = 0
    rounds = []

    def verdict(entry):
        if entry not in verdicts:
            verdicts[entry] = probe(rom, entry[0])
        return verdicts[entry]

    def prove(targets):
        nonlocal walks
        pending = list(targets)
        while pending:
            item = pending.pop()
            if item in proven_entries:
                continue
            proven_entries.add(item)
            _spans, more, entries, made = walk(rom, [item], classes, modes, PROVEN)
            pools.update(more)
            proven_entries.update(entries)
            pending += list(made)
            walks += 1

    while len(rounds) < CHANNEL_ROUNDS:
        before = (len(accepted), len(proven_entries), len(calls), len(pools))
        proven_addresses = {address for address, _mode in proven_entries}
        tabled = table_targets(runs, proven_addresses) if runs else {}
        candidates = []
        if "call" in channels:
            candidates += [(entry, "call") for entry in calls]
        if "table" in channels:
            candidates += [((address, MODE_THUMB), "table") for address in taken]
        if "pool" in channels:
            candidates += [((address, MODE_THUMB), "pool")
                           for address in pointer_words(rom, pools)]
        if "repeated" in channels:
            candidates += [((address & ~1, MODE_THUMB), "repeated")
                           for address in repeated_code_pointers(rom)]
        for entry, channel in sorted(candidates):
            if entry in accepted or entry[1] != MODE_THUMB:
                continue
            ok, returned, branches = verdict(entry)
            if not ok or not returned:
                continue
            if channel == "table":
                if not (entry in calls or entry[0] in tabled or branches >= FILTER_BRANCHES):
                    continue
            accepted[entry] = [channel]
            order.append(entry)
        for entry in order:
            due = PROVEN if entry in calls else FILTERED
            if walked.get(entry) == due:
                continue
            walked[entry] = due
            _spans, more, entries, made = walk(rom, [entry], classes, modes, due)
            pools.update(more)
            if due == PROVEN:
                proven_entries.update(entries)
            for target in made:
                calls.setdefault(target, None)
            walks += 1
        prove(set(calls) - proven_entries)
        if (len(accepted), len(proven_entries), len(calls), len(pools)) == before:
            break
        rounds.append(before)
    for pool in pools:
        if has_word(rom, pool):
            mark(classes, modes, pool, 4, POOL, MODE_NONE)
    return {"classes": classes, "modes": modes, "spans": spans, "pools": pools,
            "proven_entries": proven_entries, "calls": calls, "accepted": accepted,
            "order": order, "taken": taken, "taken_words": taken_words, "walks": walks,
            "channels": channels, "runs": len(runs), "copies": copies}


def thumb_effects(rom, addr):
    half = hw(rom, addr)
    size = thumb_length(rom, addr)
    if size is None:
        return {"size": 0, "broken": True, "ended": True, "returned": False, "targets": [],
                "saving": False, "written": set(), "home": None}
    ended = returned = False
    targets = []
    saving = (half & 0xFE00) == 0xB400 and bool(half & 0x0100)
    home = thumb_home(half)
    written = set()
    dest = thumb_dest(half)
    if dest is not None and dest < 4:
        written.add(dest)
    if size == 4:
        target = thumb_call_target(rom, addr)
        if in_image(rom, target):
            targets.append((target, MODE_THUMB))
        return {"size": 4, "broken": False, "ended": False, "returned": False,
                "targets": targets, "saving": False, "written": set(), "home": None}
    if (half & 0xFF80) == 0x4700:
        ended = True
        returned = half == 0x4770
    elif (half & 0xFF00) == 0xBD00:
        ended = returned = True
    elif (half & 0xFF00) == 0xDF00:
        ended = returned = True
    elif (half & 0xF800) == 0xE000:
        ended = True
        target = thumb_branch_target(addr, half)
        if in_image(rom, target):
            targets.append((target, MODE_THUMB))
    elif (half & 0xF000) == 0xD000:
        offset = half & 0x00FF
        if offset & 0x80:
            offset -= 0x100
        target = addr + 4 + (offset << 1)
        if in_image(rom, target):
            targets.append((target, MODE_THUMB))
    return {"size": size, "broken": False, "ended": ended, "returned": returned,
            "targets": targets, "saving": saving, "written": written, "home": home}


def arm_effects(rom, addr):
    if not has_word(rom, addr):
        return {"size": 0, "broken": True, "ended": True, "returned": False, "targets": [],
                "saving": False, "written": set(), "home": None}
    instruction = word(rom, addr)
    if instruction >> 28 == 0x0F:
        return {"size": 0, "broken": True, "ended": True, "returned": False, "targets": [],
                "saving": False, "written": set(), "home": None}
    ended = returned = False
    targets = []
    saving = (instruction & 0xFFFF0000) == 0xE92D0000 and bool(instruction & 0x4000)
    home = arm_home(instruction)
    written = set()
    dest = (instruction >> 12) & 0x0F
    if dest < 4 and (instruction & 0x0C000000) != 0x08000000:
        written.add(dest)
    if instruction in (0xE12FFF1E, 0xE1A0F00E):
        ended = returned = True
    elif (instruction & 0x0FFF8000) == 0x08BD8000:
        ended = returned = True
    elif (instruction & 0x0F000000) == 0x0A000000:
        target = arm_branch_target(addr, instruction)
        if in_image(rom, target):
            targets.append((target, MODE_ARM))
        ended = instruction >> 28 == 0x0E
    elif (((instruction >> 12) & 0x0F) == 0x0F
          and (instruction & 0x0C000000) in (0x00000000, 0x04000000, 0x08000000)
          and (instruction & 0x0F800000) != 0x01000000):
        ended = returned = True
    return {"size": 4, "broken": False, "ended": ended, "returned": returned,
            "targets": targets, "saving": saving, "written": written, "home": home}


def effects(rom, addr, mode):
    return thumb_effects(rom, addr) if mode == MODE_THUMB else arm_effects(rom, addr)


def body(rom, start, mode, limit):
    seen = set()
    returned = False
    extent = start
    todo = [start]
    steps = 0
    while todo and steps < STEP_LIMIT:
        position = todo.pop()
        while position not in seen and start <= position < limit and steps < STEP_LIMIT:
            steps += 1
            found = effects(rom, position, mode)
            if found["size"] == 0:
                return seen, extent, returned
            seen.add(position)
            extent = max(extent, position + found["size"])
            if found["returned"]:
                returned = True
            for target, target_mode in found["targets"]:
                if target_mode == mode:
                    todo.append(target)
            if found["ended"]:
                break
            position += found["size"]
    return seen, extent, returned


def leading(rom, address, mode, count=8):
    found = []
    at = address
    while len(found) < count:
        item = effects(rom, at, mode)
        if item["size"] == 0:
            return found, at, True
        found.append((at, item))
        at += item["size"]
        if item["saving"] or item["ended"]:
            break
    return found, at, False


def closest(rom, address, mode):
    found, _at, broken = leading(rom, address, mode, 6)
    if broken:
        return None
    for at, item in found:
        if item["saving"]:
            return at if at > address else None
    return None


def home_after(rom, address, mode, count=2):
    found, _at, _broken = leading(rom, address, mode, count)
    return [item["home"] for _at, item in found if item.get("home")]


def flag_of(rom, address, mode):
    items, after, broken = leading(rom, address, mode)
    flags = []
    if closest(rom, address, mode) is not None:
        flags.append("data")
    if broken or any(item["broken"] for _at, item in items):
        flags.append("undecodable")
    written = set()
    for _at, item in items:
        if item["saving"] or item["ended"]:
            break
        written |= item["written"]
    if written and items and items[-1][1]["saving"]:
        for home in home_after(rom, after, mode):
            if home[1] in written:
                flags.append("clobber")
                break
    return flags


def ends_of(rom, starts, modes, pools):
    bounds = sorted(set(starts))
    pool_edges = sorted(pools)
    out = {}
    bodies = {}
    for address in bounds:
        mode = modes.get(address, MODE_THUMB)
        following = next((bound for bound in bounds if bound > address), None)
        pool = next((edge for edge in pool_edges if edge > address), None)
        edges = [edge for edge in (following, pool) if edge is not None]
        edge = min(edges) if edges else None
        limit = min(edge, address + BODY_CAP) if edge is not None else address + BODY_CAP
        seen, extent, returned = body(rom, address, mode, limit)
        bodies[address] = seen
        if not seen or extent <= address:
            out[address] = (None, "no-body")
        elif edge is not None and edge < extent:
            out[address] = (edge, "next-start" if edge == following else "pool")
        elif not returned:
            out[address] = (extent, "no-return")
        else:
            out[address] = (extent, "-")
    return out, bodies


def fragments_of(accepted, ends, bodies):
    out = {}
    starts = sorted(accepted)
    for address in starts:
        mode = accepted[address]["mode"]
        inside = set()
        for start in starts:
            if start == address:
                continue
            if accepted[start]["mode"] != mode:
                continue
            end = ends[start][0]
            if end is not None and start < address < end:
                inside.add(start)
        if inside:
            out[address] = max(inside)
    return out


def census_result(rom, channels=CHANNELS):
    measured = census(rom, channels)
    classes = measured["classes"]
    starts = {}
    for entry in measured["order"]:
        address, mode = entry
        starts[address] = {"mode": mode, "limbs": list(measured["accepted"][entry])}
    proven_addresses = {address for address, _mode in measured["proven_entries"]}
    for address, mode in sorted(measured["proven_entries"]):
        if address not in starts:
            limbs = ["vector"] if address in (VECTOR, CRT0) else ["proven"]
            starts[address] = {"mode": mode, "limbs": limbs}
    for copy in measured["copies"]:
        for address in starts:
            if copy["source"] <= address < copy["source"] + copy["size"]:
                if starts[address]["limbs"] == ["proven"]:
                    starts[address]["limbs"] = ["copy"]
    modes = {address: item["mode"] for address, item in starts.items()}
    ends, bodies = ends_of(rom, starts, modes, measured["pools"])
    flags = {address: flag_of(rom, address, modes[address]) for address in starts}
    fragments = fragments_of(starts, ends, bodies)
    proven_bytes = sum(end - address for address, (end, _reason) in ends.items() if end)
    return {"measured": measured, "classes": classes, "starts": starts, "ends": ends,
            "flags": flags, "fragments": fragments, "proven_bytes": proven_bytes,
            "modes": modes}


def shaped_in(rom, ranges):
    total = 0
    for begin, end in ranges:
        position = begin
        while position < end:
            run = position
            while run < end and thumb_length(rom, ROM_BASE + run) is not None:
                run += 2
            if run - position >= 2 * RUN:
                total += run - position
            position = max(run, position + 2)
    return total


def padding_in(rom, ranges):
    out = []
    for begin, end in ranges:
        position = begin
        while position < end:
            value = rom[position]
            run = position
            while run < end and rom[run] == value:
                run += 1
            if value in (0x00, 0xFF) and run - position >= PAD:
                out.append((position, run))
            position = run
    return union(out)


def remainder(rom, result):
    closed = bytearray(len(rom))
    for address, (end, _reason) in result["ends"].items():
        if end:
            closed[address - ROM_BASE:end - ROM_BASE] = b"\x01" * (end - address)
    leftover = []
    offset = 0
    total = len(rom)
    while offset < total:
        if closed[offset]:
            offset += 1
            continue
        start = offset
        while offset < total and not closed[offset]:
            offset += 1
        leftover.append((start, offset))
    pads = padding_in(rom, leftover)
    padded = bytearray(len(rom))
    for begin, end in pads:
        padded[begin:end] = b"\x01" * (end - begin)
    clean = []
    for begin, end in leftover:
        position = begin
        while position < end:
            if padded[position]:
                while position < end and padded[position]:
                    position += 1
                continue
            start = position
            while position < end and not padded[position]:
                position += 1
            clean.append((start, position))
    shaped = shaped_in(rom, clean)
    pad_bytes = sum(end - begin for begin, end in pads)
    leftover_bytes = sum(end - begin for begin, end in leftover)
    null = shaped_in(permute(rom), clean)
    return {"leftover": leftover, "bytes": leftover_bytes, "padding": pad_bytes,
            "shaped": shaped, "unshaped": leftover_bytes - pad_bytes - shaped,
            "null_shaped": null, "null_share": 100.0 * null / max(shaped, 1)}


def union(intervals):
    out = []
    for begin, end in sorted(intervals):
        if out and begin <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((begin, end))
    return out


def inside(intervals, offset):
    for begin, end in intervals:
        if begin <= offset < end:
            return True
    return False


def next_edge(intervals, offset, limit):
    for begin, end in intervals:
        if begin <= offset < end:
            return min(end, limit)
    return offset + 1


def channel_text(result):
    counts = {}
    for address, item in result["starts"].items():
        for limb in item["limbs"]:
            counts[limb] = counts.get(limb, 0) + 1
    return counts


def rows(result):
    measured = result["measured"]
    out = []
    for address in sorted(result["starts"]):
        item = result["starts"][address]
        end, reason = result["ends"][address]
        out.append((address, "start", "+".join(item["limbs"]), MODE_NAMES[item["mode"]],
                    end, reason, "+".join(result["flags"][address]),
                    evidence_of(measured, address)))
    for address in sorted(result["fragments"]):
        item = result["starts"][address]
        end, reason = result["ends"][address]
        out.append((address, "fragment", "+".join(item["limbs"]), MODE_NAMES[item["mode"]],
                    end, reason, "+".join(result["flags"][address]),
                    "inside the start at 0x%08x" % result["fragments"][address]))
    return out


def evidence_of(measured, address):
    if address == VECTOR:
        return "the reset vector at 0x08000000"
    if address == CRT0:
        return "the startup block's entry"
    call = measured["calls"].get((address, MODE_THUMB))
    if call is None:
        call = measured["calls"].get((address, MODE_ARM))
    if call is not None:
        return "the call at 0x%08x names it" % call
    channel = "table"
    for entry, item in measured["accepted"].items():
        if entry[0] == address:
            channel = item[0]
            break
    for copy in measured["copies"]:
        if copy["source"] <= address < copy["source"] + copy["size"]:
            return "the DMA3 copy setup at 0x%08x names it" % copy["site"]
    return {"pool": "a literal-pool word names it",
            "repeated": "a pointer word repeated four or more times names it",
            "table": "a run of address-taken words names it"}.get(
                channel, "the walk reached it")


def text(rows_in):
    lines = [HEADER]
    for address, kind, channel, mode, end, reason, flags, evidence in rows_in:
        lines.append("0x%08x,%s,%s,%s,%s,%s,%s,%s"
                     % (address, kind, channel or "-", mode,
                        "0x%08x" % end if end else "-", reason, flags or "-", evidence))
    return "\n".join(lines) + "\n"


def doc_text(result, remainder_result):
    measured = result["measured"]
    channels = channel_text(result)
    total = ROM_SIZE
    ends = result["ends"]
    closed = [address for address in ends if ends[address][0]]
    open_bounds = [address for address in ends if not ends[address][0]]
    reasons = dict((reason, len([1 for address in ends if ends[address][1] == reason]))
                   for reason in REASONS)
    flagged = dict((flag, len([1 for address in result["flags"]
                               if flag in result["flags"][address]])) for flag in FLAGS)
    class_bytes = dict((name, 0) for name in CLASS_NAMES.values())
    for value, name in CLASS_NAMES.items():
        class_bytes[name] = measured["classes"].count(value)
    lines = ["# The code and data split", "",
             "`tools/split/census.py` derives this page from the retail image and `--check` "
             "re-derives it.", "",
             "## Channels", "",
             "| channel | entries it starts |", "| --- | --- |"]
    for name in CHANNEL_PRIORITY:
        lines.append("| %s | %d |" % (name, channels.get(name, 0)))
    lines += ["", "The address-taken channel sees %d odd in-image words, %d distinct addresses, in "
              "%d runs of two or more consecutive words." %
              (measured["taken_words"], len(measured["taken"]), measured["runs"])]
    for copy in measured["copies"]:
        lines.append("The copy channel reads the DMA3 setup at `0x%08x`: %d B from `0x%08x` to "
                     "IWRAM `0x%08x`." % (copy["site"], copy["size"], copy["source"],
                                          copy["dest"]))
    lines += ["",
              "## Starts and ends", "",
              "%d starts, %d with an end, %d open; %d fragment entries lie inside another start."
              % (len(result["starts"]), len(closed), len(open_bounds),
                 len(result["fragments"])), "",
              "| reason | starts |", "| --- | --- |"]
    for reason in REASONS:
        lines.append("| %s | %d |" % (reason, reasons.get(reason, 0)))
    lines += ["", "Entry flags:", "",
              "| flag | starts |", "| --- | --- |"]
    for flag in FLAGS:
        lines.append("| %s | %d |" % (flag, flagged.get(flag, 0)))
    lines += ["", "A `no-return` end is where the walk stopped at a halfword the CPU cannot "
              "execute before it met a return, so it is a measured stop and not a return. "
              "Runtime-only entries: none, because this title carries no runtime capture, so no "
              "row here is credited by one.", "",
              "## Instruction bytes", "",
              "The walk marks %d B of instructions: %d B proven, %d B filtered, %d B table-held. "
              "The closed bounds hold %d B, which is less because a bound stops at the next "
              "start or at the first halfword the CPU cannot execute."
              % (sum(end - begin for begin, end in class_spans(measured, PROVEN))
                 + sum(end - begin for begin, end in class_spans(measured, FILTERED))
                 + sum(end - begin for begin, end in class_spans(measured, TABLE)),
                 sum(end - begin for begin, end in class_spans(measured, PROVEN)),
                 sum(end - begin for begin, end in class_spans(measured, FILTERED)),
                 sum(end - begin for begin, end in class_spans(measured, TABLE)),
                 result["proven_bytes"]), "",
              "## The image's byte classes", "",
              "| class | bytes | share |", "| --- | --- | --- |"]
    for name in ("proven code", "filtered pointer-entry code", "table-held code", "literal pool",
                 "unclassified"):
        lines.append("| %s | %d | %.4f %% |"
                     % (name, class_bytes[name], 100.0 * class_bytes[name] / total))
    lines += ["", "## Code-shaped remainder", "",
              "%d B outside every closed bound: %d B padding, %d B decodable runs of %d or more "
              "Thumb halfwords, %d B neither (%d extents)."
              % (remainder_result["bytes"], remainder_result["padding"],
                 remainder_result["shaped"], RUN, remainder_result["unshaped"],
                 len(remainder_result["leftover"])), "",
              "The same decodable-run rule over the same bytes of a pair-permuted image gives "
              "%d B, %.4f %% of the %d B class, so the class is %s."
              % (remainder_result["null_shaped"], remainder_result["null_share"],
                 remainder_result["shaped"],
                 "a chance shape" if remainder_result["null_share"] >= 100.0
                 else "above its null"), ""]
    return "\n".join(lines)


def class_spans(measured, value):
    return [(begin, stop) for begin, stop in class_runs(measured["classes"], value)]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", default=ROM)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--starts", action="store_true")
    arguments = parser.parse_args(argv)
    if not os.path.exists(arguments.rom):
        print("the census needs the retail image at %s" % arguments.rom)
        return 1
    rom = open(arguments.rom, "rb").read()
    result = census_result(rom)
    table = remainder(rom, result)
    rows_out = rows(result)
    ends = result["ends"]
    open_bounds = [address for address in ends if not ends[address][0]]
    if arguments.starts:
        for address, kind, channel, mode, end, reason, flags, evidence in rows_out:
            print("0x%08x %-8s %-24s %-5s %-10s %-10s %-20s %s"
                  % (address, kind, channel, mode, "0x%08x" % end if end else "-", reason,
                     flags or "-", evidence))
    counts = channel_text(result)
    print("channels " + " ".join("%s=%d" % (name, counts.get(name, 0))
                                 for name in CHANNEL_PRIORITY))
    print("starts=%d closed=%d open=%d fragments=%d"
          % (len(result["starts"]), len(ends) - len(open_bounds), len(open_bounds),
             len(result["fragments"])))
    print("by_reason " + " ".join("%s=%d" % (reason, len([1 for address in ends
                                                          if ends[address][1] == reason]))
                                  for reason in REASONS))
    print("flagged " + " ".join("%s=%d" % (flag, len([1 for address in result["flags"]
                                                     if flag in result["flags"][address]]))
                                for flag in FLAGS))
    print("proven=%d B remainder=%d B padding=%d shaped=%d unshaped=%d"
          % (result["proven_bytes"], table["bytes"], table["padding"], table["shaped"],
             table["unshaped"]))
    print("shaped_null=%d B %.4f %% of the class" % (table["null_shaped"], table["null_share"]))
    body = text(rows_out)
    page = doc_text(result, table)
    if arguments.write:
        for path, payload in ((EVIDENCE, body), (DOC, page)):
            directory = os.path.dirname(path)
            if not os.path.isdir(directory):
                os.makedirs(directory)
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
            print("wrote %s" % os.path.relpath(path, ROOT).replace("\\", "/"))
        return 0
    if arguments.check:
        for path, payload in ((EVIDENCE, body), (DOC, page)):
            current = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            if current != payload:
                print("CENSUS FAIL: %s is not what the image gives"
                      % os.path.relpath(path, ROOT).replace("\\", "/"))
                return 1
        print("CENSUS PASS")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
