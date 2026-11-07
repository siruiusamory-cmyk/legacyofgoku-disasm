from __future__ import annotations

import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "code"))

import dialogue_rows
import emit_code

ROM = dialogue_rows.ROM
ROM_BASE = dialogue_rows.ROM_BASE
ROM_SIZE = dialogue_rows.ROM_SIZE
GAME_CODE = dialogue_rows.GAME_CODE

STATES = 0x0800EF28
STATE_SLOTS = 8
STATE_TARGETS = (0x0800F330, 0x0800F354, 0x08005380, 0x08005B38,
                 0x0800F3AC, 0x0800F39C, 0x0800538A, 0x08005392)
PAGE = 0x02029D94
PAGE_STRIDE = 0x824
PAGES = 4
PAGE_BASE_LITERAL = 0x080053B8
SHADOW = 0x0202BE24
STAGING = 0x0200B024
CONTEXT = 0x03000794
CONTEXT_LITERAL = 0x080028DC
CURSOR_LITERAL = 0x080028E4
OBJ_LITERAL = 0x080028E8
STAGING_LITERAL = 0x080028EC
MATRIX_PADS = ((0x0800989E, 0x06, "r2, [r0, #0x6]"), (0x080098A2, 0x0E, "r3, [r0, #0xE]"),
               (0x080098A0, 0x16, "r3, [r0, #0x16]"), (0x080098A8, 0x1E, "r2, [r0, #0x1E]"))
TERMINAL = dialogue_rows.TERMINATOR
SCENE = 66

