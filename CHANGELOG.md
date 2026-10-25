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
- The same channel fed from four routes: a 10,800-frame no-input attract run, a 13,782-frame boot
  run (title, new game, the opening cards, the first field with a walk in four directions, the pause
  menu opened and closed through Exit), a 3,701-frame mid-fight traversal from a savestate, and a
  6,089-frame seeded fuzz from the same savestate. The three gameplay runs recorded 495 distinct
  dispatch entries; 210 of them were not yet tracked and the census admits them, so
  `RUNTIME_LABELS.csv` carries 492 rows, the evidence table 2,010 starts, `RECOMP_INPUTS.toml`
  2,010 rows and 45.7603 % of the image builds from source. Three recorded entries are refused
  because the walk finds them inside an instruction rather than on a boundary.
  `RUNTIME_LABELS_RUNS.csv` carries one provenance row per run; its `entries` column counts the
  labels that run added, so the rows sum to the file.
- A start a bounded run entered is not flagged `data`: the flag is a shape test on the leading
  instructions and a dispatch entry measures the same question directly, so `0x08004d5c` and
  `0x08008016` - both Thumb code whose own frame save follows a three-instruction setup - are
  emitted as code rows of 46 B and 50 B instead of staying raw. A crafted-start test covers the
  rule, and the image's own census is asserted to carry no `data` flag on a recorded start.
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
- The Huffman tree grammar the BIOS decoder at `0x00001014` implements, and the ten image streams it
  reads of the eleven the code hands to SWI `0x13`: byte 0 is `0x24` (four-bit units) or `0x28`
  (eight-bit), bytes 1-3 the decoded size, byte 4 one less than the tree's leaf count, then the
  compacted tree - one byte per node, bits 7 and 6 the "this child is a leaf" flags for bit 0 and bit
  1, bits 0-5 the distance in node pairs to the child pair, and a leaf byte carrying the symbol - and
  then the bitstream as little-endian words consumed from bit 31 down. The ten streams decode to
  116,732 B and re-encode to their 100,540 stored bytes exactly, so those 100,540 B are source. The
  eleventh stream, at `0x0818a3a8`, is refused: its tree shares twenty nodes, so a symbol has more
  than one code and no encoder can rebuild its bitstream from the decoded bytes.
  `tools/compress/test_bios_streams.py` pins the eleven-row population, the naming word of each
  stream, the nine descriptor ends that agree with the decoder's own stop, a permuted LZ77 body, a
  permuted tree and the shared-node refusal.
- The generator for the script records the interpreter at `0x0800a3e6` runs, in
  `tools/scripts/script_streams.py`: the table at `0x08591f3c` holds twelve-byte descriptors, the map
  loader at `0x08002038` addresses a row with the byte at `[record+0]`, and a row carries a word
  table of record starts and a `0xff`-terminated selector table. A record is one frame-count byte and
  that many `0x00`-terminated opcode segments, and an opcode's operand count is its flag byte: read
  from the stream when the opcode's high nibble is zero, inherited from the same slot when it is one,
  and taken from the image's own table at `0x08142386` above that. The 282 records over 118,634 B
  decode to 17,332 segments and 50,087 opcodes and re-encode byte for byte, so those bytes are source,
  and `asm/remainder.s` carries their eighteen generated runs. The rows are the tracked tables
  `tools/scripts/SCRIPT_RECORDS.csv` and `tools/scripts/SCRIPT_OPS.csv`; `--check` re-derives both,
  and `tools/scripts/test_script_streams.py` pins the population, every row's tiling, the flag bytes,
  a table whose slots are permuted (no record passes) and a doctored operand.
- The generator for the actor stat table, in `tools/research/actor_rows.py`: the spawn initialiser at
  `0x08006d90` refuses an index above `0x22` (`cmp r2,#0x22` at `0x08006da0`), scales it by `0x40`
  (`lsls r2,#6` at `0x08006e6a`) and adds the base `0x086b6094` (literal at `0x08007188`), so the
  table is 35 rows of 64 bytes. A row carries its index at `+0`, a name pointer at `+4`, a class
  halfword at `+8`, a counter word at `+0xc`, four halfwords from `+0x10`, eleven signed halfwords
  from `+0x18`, and the EP, HP and damage words at `+0x34`, `+0x38` and `+0x3c`. The next structure
  the code names begins at `0x086b6a78` (loaded at `0x0800481c`), which bounds the family at 2,532 B
  with the name pool the `+4` fields point at. Nothing read from the image is tracked: the layout,
  the bounds and the instructions that cite them are the committed part, and the generator reads the
  rows and the pool out of the builder's image at build time, refuses an image whose bounds, digest
  or round trip differ, and writes the family to `build/actors/`, which `asm/remainder.s` incbins in
  place of the raw slice. `--check` re-derives the run and the slices, and
  `tools/research/test_actor_rows.py` pins the bounds, the round trip, the first-use rule for every
  name pointer, the pool walk, a table advanced by one row (no row passes), the rotation that is not
  a null because each row carries its own index, a doctored HP word (exactly one row disagrees), and
  the refusals of a name pointer outside the pool, a moved base literal and an image whose sha1
  differs.
