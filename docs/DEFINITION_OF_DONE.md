# Definition of done

One target for every change: the full image, as `python tools\gate\gate.py` measures it.

## What counts as source

- Code assembled or compiled from tracked source.
- A `DCD` line that names a label the tracked assembly already defines, resolved by the assembler.
- A tracked table of plain numbers whose rows have a named layout and a consumer or a structural
  proof. An unlabeled byte dump is not source.
- A byte-exact generator that re-encodes assets from the builder's own ROM at build time, with
  nothing from the ROM committed. An identity copy is not source.

## The finish line

- 100 % of the 8,388,608 B image. A byte that cannot be reached is named irreducible, with its
  reason.

## Current gate output

```
generated=3835635
identity copies=0 (0.0000 %)
raw-data=4502691 (53.6763 %)
source=3885917 of 8388608 (46.3237 %)
accounted=8388608 of 8388608 (100.0000 %) raw 4502691 + identity 0 + source 3885917
```

README.md carries the same figures; the README-numbers check in `tools/lint/lints.py` reads
README.md only, so this file is not linted for numbers.
