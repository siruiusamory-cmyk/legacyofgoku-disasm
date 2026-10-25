<!-- TODO demo GIF: a short capture of extract.cmd, rebuild.cmd and the gate printing GATE PASS, saved as docs/demo.gif and placed under the tagline. -->
<!-- TODO social preview: set the repository social image in Settings once the banner exists. -->
<p align="center"><img src="docs/banner.png" alt="Dragon Ball Z: The Legacy of Goku" width="900"></p>

# Dragon Ball Z: The Legacy of Goku disassembly

**A byte-exact disassembly of Dragon Ball Z: The Legacy of Goku (GBA, USA) that rebuilds the original ROM from tracked source.**

![License](https://img.shields.io/badge/license-MPL--2.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-Game%20Boy%20Advance-lightgrey.svg)
![Code starts](https://img.shields.io/badge/code%20starts-2010-blueviolet.svg)

## Contents

- [What this is](#what-this-is)
- [What this is not](#what-this-is-not)
- [Progress](#progress)
- [Building](#building)
- [Reading and changing a function](#reading-and-changing-a-function)
- [Tests](#tests)
- [Repository layout](#repository-layout)
- [Credits and license](#credits-and-license)

## What this is

The startup block is ARM assembly. ARM Developer Suite 1.2 assembles and links it back into the
retail ROM, and the gate compares the result with the retail sha256. Every start the census proves is
code is disassembled to Thumb or ARM assembly as well, and the rest of the image is carried as
slices of the retail image, so the gate's count names every byte of it.

It builds one ROM:

* Dragon Ball Z: The Legacy of Goku (USA), sha1 `a3c8c76742f11fc6a3f6e3fcca20992458cac0b5`

## What this is not

This is not a decompilation. The build compiles no C: the census's code rows are disassembled to
assembly, the data rows and the residual image stay slices, and no function has a name yet. A start
is where a static channel names the address, not a prologue this tree proves, so no function
boundary is claimed either. Naming or joining one takes evidence, never a guess.

The progress figure below measures how much of the ROM the build produces from tracked source. It
does not measure how much of the code has been turned into C.

## Progress

59.9904 % of the ROM (5,032,358 of 8,388,608 bytes) builds from tracked source: the startup block
at `0x080000c0` in [asm/crt0.s](asm/crt0.s), every census code row, disassembled into `build/code/`
by [tools/code/emit_code.py](tools/code/emit_code.py), all 532 records of the three lists the
custom decompressor serves, decoded into rows, token plans, a palette and an image stream and
re-encoded by [tools/compress/f1_streams.py](tools/compress/f1_streams.py), the 157 BIOS
codec streams the image names - one LZ77 and 156 Huffman - decoded and re-encoded by
[tools/compress/bios_streams.py](tools/compress/bios_streams.py), the 282 script records the
interpreter at `0x0800a3e6` runs, decoded to 50,087 opcodes and re-encoded by
[tools/scripts/script_streams.py](tools/scripts/script_streams.py), and the 35 actor stat rows at
`0x086b6094` with the name pool their `+4` fields point at, read from the image at build time under
the layout their reader's offsets give and re-encoded by
[tools/research/actor_rows.py](tools/research/actor_rows.py), and the 142-line credits table at
`0x08010094` with the text pool its entries point at, re-encoded by
[tools/research/credits_rows.py](tools/research/credits_rows.py), and the 80-record dialogue table at
`0x0815bf28` with the node chains and text pools its pointers name, re-encoded by
[tools/research/dialogue_rows.py](tools/research/dialogue_rows.py), and the six messages the code
names one by one at `0x085c2de2` with the 31-row message-id table and its 14-string pool at
`0x085c2fb8`, re-encoded by [tools/research/message_rows.py](tools/research/message_rows.py), and
the 14 runs of four or more image-addressed words whose every word names a label the code files
already carry, emitted as `DCD` lines naming that label by
[tools/research/pointer_rows.py](tools/research/pointer_rows.py), and the three text tables whose
rows tile into their own string pools - 109 rows at `0x080109f0`, 17 rows at `0x08010ec4` and the
24-word table at `0x081c6224` that the reader at `0x08001830` scales by eight - re-encoded by
[tools/research/text_rows.py](tools/research/text_rows.py). The
rest is INCBIN
slices of the retail image. Inside the noise-like family the generated runs leave 141,821 B that no
byte-exact stream reaches - among them three streams whose Huffman tree shares a node, refused at
`+356` and `+516` - and the 544 B of art tables that two literal loads name at `0x08011ba8` and
`0x08011da8`; both stay raw, as do three run-length streams of 1,319 B whose codec this tree does not
encode. `python tools\gate\gate.py` prints the split, and the code and data classes it derives
are the page [docs/CODE_SPLIT.md](docs/CODE_SPLIT.md), which `tools/split/census.py --check`
re-derives.

## Building

You need ARM Developer Suite 1.2, Python 3.12, Visual Studio 2022 or Build Tools with the C++
workload, and your own copy of the game saved as `baserom.gba`. [INSTALL.md](INSTALL.md) has the
details. The build compiles the jcalg1 compressor from the vendored source when it is absent, so no
compiled copy of it is distributed here.

```
extract.cmd
rebuild.cmd
python tools\gate\gate.py
```

The gate rebuilds from scratch and prints `DIGEST MATCH` and `GATE PASS` when the output equals the
retail ROM.

## Reading and changing a function

1. Find the start in [tools/code/CENSUS_EVIDENCE.csv](tools/code/CENSUS_EVIDENCE.csv). It carries one
   row per start, with the end the walk reached, the Thumb or ARM mode, the channel that found the
   address and the entry flags. [docs/CODE_SPLIT.md](docs/CODE_SPLIT.md) counts them by channel and
   by reason, and `tools/split/census.py --check` re-derives it. The startup block is the one start
   written by hand, in [asm/crt0.s](asm/crt0.s).
2. Read its file. Every code row becomes one file, `build\code\code_<address>.s`, which
   [asm/remainder.s](asm/remainder.s) includes at the address the row starts on; a branch target
   inside it carries a `loc_<address>` label. The file is generated at build time, so read it after
   `rebuild.cmd` has run.
3. Changing what a start does means changing what it is generated from: the instructions are decoded
   from the retail image by [tools/code/emit_code.py](tools/code/emit_code.py) from the bounds in the
   census, so the change that keeps is to the decoder, to the census row or to the hand transcription
   in `asm/crt0.s`.
4. Any such change has one proof: `rebuild.cmd`, then `python tools\gate\gate.py`, which must still
   print `DIGEST MATCH` and `GATE PASS`. The gate purges every object first, so a rebuild that did
   not really happen cannot pass as one.

## Tests

`check.cmd` runs the link check, the source checks and every test file, one file per process; its
test step needs the runner CI installs, `python -m pip install pytest`. The CI workflow at
[.github/workflows/check.yml](.github/workflows/check.yml) runs the same link check and source
checks, and then the whole suite one file per process. A test that needs the retail image skips while
`baserom.gba` is absent, which is what CI runs.

## Repository layout

| Path | Contents |
| --- | --- |
| `asm/` | the assembly the image is built from: the transcribed startup block, the equates, the include list and the generated remainder |
| `tools/` | the gate, the source checks, the slice writer, the census, the emitter, the recompiler input, the compressor and the tests; `tools/README.md` says what runs each one |
| `docs/` | the reader guide; `docs/README.md` says where to start |
| `build/` | the objects, the generated assembly files and the image; never tracked |
| `work/` | the rebuild log the gate writes; never tracked |

## Credits and license

The gate, the source checks, the link check, the slice writer and the build scripts start from the
[2genkidev/buusfury](https://github.com/2genkidev/buusfury) disassembly. Third-party code and
credits are listed in [NOTICE](NOTICE). Changes are listed in [CHANGELOG.md](CHANGELOG.md).

No ROM, BIOS or extracted game data is included. You need your own legally obtained copy of the
game. Not affiliated with the rights holders of the game.

MPL-2.0, see [LICENSE](LICENSE).