CITED = (
    ("talk-index", 0x0800581C, "LDRB", "r0, [r4, #0x16]"),
    ("talk-call", 0x08005824, "BL", "|loc_080051D0|"),
    ("successor-read", 0x0800520C, "LDRB", "r0, [r4, #0x1]"),
    ("successor-store", 0x08005210, "STRB", "r0, [r1, #0x0]"),
    ("kind-read", 0x08005212, "LDRB", "r0, [r4, #0x0]"),
    ("terminal-test", 0x08005214, "CMP", "r0, #0xFF"),
    ("terminal-map", 0x0800521A, "BL", "|loc_08008D14|"),
    ("terminal-out", 0x08005220, "BL", "|loc_08008D8A|"),
    ("terminal-tail", 0x08005228, "BL", "|loc_08005478|"),
    ("node-text", 0x080052B2, "LDR", "r1, [r4, #0x4]"),
    ("node-push", 0x08005334, "BL", "|loc_080097F8|"),
    ("node-flush", 0x08005366, "BL", "|loc_08002896|"),
    ("node-next", 0x0800536A, "B", "|loc_08005202|"),
    ("install-text", 0x0800930C, "STR", "r1, [r0, #0x14]"),
    ("install-map", 0x08009310, "BL", "|loc_08008D14|"),
    ("install-counter", 0x08009316, "STRB", "r0, [r4, #0x1C]"),
    ("install-budget-top", 0x0800931A, "LDRSH", "r1, [r4, r3]"),
    ("install-done", 0x0800931C, "STR", "r0, [r4, #0x20]"),
    ("install-budget-origin", 0x08009320, "LDRSH", "r0, [r4, r3]"),
    ("install-budget", 0x08009322, "SUB", "r0, r1, r0"),
    ("install-budget-store", 0x08009324, "STR", "r0, [r4, #0x18]"),
    ("wrapper-call", 0x0800539A, "BL", "|loc_08009328|"),
    ("wrapper-cursor", 0x0800539E, "LDR", "r1, [r4, #0x14]"),
    ("wrapper-flag", 0x080053A6, "MOV", "r0, #0x0"),
    ("driver-done", 0x0800932C, "LDR", "r0, [r0, #0x20]"),
    ("driver-cursor", 0x08009350, "LDR", "r0, [r4, #0x14]"),
    ("driver-byte", 0x08009358, "LDRB", "r0, [r0, #0x0]"),
    ("driver-byte-test", 0x0800935A, "CMP", "r0, #0x0"),
    ("driver-press-clear", 0x08009360, "STRH", "r7, [r6, #0x0]"),
    ("driver-cursor-zero", 0x08009364, "STR", "r7, [r4, #0x14]"),
    ("runner-leave", 0x08009810, "LDR", "r2, [r1, #0x4]"),
    ("runner-enter", 0x0800981C, "LDR", "r2, [r1, #0x0]"),
    ("runner-current", 0x08009824, "STR", "r6, [r4, #0x4]"),
    ("runner-step", 0x0800982C, "LDR", "r2, [r1, #0x8]"),
    ("runner-poll", 0x0800983E, "BL", "|loc_0800A664|"),
    ("runner-body", 0x08009846, "LDR", "r2, [r1, #0xC]"),
    ("runner-test", 0x0800984E, "CMP", "r0, #0x0"),
    ("runner-loop", 0x08009850, "BEQ", "|loc_08009828|"),
    ("runner-exit", 0x08009856, "LDR", "r2, [r1, #0x4]"),
    ("map-fill", 0x08008D14, "LDRB", "r1, [r0, #0x0]"),
    ("pen-column", 0x08008D32, "STRH", "r1, [r0, #0xA]"),
    ("pen-row", 0x08008D36, "STRH", "r1, [r0, #0xC]"),
    ("map-dest", 0x08008D40, "STR", "r1, [r4, #0x10]"),
    ("origin-column", 0x08008D4C, "STRH", "r2, [r4, #0x2]"),
    ("origin-row", 0x08008D52, "STRH", "r2, [r4, #0x4]"),
    ("max-column", 0x08008D56, "STRH", "r2, [r4, #0x6]"),
    ("max-row", 0x08008D5C, "STRH", "r2, [r4, #0x8]"),
    ("map-out", 0x08008D92, "STR", "r2, [r0, #0x0]"),
    ("ctx-literal", 0x0800289C, "LDR", "r1, [pc, #0x3C]"),
    ("cursor-negated", 0x0800289E, "LDR", "r2, [pc, #0x44]"),
    ("ctx-back", 0x080028A0, "SUB", "r1, #0xC"),
    ("staged", 0x080028A2, "LDR", "r0, [r1, #0x4]"),
    ("span", 0x080028A4, "ADD", "r0, r0, r2"),
    ("base-tile", 0x080028A8, "LDRH", "r1, [r1, #0xA]"),
    ("obj-base", 0x080028AA, "LDR", "r2, [pc, #0x3C]"),
    ("tile-shift", 0x080028AE, "LSL", "r1, r1, #0x5"),
    ("dad", 0x080028B0, "ADD", "r2, r1, r2"),
    ("sad", 0x080028B4, "STR", "r3, [r1, #0x0]"),
    ("count", 0x080028B8, "LSR", "r0, r0, #0x2"),
    ("control", 0x080028BC, "MOV", "r0, #0x21"),
    ("control-hi", 0x080028C0, "STRH", "r0, [r1, #0xA]"),
    ("rebuild-head", 0x08002556, "PUSH", "{r4, r5, r6, r7, lr}"),
    ("rebuild-clear", 0x0800255E, "BL", "|loc_080098DE|"),
    ("rebuild-entry", 0x0800256C, "STRH", "r4, [r0, #0x0]"),
    ("rebuild-staging", 0x08002570, "STR", "r1, [r0, #0x4]"),
    ("identity-stride", 0x0800989A, "LSL", "r0, r1, #0x5"),
    ("identity-pa", 0x0800989E, "STRH", "r2, [r0, #0x6]"),
    ("identity-pc", 0x080098A0, "STRH", "r3, [r0, #0x16]"),
    ("identity-pb", 0x080098A2, "STRH", "r3, [r0, #0xE]"),
    ("identity-pd", 0x080098A8, "STRH", "r2, [r0, #0x1E]"),
    ("identity-groups", 0x080098A6, "CMP", "r1, #0x20"),
    ("identity-entry", 0x080098B6, "STRH", "r1, [r2, #0x0]"),
    ("identity-entries", 0x080098BC, "CMP", "r0, #0x80"),
    ("shadow-copy", 0x080098CA, "STR", "r1, [r0, #0x0]"),
    ("shadow-clear", 0x080098E6, "STR", "r1, [r0, #0x0]"),
    ("shadow-clear-count", 0x080098EC, "LSR", "r1, r0, #0x12"),
    ("shadow-clear-control", 0x080098F0, "MOV", "r1, #0x85"),
    ("entry-x", 0x0800516E, "LSR", "r4, r4, #0x16"),
    ("entry-old-word1", 0x08005168, "LDR", "r5, [r2, #0x4]"),
    ("entry-palette", 0x0800517C, "LSL", "r7, r7, #0xC"),
    ("entry-word0", 0x08005164, "STR", "r3, [r2, #0x0]"),
    ("entry-word0-tail", 0x080051A2, "STR", "r0, [r2, #0x0]"),
    ("entry-word1", 0x08005176, "STR", "r4, [r2, #0x4]"),
    ("entry-word1-palette", 0x08005186, "STR", "r4, [r2, #0x4]"),
    ("entry-cursor", 0x08005138, "STRH", "r3, [r1, #0x0]"),
    ("staging-cursor", 0x080051A8, "STR", "r0, [r1, #0x4]"),
    ("tile-cursor", 0x080051AE, "STRH", "r0, [r1, #0x2]"),
    ("map-cell", 0x08008D90, "ADD", "r2, #0x24"),
    ("map-out-dad", 0x08008D94, "STR", "r1, [r0, #0x4]"),
    ("bank-write", 0x08008D42, "STRB", "r3, [r4, #0x0]"),
    ("shadow-clear-head", 0x080098DE, "MOV", "r0, #0x0"),
)


