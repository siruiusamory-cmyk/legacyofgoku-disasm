# Reading this tree

Start here, then follow the one page that answers your question.

| Question | Page |
| --- | --- |
| How do I build the ROM? | [../INSTALL.md](../INSTALL.md) |
| What does the build produce, and what is still a slice of the retail image? | [../README.md](../README.md) |
| What runs each tool? | [../tools/README.md](../tools/README.md) |
| Which counts may a commit not raise? | [READABILITY.md](READABILITY.md) |
| Which bytes are the startup block, and what does it install? | [STARTUP.md](STARTUP.md) |
| Which bytes are code, where does each start end, and what is still unclassified? | [CODE_SPLIT.md](CODE_SPLIT.md) |
| What counts as source, and what is the finish line? | [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md) |

## What this tree claims

The tree rebuilds the retail image byte for byte, and it proves that by digest. That is the whole of
the claim at this stage.

The startup block at `0x080000c0` is transcribed ARM assembly in [../asm/crt0.s](../asm/crt0.s): it
sets the interrupt-mode stack, zeroes one halfword, sets the system-mode stack, installs the
interrupt vector `0x03007ffc` with `0x08000138` and tail-calls the Thumb entry `0x08000274`. Two
interrupt enable and disable helpers follow the startup's literal pool.

From `0x08000138` to the end of the image, every start the census proves is code is emitted as Thumb
or ARM assembly by [../tools/code/emit_code.py](../tools/code/emit_code.py), the three stream lists
the custom decompressor serves are decoded into rows and token plans and re-encoded by
[../tools/compress/f1_streams.py](../tools/compress/f1_streams.py), and every other byte is an
INCBIN slice that the gate prints as `raw-data`. No function in it is named and no function
boundary is claimed. The census's code rows must all be emitted and must all carry a mode: the gate
prints `EXPORT PASS uncovered=0 modeless=0` and refuses anything else.

Nothing in this tree is claimed to match the original compiler's C output, because no C is compiled.

## Conventions

- A table sits beside the reader that derives it and carries a `--check` that re-derives it. No
  table is copied from another title.
- `tools/compress/compress.exe` is built from the vendored source on first use and never tracked.
- `check.cmd` is the local subset of the CI checks: the link check, the lints and one test file at a
  time.
- The gate is the only proof that a change kept the image equal, and its own two cited tests are
  test files, not a second implementation of the count.
