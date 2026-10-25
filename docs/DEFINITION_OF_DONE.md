# Definition of done

One target for every change: the full image, as `python tools\gate\gate.py` measures it.

## What counts as source

- Code assembled or compiled from tracked source.
- A tracked table of plain numbers whose rows have a named layout and a consumer or a structural
  proof. An unlabeled byte dump is not source.
- A byte-exact generator that re-encodes assets from the builder's own ROM at build time, with
  nothing from the ROM committed. An identity copy is not source.

## The finish line

- 100 % of the 8,388,608 B image. A byte that cannot be reached is named irreducible, with its
  reason.

## Current gate output

```
generated=3567985
identity copies=0 (0.0000 %)
raw-data=4775157 (56.9243 %)
source=3613451 of 8388608 (43.0757 %)
accounted=8388608 of 8388608 (100.0000 %) raw 4775157 + identity 0 + source 3613451
```

README.md carries the same figures; the README-numbers check in `tools/lint/lints.py` reads
README.md only, so this file is not linted for numbers.
