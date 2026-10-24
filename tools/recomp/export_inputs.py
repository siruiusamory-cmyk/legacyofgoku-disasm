from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "code"))
sys.path.insert(0, os.path.join(ROOT, "tools", "split"))

import census
import emit_code

ROM = os.path.join(ROOT, "baserom.gba")
SHA1 = os.path.join(ROOT, "baserom.sha1")
OUT = os.path.join(ROOT, "tools", "recomp", "RECOMP_INPUTS.toml")
MODES = emit_code.MODES
VECTOR = census.VECTOR
ROW = re.compile(r"\[\[(code|raw)\]\]\naddr = 0x([0-9a-fA-F]{8})\nmode = \"([^\"]*)\"\n"
                 r"size = (\d+)\nend = 0x([0-9a-fA-F]{8})\norigin = \"([^\"]*)\""
                 r"(?:\nreason = \"([^\"]*)\")?")


def site(path):
    relative = os.path.relpath(path, ROOT)
    return path if relative.startswith("..") else relative.replace("\\", "/")


def identity(path=ROM, sha1_path=SHA1):
    if not os.path.exists(path):
        raise SystemExit("no image at %s, so the export cannot be derived" % path)
    data = open(path, "rb").read()
    digest = hashlib.sha1(data).hexdigest()
    expected = open(sha1_path, encoding="ascii").read().strip()
    if digest != expected:
        raise SystemExit("%s has sha1 %s, not the %s of %s"
                         % (path, digest, expected, sha1_path))
    return digest, hashlib.md5(data).hexdigest()


def raw_reason(row):
    if row["channel"] == "pool":
        return "pool"
    if "data" in row["flags"]:
        return "data"
    if row["kind"] != "start":
        return "kind"
    return "below-image"


def rows_of(rows):
    code = set(row["address"] for row in emit_code.code_rows(rows))
    out = []
    for row in rows:
        if row["end"] is None or row["end"] <= row["address"]:
            raise SystemExit("the census has no end for the start at 0x%08X, so the export "
                             "cannot close it" % row["address"])
        record = {"section": "code" if row["address"] in code else "raw",
                  "addr": row["address"], "mode": row["mode"],
                  "size": row["end"] - row["address"], "end": row["end"],
                  "origin": row["channel"]}
        if record["section"] == "raw":
            record["reason"] = raw_reason(row)
        out.append(record)
    return out


def text_of(records, sha1, md5, copies):
    code = [record for record in records if record["section"] == "code"]
    raw = [record for record in records if record["section"] == "raw"]
    lines = [
        "[counts]",
        "functions = %d" % len(code),
        "code_bytes = %d" % sum(record["size"] for record in code),
        "entries = 0",
        "jump_tables = 0",
        "code_copies = %d" % len(copies),
        "raw_rows = %d" % len(raw),
        "rows = %d" % len(records),
        "",
        "[identity]",
        'sha1 = "%s"' % sha1,
        'md5 = "%s"' % md5,
        "",
        "[program]",
        "entry_pc = 0x%08x" % VECTOR,
        "",
    ]
    for copy in copies:
        lines += [
            "[[code_copy]]",
            "runtime_start = 0x%08x" % copy["dest"],
            "source_start = 0x%08x" % copy["source"],
            "size = 0x%x" % copy["size"],
            "",
        ]
    for record in records:
        lines += [
            "[[%s]]" % record["section"],
            "addr = 0x%08x" % record["addr"],
            'mode = "%s"' % record["mode"],
            "size = %d" % record["size"],
            "end = 0x%08x" % record["end"],
            'origin = "%s"' % record["origin"],
        ]
        if "reason" in record:
            lines += ['reason = "%s"' % record["reason"]]
        lines += [""]
    return "\n".join(lines)


def render(rom=ROM, rows=None):
    rows = emit_code.census_rows() if rows is None else rows
    data = open(rom, "rb").read()
    sha1, md5 = identity(rom)
    if (census.word(data, VECTOR) & 0x0F000000) != 0x0A000000:
        raise SystemExit("the reset vector at 0x%08X is not an ARM branch: %08X"
                         % (VECTOR, census.word(data, VECTOR)))
    return text_of(rows_of(rows), sha1, md5, census.copy_descriptors(data))


