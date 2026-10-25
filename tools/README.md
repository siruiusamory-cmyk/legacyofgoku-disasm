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
| `tools/recomp/runtime_labels.py` | `check.cmd`'s test file, a person | records the dispatch entries a bounded run measured as `tools/code/RUNTIME_LABELS.csv` from the recorder's accumulator (`--import --write`), and `--check` re-measures every label against the census evidence table with a displaced-label null |
| `tools/incbin.bat` | `rebuild.cmd` | writes a slice if it is absent, then stops |
| `tools/compress/build.cmd` | `rebuild.cmd`, `tools/compress/jcalg1.py` | builds `compress.exe` from `tools/compress/jcalg1/` with CMake and the Visual C++ toolset |
| `tools/compress/jcalg1.py` | nothing yet | the JCALG1 body grammar, and the encoder call that builds the compressor on first use |
| `tools/compress/f1_streams.py` | `rebuild.cmd`, a person | walks the three stream lists the custom decompressor serves from its header count, decodes every entry by its type - a row stream, a palette stream or an image stream - re-encodes it, refuses a record that does not round trip, and rewrites `asm/remainder.s` so each list is a generated run; `--check` re-derives them |
| `tools/compress/bios_streams.py` | `rebuild.cmd`, a person | decodes the streams the image names and the BIOS codecs read - one LZ77 and ten Huffman, the Huffman through the tree grammar at `0x00001014` - re-encodes each one (greedy 18-byte-window for LZ77, code-table replay for Huffman) and rewrites `asm/remainder.s` so every round-tripping stream is a generated run; refuses a Huffman tree that shares a node; `--check` re-derives them |
| `tools/research/startup_writes.py` | a person | walks the startup path and prints every DMA kick, software interrupt and IWRAM or EWRAM block store with its source, destination and length |
| `tools/scripts/script_streams.py` | `rebuild.cmd`, a person | walks the twelve-byte script descriptors at `0x08591f3c` the interpreter at `0x0800a3e6` runs, decodes every opcode record to its frame count of `0x00`-terminated segments, re-encodes it, refuses a record that does not round trip, and rewrites `asm/remainder.s` so each row's records are a generated run; `--check` re-derives the two tables and the rows |
| `tools/research/f1_population.py` | a person, `tools/research/test_f1_population.py` | walks the custom decompressor's stream list from its header count, decodes every row stream under the code's grammar, counts the entries by type, and runs the permuted-region null and the token-plan ambiguity census |
| `tools/testkit.py` | every ROM-gated test | the ROM presence skip and the digest assert |

`tools/compress/compress.exe` and every `baserom.gba_*.extracted` slice are build products and are
never tracked.

The tests sit beside what they test: `tools/gate/test_gate.py`, `tools/lint/test_lint.py`,
`tools/extract/test_slice_rom.py`, `tools/compress/test_jcalg1.py`,
`tools/compress/test_f1_streams.py`,
`tools/compress/test_bios_streams.py`, `tools/research/test_startup_writes.py`,
`tools/research/test_f1_population.py`, `tools/scripts/test_script_streams.py`,
`tools/split/test_census.py`,
`tools/code/test_emit_code.py`, `tools/recomp/test_export_inputs.py`,
`tools/recomp/test_runtime_labels.py` and `tools/test_check_links.py`.
