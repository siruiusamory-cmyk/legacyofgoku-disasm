# Changelog

All notable changes to this tree are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

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
