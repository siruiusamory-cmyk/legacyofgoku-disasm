# The dialogue runtime surface

What a conversation does to the machine between the record table and the OAM buffer, as the retail
bytes describe it. `tools/research/dialogue_runtime.py` decodes every instruction this page cites
and refuses an image where any of them differs, `--check` included.

The image this page is derived from is 8,388,608 B with game code `ALGE` and sha256
`3BA9919E26704B0F5FDC2BFABC7F7A0404C71413761D38ABCD94224C3BD4B1B9`; the reader refuses any other
image, so every address below is an address in that exact image.

## What this page claims, and what it does not

Every row below is **read from bytes**: one instruction in the retail image proves it. The page
names no function and claims no entry point or boundary: each address is the instruction that
proves the row, and the reader re-decodes exactly that instruction. The record layout, its 80 rows
and its 988 nodes are already derived by [dialogue_rows.py](../tools/research/dialogue_rows.py) and
this page links to it rather than restating it.

Nothing here is a runtime observation. No claim on this page was produced by an emulator, and none
of it says what a controller press does on a given frame.

## 1. One conversation, one blocking call, one persistent cursor

The talk handler reads an index from a character record (`0x0800581C ldrb r0, [r4, #0x16]`) and
makes a single call (`0x08005824 bl 0x080051D0`). The node's own continuation sits below that call
(`0x08005334` is the per-node push, `0x08005366` the flush after it), so the scene's continuation
past the talk waits for the whole chain of nodes; the call is not re-entered per node.

The cursor is advanced **before** the node is classified:

```
0x0800520C  ldrb  r0, [r4, #0x1]     successor index, read first
0x08005210  strb  r0, [r1, #0x0]     and stored into the cursor here
0x08005212  ldrb  r0, [r4, #0x0]     only now the kind byte
0x08005214  cmp   r0, #0xFF
```

So the cursor names the successor of a terminal node by the time the terminal branch runs, and the
next conversation starts at that node with no second writer of the cursor. The terminal branch
(`0x0800521A`, `0x08005220`, `0x08005228`) redraws the map and flushes; it pushes no state.

## 2. The page object

Four page objects at stride `0x824` start at `0x02029D94`, which the literal at `0x080053B8` names
and the dialogue build passes to the installer at `0x0800539A`. The reader checks the literal and
that all four bases are named by a word somewhere in the image.

| off | width | meaning | proving access |
| --- | --- | --- | --- |
| `+0x00` | u8 | BG palette bank | `0x08008D14` reads it, `0x08008D42` writes it |
| `+0x02` | u16 | map origin column | `0x08008D4C` writes it, `0x08008D32` copies it to the pen |
| `+0x04` | u16 | map origin row | `0x08008D52` writes it, `0x08008D36` copies it to the pen |
| `+0x06` | u16 | wrap limit | `0x08008D56` writes it |
| `+0x08` | u16 | line limit | `0x08008D5C` writes it |
| `+0x0A` | u16 | pen column | `0x08008D32` writes it |
| `+0x0C` | u16 | pen row | `0x08008D36` writes it |
| `+0x10` | u32 | map destination | `0x08008D40` writes it, `0x08008D94` hands it to DMA |
| `+0x14` | u32 | text cursor | `0x0800930C` sets it, `0x08009364` zeroes it |
| `+0x18` | u32 | line budget | `0x08009324` writes it |
| `+0x1C` | u8 | reveal counter | `0x08009316` clears it |
| `+0x20` | u32 | done word | `0x0800931C` clears it, `0x0800932C` tests it |
| `+0x24` | n/a | the cell map a transfer reads | `0x08008D90` takes its address, `0x08008D92` names it as the source |

The segment installer, ten instructions from `0x0800930A` to `0x08009326`, is the whole of a node's
page state: store the node's text pointer into `+0x14`, refill the map (`0x08009310`), clear the
reveal counter (`0x08009316`), clear the **word** at `+0x20` (`0x0800931C`), then set
`+0x18 = (s16)+0x08 - (s16)+0x04`: the line budget is the difference of the two limits, read as
signed halfwords (`0x0800931A`, `0x08009320`, `0x08009322`).

