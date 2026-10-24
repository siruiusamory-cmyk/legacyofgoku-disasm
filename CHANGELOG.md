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
