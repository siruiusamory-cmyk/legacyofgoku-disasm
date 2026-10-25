# Changelog

All notable changes to this tree are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `docs/banner.png`, shown centred at the top of the README.
- The repository layout, `extract.cmd`, `rebuild.cmd` and `scatter.ld` for the retail image.
- The retail identity gate, the byte accounting and the citation tests in `tools/gate/gate.py`.
- The startup block at `0x080000c0` transcribed in `asm/crt0.s`, its equates, and one INCBIN slice
  for the rest of the image.
- The source checks and the two ratchets in `tools/lint/lints.py`.
- The link check, the slice writer and the vendored JCALG1 compressor.
- The CI workflow and `check.cmd`.
- The code and data census in `tools/split/census.py`: every start seeded from a static pointer
  channel, a walked end for each, the entry flags, the remainder classes and their null; its
  evidence table, its page and the gate rule that refuses an open bound.
- The code emitter in `tools/code/emit_code.py`: every census code row is disassembled to Thumb or
  ARM assembly in the mode the census records, the data rows and the residual image stay INCBIN
  slices, and the gate refuses an uncovered or modeless code row.
- `README.md` follows the house layout: one section per area with a Contents entry for each, a
  license, platform and code-start badge row that states nothing by colour, a comment in place of the
  banner, the demo GIF and the social preview until each exists, and a progress figure and start
  count the lint compares with the gate and the census. `INSTALL.md` names the test runner its
  `check.cmd` step needs.
- The remainder's decision in `tools/split/census.py`: every byte outside a closed bound carries
  one class and its reason, each channel that claims those bytes is measured on the proven code and
  against a pair-permuted null at a 5 % bar, and a body walk that reaches the 0x400 B cap now ends
  at its measured stop instead.
- A start whose Thumb body carries a halfword with an empty register list is flagged `data`: no
  assembler emits that encoding and no ARMv4T core executes it as code, so the row's bytes stay raw
  instead of being assembled. `0x086cfe88` is the one row on this image.
- The census refuses a seed that falls inside an instruction of a row in the other mode, and a
  copy-seeded ARM start whose save is its own frame save is not flagged `data`: `0x080001f2` stops
  being a start, `0x08000138` becomes an ARM code row, and the interrupt handler the startup copies
  to IWRAM is emitted as code.
- The static recompiler input in `tools/recomp/`: one row per census start with its closed bound,
  mode and channel, the rows the emitter leaves raw with their reason, the image identity and the
  code copy the startup makes to IWRAM. `export_inputs.py --check` re-derives it, and the gate
  refuses a missing, duplicated or open row.
- A tracked runtime channel: `tools/code/RUNTIME_LABELS.csv` carries the 126 dispatch entries a
  bounded no-input run recorded, each admitted as a census start only where the walk also decodes it
  from an instruction boundary and closes it, and refused when it falls inside an instruction. The
  census and the recompiler input carry the rows as `runtime`, the page counts them, and
  `tools/recomp/runtime_labels.py --check` re-measures every label against the evidence table
  beside a null of the same labels displaced by one halfword.
- The stream population of the custom row decompressor in `tools/research/f1_population.py`: the
  header at `0x08337248` names 269 objects and its list at `0x083372c8` walks to `0x084dd59e`,
  1,729,239 B, every record's entries tiling its size; 268 of them are row streams that decode
  under the code's grammar to 21,424 rows and 1,654,598 written bytes, and the same walk over three
  permutations of the block finds no record. The tool also measures that the retail token plan is
  not a function of the decoded content: 576 of the block's 81,024 distinct pixel regions carry two
  or more token plans, so no encoder can rebuild the block's bytes from a decoded asset alone.
  `tools/research/test_f1_population.py` pins the census, the null, two refusals and the ambiguity
  count. No byte of this block is registered as source.
- The generator for the three lists the custom row decompressor serves, in
  `tools/compress/f1_streams.py`: each record is decoded into rows and token plans through the same
  grammar and re-encoded, and the run is emitted only where the re-encoding equals the retail bytes.
  The three lists hold 532 records over 3,557,038 B and every record re-encodes byte for byte, so all
  3,557,038 B are source. A type 12 entry is a row stream; a type 4 entry is a palette stream (u16
  group count, then per group a slot gap, a run count whose 0 reads as 256, and three bytes per
  entry) and a type 15 entry is an image stream (per row a run count, then per run a signed length:
  negative copies that many literal bytes, positive repeats one byte that many times), decoded the
  way the entry-type switch at `0x08004698` dispatches them.
  `--check` re-derives the token list, the generated runs and the slices around them, and
  `tools/compress/test_f1_streams.py` pins the three populations, the address list, the two other
  grammars on each first record, the round trip and the permuted-region null. `asm/remainder.s` now
  carries the six runs and the three retail slices between them.
- The generator for the one LZ77 stream the BIOS decoder is handed from the image, in
  `tools/compress/bios_streams.py`: the stream at `0x081bdc1c` decodes to 11,656 B and a greedy
  18-byte-window encoder re-encodes the 10,947 stored bytes exactly, so those 10,947 B are source.
  `tools/compress/test_bios_streams.py` pins the stream, its two lengths, the word that names it,
  the round trip and a permuted-body null.
