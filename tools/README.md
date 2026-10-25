# Tools

Every tool the build and the checks run, and what runs it.

| Tool | Run by | What it does |
| --- | --- | --- |
| `tools/gate/gate.py` | `extract.cmd`, `rebuild.cmd`'s proof step, a person | verifies the retail image, runs the lints and the cited tests, rebuilds, compares the digest and prints the byte accounting |
| `tools/lint/lints.py` | `check.cmd`, `tools/gate/gate.py`, CI | the source checks and the two ratchets |
| `tools/check_links.py` | `check.cmd`, CI | every relative link in a tracked page resolves and no page cites a raw commit hash |
| `tools/extract/slice_rom.py` | `tools/incbin.bat` | writes one byte range of the retail image to a `.extracted` file |
| `tools/split/census.py` | a person, `tools/split/test_census.py` | seeds the code census from every static pointer channel, walks each start to an end, flags the entries and writes `tools/code/CENSUS_EVIDENCE.csv` and `docs/CODE_SPLIT.md`; `--check` re-derives both |
| `tools/code/emit_code.py` | `rebuild.cmd`, a person | disassembles every census code row to Thumb or ARM assembly in the mode the row records, writes `build/code/`, `asm/remainder.s` and the raw slices; `--check` re-derives them |
| `tools/recomp/export_inputs.py` | `tools/gate/gate.py` (`--check`), a person | writes `tools/recomp/RECOMP_INPUTS.toml`: one row per census start with its closed bound, mode and channel, the rows the emitter leaves raw with their reason, the image identity and its one code copy; `--check` re-derives it |
| `tools/recomp/runtime_labels.py` | `check.cmd`'s test file, a person | records the dispatch entries bounded runs measured as `tools/code/RUNTIME_LABELS.csv` from the recorder's accumulator (`--import --admit --write` unions them with the tracked rows and drops the ones the census cannot place), and `--check` re-measures every label against the census evidence table with a displaced-label null and sums `RUNTIME_LABELS_RUNS.csv` against the file; a run row's `entries` counts the labels that run added to the file, so the rows sum to it |
| `tools/incbin.bat` | `rebuild.cmd` | writes a slice if it is absent, then stops |
| `tools/compress/build.cmd` | `rebuild.cmd`, `tools/compress/jcalg1.py` | builds `compress.exe` from `tools/compress/jcalg1/` with CMake and the Visual C++ toolset |
| `tools/compress/jcalg1.py` | nothing yet | the JCALG1 body grammar, and the encoder call that builds the compressor on first use |
| `tools/compress/f1_streams.py` | `rebuild.cmd`, a person | walks the three stream lists the custom decompressor serves from its header count, decodes every entry by its type - a row stream, a palette stream or an image stream - re-encodes it, refuses a record that does not round trip, and rewrites `asm/remainder.s` so each list is a generated run; `--check` re-derives them |
| `tools/compress/bios_streams.py` | `rebuild.cmd`, a person | decodes the 159 streams the image names - one LZ77 and 158 Huffman, the Huffman through the tree grammar at `0x00001014` - re-encodes each one (greedy 18-byte-window for LZ77, code-table replay for Huffman, the shorter of two codes when a tree gives a symbol more than one) and rewrites `asm/remainder.s` so every round-tripping stream is a generated run; refuses a Huffman tree that shares a node; `--check` re-derives them |
| `tools/research/startup_writes.py` | a person | walks the startup path and prints every DMA kick, software interrupt and IWRAM or EWRAM block store with its source, destination and length |
| `tools/scripts/script_streams.py` | `rebuild.cmd`, a person | walks the twelve-byte script descriptors at `0x08591f3c` the interpreter at `0x0800a3e6` runs, decodes every opcode record to its frame count of `0x00`-terminated segments, re-encodes it, refuses a record that does not round trip, and rewrites `asm/remainder.s` so each row's records are a generated run; `--check` re-derives the two tables and the rows |
| `tools/research/f1_population.py` | a person, `tools/research/test_f1_population.py` | walks the custom decompressor's stream list from its header count, decodes every row stream under the code's grammar, counts the entries by type, and runs the permuted-region null and the token-plan ambiguity census |
| `tools/research/actor_rows.py` | `rebuild.cmd`, a person | decodes the 35 actor stat rows the spawn initialiser at `0x08006d90` indexes at stride `0x40` under the bound `cmp r2,#0x22`, re-encodes each row and the name pool their `+4` fields point at, refuses an image whose bounds, digest or round trip differs, and rewrites `asm/remainder.s` so the family is a generated run; no row value and no name is tracked, only the layout and the bounds; `--check` re-derives the run and the slices |
| `tools/research/credits_rows.py` | `rebuild.cmd`, a person | decodes the 142-line credits table the renderer at `0x08001cfa` indexes under the bound `cmp r0,#0x8e`, re-encodes the four header halfwords, the pointer rows and the 79-text pool they name, refuses an image whose bounds, digest or round trip differ, and rewrites `asm/remainder.s` so the family is a generated run; no halfword and no string is tracked, only the layout and the bounds; `--check` re-derives the run and the slices |
| `tools/research/dialogue_rows.py` | `rebuild.cmd`, a person | decodes the 80-record dialogue table the reader at `0x080051d0` indexes at stride `0x4` and whose records it walks as eight-byte nodes ending on a `0xff` kind, re-encodes every record's node chain and the `0x00`-terminated text pool its `+4` words name, refuses an image whose bounds, digest or round trip differ, and rewrites `asm/remainder.s` so the family is a generated run; no node value and no string is tracked, only the layout and the bounds; `--check` re-derives the run and the slices |
| `tools/research/message_rows.py` | `rebuild.cmd`, a person | decodes the six messages from `0x085c2de2` that six pc-relative loads name one by one, and the 31-row message-id table at `0x085c2fb8` the code loads and scales by four, re-encodes the messages, the rows and the `0x00`-terminated pool of 14 strings they name up to the data base at `0x085c31ec`, refuses an image whose bounds, digest or round trip differ, and rewrites `asm/remainder.s` so both families are generated runs; no string and no row is tracked, only the layout and the bounds; `--check` re-derives the runs and the slices |
| `tools/research/pointer_rows.py` | `rebuild.cmd`, a person | probes the pointer rule over the raw slices - four or more consecutive four-byte-aligned words that each name the image - as 317 runs and 21,152 B, emits the 14 runs whose every word names a label the code files already define as `DCD` lines naming that label and its Thumb bit (1,308 B), leaves the 303 runs whose targets no label names raw and counts them, reads `asm/remainder.s` as a positioned token list that must cover the whole image, refuses a `DCD` that does not re-derive the word at its position, and rewrites `asm/remainder.s` and the gap slices; `--check` re-derives the list and the slices |
| `tools/testkit.py` | every ROM-gated test | the ROM presence skip and the digest assert |

`tools/compress/compress.exe` and every `baserom.gba_*.extracted` slice are build products and are
never tracked.

The tests sit beside what they test: `tools/gate/test_gate.py`, `tools/lint/test_lint.py`,
`tools/extract/test_slice_rom.py`, `tools/compress/test_jcalg1.py`,
`tools/compress/test_f1_streams.py`,
`tools/compress/test_bios_streams.py`, `tools/research/test_startup_writes.py`,
`tools/research/test_f1_population.py`, `tools/scripts/test_script_streams.py`,
`tools/research/test_actor_rows.py`, `tools/research/test_credits_rows.py`,
`tools/research/test_message_rows.py`, `tools/research/test_pointer_rows.py`,
`tools/split/test_census.py`,
`tools/code/test_emit_code.py`, `tools/recomp/test_export_inputs.py`,
`tools/recomp/test_runtime_labels.py` and `tools/test_check_links.py`.
