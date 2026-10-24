# Readability

Two counts are recorded from this tree and may not rise without the change that raises them being
the point of the commit. `tools/lint/lints.py` re-derives both and fails on any difference, in
either direction, so lowering one is an edit to the baseline file and nothing else.

## Raw address literals

`tools/lint/READABILITY_BASELINE.txt`:

```
ram=0
hardware=0
```

`ram` counts literals in `asm/*.s` that spell an address in `0x03xxxxxx`, `hardware` the ones in
`0x04xxxxxx`. Both are counted outside `asm/registers.s` and `asm/memory.s`, because those two files
are where an address belongs: transcribed code names the constant, and the constant is declared
once. The startup block reads every address it uses from those two files, which is why both counts
are zero and the first raw literal a later ticket writes is a failure.

## Address-named symbols

`tools/lint/NAMING_BASELINE.txt` holds one count: the number of `sub_XXXXXXXX` symbols in
`asm/*.s`. It is zero because no function is named yet. A name is an evidence claim, so a new
address-named symbol is a deliberate edit to this file and to the row that carries its evidence.

## What this page does not claim

There is no naming ledger and no function index yet, so this page says nothing about names or about
which file carries a function. Those arrive with the census and the emitter, and each gets its own
ratchet when it does.