Two gaps in the object carry no access among the instructions cited here: `+0x0E` (2 B, between two
halfword fields) and `+0x1D`..`+0x1F` (3 B, after a byte field). That is inferred from structure,
because every neighbouring access uses a width that stops at the gap, and a whole-image access census is
not part of this page.

## 3. Page advance is inside the driver

`0x08005392` passes the page and a callback to `0x08009328` (`0x0800539A`), then reports the
conversation's own end condition as *the cursor is null* (`0x0800539E` reads `page[+0x14]`,
`0x080053A6` clears the result for a non-null cursor). The driver tests the done word first
(`0x0800932C`) and, on the exhausted path, reads the cursor, reads the byte it points at, and
clears either the press word or the cursor:

```
0x08009350  ldr   r0, [r4, #0x14]    the text cursor
0x08009358  ldrb  r0, [r0, #0x0]     the byte it points at
0x0800935A  cmp   r0, #0x0
0x08009360  strh  r7, [r6, #0x0]     press word, when the cursor is null or the byte is 0
0x08009364  str   r7, [r4, #0x14]    cursor zeroed
```

A page advance therefore rewrites no object, allocates nothing and moves no OAM entry: it is the
same cursor, the same page, and only the budget, reveal counter and done word are re-armed.

## 4. The OBJ staging span

The sprite staging area is one EWRAM span, `0x0200B024`, named by exactly two words in the image:
the reset inside the rebuild (`0x080027D4`) and the flush (`0x080028EC`). The flush at `0x08002896`
is a DMA3 transfer whose four inputs are all derived:

```
0x0800289C  r1 = 0x030007A0                 0x080028A0  subs r1, #0xC  -> context 0x03000794
0x080028A2  r0 = ctx[+0x04]                 staged cursor
0x0800289E  r2 = 0xFDFF4FDC                 = -0x0200B024, the same span negated
0x080028A4  adds r0, r0, r2                 staged bytes
0x080028A8  ldrh r1, [r1, #0x0A]            OBJ base tile
0x080028AE  lsls r1, r1, #5                 base tile as a byte offset
0x080028B0  adds r2, r1, r2                 destination = 0x06010000 + base tile * 32
0x080028B8  lsrs r0, r0, #2                 count in words
0x080028BC  movs r0, #0x21; lsls #0xA       control 0x8400
```

So the transfer is positional and exact: byte `k` of the staged span lands at
`0x06010000 + (ctx[+0x0A] * 32) + k`, which is tile `ctx[+0x0A] + k / 32`. The reader checks that
the subtrahend is exactly the negation of the staging base and that the base is named twice.

The cursor only ever falls back to the base at a rebuild: `0x08002570` stores the span into
`ctx[+0x04]` while `0x0800256C` stores the entry cursor and `0x08002562` loads the context, and the
rebuild clears the shadow first (`0x0800255E`). Staged bytes therefore accumulate across one
rebuild and reset at the next, not per frame.

## 5. Where an affine matrix lives, and who may keep one

OAM interleaves 128 sprite entries with 32 rotation/scaling groups: matrix `m` keeps `PA` at the
halfword at `0x20*m + 0x06`, `PB` at `+0x0E`, `PC` at `+0x16` and `PD` at `+0x1E`, which are the pad
halfwords of entries `4m`..`4m+3`. The initialiser at `0x0800988C` proves that layout: for 32 groups
(`0x080098A6 cmp r1, #0x20`) it writes `0x0100, 0, 0, 0x0100` (`0x0800989E`, `0x080098A2`,
`0x080098A0`, `0x080098A8`), the identity matrix in 8.8 fixed point, and then clears the 128
entries' attribute words (`0x080098B6`, `0x080098BC cmp r0, #0x80`).

