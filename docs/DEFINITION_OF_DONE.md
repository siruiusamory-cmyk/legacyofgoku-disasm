# Definition of done

One target for every change: the full image, as `python tools\gate\gate.py` measures it.

## What counts as source

- Code assembled or compiled from tracked source.
- A `DCD` line that names a label the tracked assembly already defines, resolved by the assembler.
- A tracked table of plain numbers whose rows have a named layout and a consumer or a structural
  proof. An unlabeled byte dump is not source.
- A byte-exact generator that re-encodes assets from the builder's own ROM at build time, with
  nothing from the ROM committed. An identity copy is not source.
- A uniform run of one byte value, `0x00` or `0xFF` and 32 B or longer, emitted as the assembler's own
  fill directive: the run's own bytes state its extent, and no ROM byte is tracked.

## The finish line

- 100 % of the 8,388,608 B image. A byte that cannot be reached is named irreducible, with its
  reason.

## Current gate output

```
generated=5006759
identity copies=0 (0.0000 %)
raw-data=2332412 (27.8045 %)
source=6056196 of 8388608 (72.1955 %)
accounted=8388608 of 8388608 (100.0000 %) raw 2332412 + identity 0 + source 6056196
fill=999155 bytes (11.9109 %) as directives
source-without-fill=5057041 of 8388608 (60.2846 %)
```

README.md carries the same figures; the README-numbers check in `tools/lint/lints.py` reads
README.md only, so this file is not linted for numbers.