def word(image, address):
    return int.from_bytes(image[address - ROM_BASE:address - ROM_BASE + 4], "little")


def cited(image):
    seen = {}
    for role, address, mnemonic, text in CITED:
        found = emit_code.decode(image, address, "thumb")
        if found is None or found[:2] != (mnemonic, text):
            raise ValueError("the code at 0x%08X is %r, not %s %s"
                             % (address, found, mnemonic, text))
        seen[role] = address
    return seen


def problem(image):
    if len(image) != ROM_SIZE:
        return "the image is %d B, not %d B" % (len(image), ROM_SIZE)
    if image[0xAC:0xB0] != GAME_CODE:
        return "the image carries game code %r, not %r" % (image[0xAC:0xB0], GAME_CODE)
    expected = open(dialogue_rows.SHA1, encoding="ascii").read().strip().lower()
    measured = hashlib.sha1(image).hexdigest()
    if measured != expected:
        return "the image's sha1 %s is not baserom.sha1's %s" % (measured, expected)
    return None


def page_bases(image):
    base = word(image, PAGE_BASE_LITERAL)
    if base != PAGE:
        raise ValueError("the page literal at 0x%08X is 0x%08X, not 0x%08X"
                         % (PAGE_BASE_LITERAL, base, PAGE))
    seen = []
    for index in range(PAGES):
        address = base + PAGE_STRIDE * index
        if image.find(address.to_bytes(4, "little")) < 0:
            raise ValueError("the page at 0x%08X is named by no literal" % address)
        seen.append(address)
    return seen


def staging(image):
    context = word(image, CONTEXT_LITERAL) - 0xC
    if context != CONTEXT:
        raise ValueError("the flush derives context 0x%08X, not 0x%08X" % (context, CONTEXT))
    negated = word(image, CURSOR_LITERAL)
    obj = word(image, OBJ_LITERAL)
    base = word(image, STAGING_LITERAL)
    if negated != (0 - base) & 0xFFFFFFFF:
        raise ValueError("the flush's subtrahend 0x%08X is not minus the staging base 0x%08X"
                         % (negated, base))
    if obj != 0x06010000:
        raise ValueError("the object base is 0x%08X, not 0x06010000" % obj)
    if image.count(base.to_bytes(4, "little")) != 2:
        raise ValueError("the staging base 0x%08X is named by %d words, not 2"
                         % (base, image.count(base.to_bytes(4, "little"))))
    return {"context": context, "base": base, "obj": obj}