Two transfers bracket a matrix's life: the whole 1024-byte shadow is copied to OAM every frame
(`0x080098CA`, source `0x0202BE24`), and the rebuild's first body zero-fills the **whole** shadow
(`0x0800255E` calls `0x080098DE`: a constant-word fill of `0x100` words from a zeroed scratch word
at `0x030047EC`). A matrix therefore survives from its writer's frame until the next rebuild and no
longer, and every rebuild starts from zero pads.

One staging routine (`0x08005118`, its body ending at `0x080051B2`) appends a sprite entry, and what
it stores is exactly two words of that entry plus three cursor fields: `0x08005164` and
`0x080051A2` write word 0, `0x08005176` and `0x08005186` write word 1, `0x08005138` advances the
entry cursor, `0x080051A8` the staging cursor and `0x080051AE` the tile cursor. No store in that
extent reaches a pad offset. Word 1 is rebuilt from the entry's own old value: `0x08005168` loads
it, `0x0800516E` keeps 10 bits of the new x, and `0x0800517C`..`0x08005186` replace bits 12..15 with
the palette byte the record carries at `+0x0D`. The pad halfwords share word 1's upper half, so the
retail writer **preserves the upper half of word 1**: a pad is carried across, not zeroed.

That is the constraint the layout imposes: a matrix is one halfword inside an entry's word, so a
writer that stores a whole word over an entry can clear a pad it does not own. Who owns which pad is
therefore a code question, and the two cases are separate:

| | whose code | what the bytes say |
| --- | --- | --- |
| original engine | the staging routine at `0x08005118`..`0x080051B2` | loads word 1 at `0x08005168` and rebuilds only bits 0..9 and 12..15, so bits 16..31 (both pad halfwords inside word 1) are **preserved**, not cleared |
| new compatibility code | a derived image's own writer, which is not in this tree | composing word 1 as one value and storing it clears the upper half, and that is new code; no original behaviour is claimed for it |

Which entries are affine at any given moment is not claimed here, and no affine clearing behaviour is
attributed to this engine anywhere on this page.

## 6. Terminal and repeat are a graph property

Record 66, the scene at `0x081647F4`, has 39 nodes. Following the `successor` field from node 0
visits `0`..`10` and then returns to `8`, so:

| slot | 0..6 | 7 | 8 | 9 | 10 |
| --- | --- | --- | --- | --- | --- |
| kind | 59/34 alternating | `0xFF` | 59 | 31 | `0xFF` |
| successor | +1 each | 8 | 9 | 10 | **8** |
| text | present | none | present | present | none |

The first conversation runs `0`..`6` and stops at the terminal `7`, whose successor is `8`; every
later conversation starts at `8`, runs `8` and `9`, and stops at the terminal `10`, whose successor
is `8` again. That is where the repeat comes from: not a flag, a cycle in the successor field. The
reader derives the chain, requires both terminals to carry no text pointer, and requires the last
text of each pass to be `6` and `9`.

## 7. Re-deriving it

```
python tools\research\dialogue_runtime.py --check
```

It prints one line, and with this image:

```
cites=91 records=80 nodes=988 pages=4 stride=0x824 staging=0x0200B024 slots=8 pads=0x06,0x0E,0x16,0x1E terminals=7,10,12,14,19,24,26,34,36,38 scene=66
```

Any drift in a cited instruction, the page literal, the staging negation, the state table, the
matrix stores or record 66's chain prints `RUNTIME FAIL` with the address that disagreed. Nothing
here writes a file: the dialogue family's generated run and slices stay
[dialogue_rows.py](../tools/research/dialogue_rows.py)'s job.

## 8. Not part of this page

- No runtime behaviour, no frame cadence, no reveal timing, no input handling claim.
- No function name, entry point or extent.
- No enumeration of every instruction that touches a page or a pad: the gaps in §2 are inferred
  from the widths of the neighbouring accesses, not from a census.
- No text content: not one byte of the game's dialogue is reproduced.
- Nothing about the extended scene-plan and presentation mechanism a derived image adds; that is not
  in this image and is not described here. In particular a compatibility writer that stores word 1 as
  one value is new code in that derived image, not original engine behaviour, and this page does not
  attribute any pad-clearing to the retail writer, which the citations in §5 show preserves it.