def found_rows(text):
    return [{"section": match.group(1), "addr": int(match.group(2), 16),
             "mode": match.group(3), "size": int(match.group(4)),
             "end": int(match.group(5), 16), "origin": match.group(6),
             "reason": match.group(7)}
            for match in ROW.finditer(text)]


def audit(text, rows, path=OUT):
    name = site(path)
    found = found_rows(text)
    expected = dict((row["address"], row) for row in rows)
    seen, twice = set(), []
    for record in found:
        if record["addr"] in seen:
            twice.append(record["addr"])
        seen.add(record["addr"])
    if twice:
        return ["%s: %d row(s) repeat an address, the first 0x%08X"
                % (name, len(twice), twice[0])]
    opened = [record for record in found if record["end"] <= record["addr"]]
    if opened:
        return ["%s: the row at 0x%08X has an open bound (end 0x%08X)"
                % (name, opened[0]["addr"], opened[0]["end"])]
    short = [record for record in found if record["size"] != record["end"] - record["addr"]]
    if short:
        return ["%s: 0x%08X carries size %d and end 0x%08X, which is not its own bound"
                % (name, short[0]["addr"], short[0]["size"], short[0]["end"])]
    modeless = [record for record in found if record["mode"] not in MODES]
    if modeless:
        return ["%s: %d row(s) carry a mode outside %s, the first 0x%08X"
                % (name, len(modeless), ", ".join(MODES), modeless[0]["addr"])]
    missing = [row for row in rows if row["address"] not in seen]
    if missing:
        return ["%s: %d census start(s) have no row, the first 0x%08X"
                % (name, len(missing), missing[0]["address"])]
    extra = sorted(record["addr"] for record in found if record["addr"] not in expected)
    if extra:
        return ["%s: %d row(s) are not census starts, the first 0x%08X"
                % (name, len(extra), extra[0])]
    code_addresses = set(row["address"] for row in emit_code.code_rows(rows))
    for record in sorted(found, key=lambda item: item["addr"]):
        row = expected[record["addr"]]
        if record["end"] != row["end"]:
            return ["%s: 0x%08X ends at 0x%08X, and the census says 0x%08X"
                    % (name, record["addr"], record["end"], row["end"])]
        want = "code" if row["address"] in code_addresses else "raw"
        if record["section"] != want:
            return ["%s: 0x%08X is a %s row, and the emitter makes it %s"
                    % (name, record["addr"], record["section"], want)]
        if record["origin"] != row["channel"]:
            return ["%s: 0x%08X carries origin %s, and the census channel is %s"
                    % (name, record["addr"], record["origin"], row["channel"])]
        if want == "raw" and record["reason"] != raw_reason(row):
            return ["%s: 0x%08X carries reason %s, and the emitter leaves it raw as %s"
                    % (name, record["addr"], record["reason"], raw_reason(row))]
    return []


def check(path=OUT, rom=ROM):
    rows = emit_code.census_rows()
    if not os.path.exists(path):
        return "%s is absent, so there is no export to check" % site(path)
    text = open(path, encoding="ascii", newline="").read()
    problems = audit(text, rows, path)
    if problems:
        return problems[0]
    if not os.path.exists(rom):
        return "%s is absent, so the export cannot be re-derived" % rom
    if text != render(rom, rows):
        return "%s is not the export this tree derives" % site(path)
    return None


def counts(rows=None):
    rows = emit_code.census_rows() if rows is None else rows
    records = rows_of(rows)
    return {"code_rows": len([r for r in records if r["section"] == "code"]),
            "raw_rows": len([r for r in records if r["section"] == "raw"]),
            "rows": len(records)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--export", default=OUT)
    args = parser.parse_args(argv)
    rows = emit_code.census_rows()
    tally = counts(rows)
    for key in ("code_rows", "raw_rows", "rows"):
        print("%s = %d" % (key, tally[key]))
    if args.write:
        text = render(rows=rows)
        os.makedirs(os.path.dirname(args.export), exist_ok=True)
        with open(args.export, "w", encoding="ascii", newline="\n") as handle:
            handle.write(text)
        print("wrote %s (%d B)" % (site(args.export), len(text)))
        return 0
    problem = check(args.export)
    if problem:
        print("RECOMP FAIL %s" % problem)
        return 1
    print("RECOMP PASS rows=%d uncovered=0 modeless=0" % tally["rows"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