def matrices(image):
    if word(image, 0x0800993C) != SHADOW or word(image, 0x08009944) != 0x030047EC:
        raise ValueError("the shadow or scratch literal is not the one the copies use")
    offsets = []
    for address, offset, expected in MATRIX_PADS:
        found = emit_code.decode(image, address, "thumb")
        if found != ("STRH", expected, 2):
            raise ValueError("the matrix store at 0x%08X is %r, not STRH %s"
                             % (address, found, expected))
        offsets.append(offset)
    return tuple(offsets)


def states(image):
    derived = []
    for index in range(STATE_SLOTS):
        address = STATES + 4 * index
        offset = word(image, address)
        signed = offset - 0x100000000 if offset >= 0x80000000 else offset
        target = (STATES + signed) & 0xFFFFFFFE
        if emit_code.decode(image, target, "thumb") is None:
            raise ValueError("the state slot at 0x%08X names 0x%08X, which decodes to nothing"
                             % (address, target))
        derived.append(target)
    if tuple(derived) != STATE_TARGETS:
        raise ValueError("the state slots name %s, not %s"
                         % (" ".join("0x%08X" % row for row in derived),
                            " ".join("0x%08X" % row for row in STATE_TARGETS)))
    return tuple(derived)


def scene(image):
    table = [word(image, dialogue_rows.BASE + dialogue_rows.STRIDE * index)
             for index in range(dialogue_rows.ROWS)]
    base = table[SCENE]
    order = sorted(table).index(base)
    stop = sorted(table)[order + 1]
    nodes, _text = dialogue_rows.nodes_of(image, base, stop)
    terminals = [index for index, (kind, _next, _pointer) in enumerate(nodes) if kind == TERMINAL]
    for index in terminals:
        if nodes[index][2] is not None:
            raise ValueError("the terminal at 0x%08X carries a text pointer" % (base + 8 * index))
    visited, at = [], 0
    while at not in visited:
        visited.append(at)
        at = nodes[at][1]
    return {"base": base, "nodes": len(nodes), "terminals": tuple(terminals),
            "cycle": at, "visited": tuple(visited), "last": tuple(
                index - 1 for index in terminals if index in visited)}


def measure(image):
    cited(image)
    problem_ = problem(image)
    if problem_:
        raise ValueError(problem_)
    dialogue = dialogue_rows.census(image)
    pages = page_bases(image)
    span = staging(image)
    pads = matrices(image)
    slots = states(image)
    scene_ = scene(image)
    if scene_["visited"] != tuple(range(len(scene_["visited"]))) or \
            (scene_["cycle"], len(scene_["visited"]) - scene_["cycle"]) != (8, 3) or \
            scene_["last"] != (6, 9):
        raise ValueError("record %d's chain is %s from %d, not 0..10 from 8"
                         % (SCENE, scene_["visited"], scene_["cycle"]))
    return {"cites": len(CITED), "records": dialogue["records"],
            "nodes": dialogue["nodes"], "pages": len(pages), "stride": PAGE_STRIDE,
            "staging": span["base"], "slots": len(slots), "pads": pads,
            "terminals": scene_["terminals"], "scene": SCENE}


def summary(measured):
    return ("cites=%d records=%d nodes=%d pages=%d stride=0x%X staging=0x%08X "
            "slots=%d pads=%s terminals=%s scene=%d"
            % (measured["cites"], measured["records"], measured["nodes"], measured["pages"],
               measured["stride"], measured["staging"], measured["slots"],
               ",".join("0x%02X" % pad for pad in measured["pads"]),
               ",".join(str(index) for index in measured["terminals"]), measured["scene"]))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in ([], ["--check"]):
        print("usage: python tools\\research\\dialogue_runtime.py [--check]")
        return 2
    if not os.path.exists(ROM):
        print("the runtime reader needs the retail image at %s" % ROM)
        return 1
    try:
        print(summary(measure(open(ROM, "rb").read())))
    except ValueError as error:
        print("RUNTIME FAIL: %s" % error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
