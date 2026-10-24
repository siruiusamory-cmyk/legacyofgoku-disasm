# Build

Prerequisites: ARM Developer Suite 1.2 (`armasm`, `armlink`, `fromelf`), Python 3.12 on `PATH`,
Visual Studio 2022 or Build Tools with the C++ workload, `pytest` for the test files
(`python -m pip install pytest`), and the retail ROM as `baserom.gba` in
this directory. `rebuild.cmd` defaults `ADS` to an ADS 1.2 Build 805 install beside this checkout's
parent directory; set `ADS` to use another installation. The ROM's sha1 must equal `baserom.sha1`
and its game code must read `ALGE`; `extract.cmd` refuses anything else.

```
extract.cmd
rebuild.cmd
python tools\gate\gate.py
```

`gate.py` rebuilds from scratch, purges every object first, and prints `DIGEST MATCH` and
`GATE PASS` when the image equals the retail sha256. It also accounts for every byte of the image
from the source tree:

```
source=<bytes> of 8388608 (<percent>)      code generated from tracked source or transcribed
raw-data=<bytes> (<percent>)               bytes the assembler embeds from extracted slices
identity copies=<bytes> (<percent>)        bytes copied through a build step
accounted=<bytes> of 8388608 (<percent>)   source plus raw-data; all of it when every byte is in one
```

`source` is the image size minus the bytes `asm/*.s` INCBINs, so it cannot drift from what the
assembler reads. `rebuild.cmd` writes both slices through `tools\incbin.bat`, whose writer is
`tools\extract\slice_rom.py`; neither the slices nor the image is tracked.

`python tools\gate\gate.py --cold` purges every object, every INCBIN slice and the built image, runs
`extract.cmd`, rebuilds, and requires the digest match from that empty start.

`python tools\gate\gate.py --verify-rom` checks the retail file only: its size, its sha1 against
`baserom.sha1`, and the game code at `0x0AC`. `extract.cmd` runs it first.

The source checks are in `tools/lint/lints.py` and the link check in `tools/check_links.py`;
`check.cmd` runs both and one test file at a time, and the CI workflow runs the same checks plus the
whole suite, one file per process. The tests are `python -m pytest tools`, one file per process,
with the retail image present; the ROM-gated tests skip while it is absent, which is what CI runs.

`rebuild.cmd` builds `tools/compress/compress.exe` from the jcalg1 source under
`tools/compress/jcalg1/` with `tools/compress/build.cmd` when the binary is absent; no compiled copy
of the compressor is tracked. No container in this image is re-encoded yet, so the compressor exists
for the containers a later ticket establishes.

The build is byte sensitive: `asm/crt0.s` carries transcribed instructions and the rest of the image
is a slice, so a change there moves the digest. The gate is the only proof that a change kept the
image equal.

[docs/READABILITY.md](docs/READABILITY.md) measures what a reader still meets in this tree and which
counts a commit may not raise.
