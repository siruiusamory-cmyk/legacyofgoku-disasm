# The code and data split

`tools/split/census.py` derives this page from the retail image and `--check` re-derives it.

## Channels

| channel | entries it starts |
| --- | --- |
| vector | 2 |
| copy | 5 |
| call | 223 |
| pool | 7 |
| table | 418 |
| repeated | 49 |
| runtime | 282 |

The address-taken channel sees 6063 odd in-image words, 4333 distinct addresses, in 265 runs of two or more consecutive words.
The copy channel reads the DMA3 setup at `0x0800996e`: 316 B from `0x08000138` to IWRAM `0x03003bc0`.

## Starts and ends

1800 starts, 1800 with an end, 0 open; 0 fragment entries lie inside another start.

A seed that falls inside an instruction of a row in the other mode is not a start.

| reason | starts |
| --- | --- |
| - | 555 |
| next-start | 0 |
| pool | 0 |
| no-return | 1245 |
| no-body | 0 |

Entry flags:

| flag | starts |
| --- | --- |
| data | 19 |
| undecodable | 0 |
| clobber | 0 |

A `data` start is one whose first instructions are a data prefix before its own prologue, unless a copy names its first byte and its save is the routine's own frame save; or one whose body carries a Thumb halfword with an empty register list, which no assembler emits and no ARMv4T core executes as code.


A `no-return` end is where the walk stopped at a halfword the CPU cannot execute before it met a return, so it is a measured stop and not a return. Runtime-only entries: 282, the dispatch entries a bounded run recorded in `tools/code/RUNTIME_LABELS.csv`, each admitted only where the walk also decodes it from an instruction boundary and closes it; a recorded entry that is already a static start adds no row, and a recorded entry that falls inside an instruction is refused instead of credited.

## Instruction bytes

The walk marks 46766 B of instructions: 25088 B proven, 21678 B filtered, 0 B table-held. The closed bounds hold 47902 B, which is less because a bound stops at the next start or at the first halfword the CPU cannot execute.

## The image's byte classes

| class | bytes | share |
| --- | --- | --- |
| proven code | 25088 | 0.2991 % |
| filtered pointer-entry code | 21678 | 0.2584 % |
| table-held code | 0 | 0.0000 % |
| literal pool | 2976 | 0.0355 % |
| unclassified | 8338866 | 99.4070 % |

## The remainder's split

Every byte outside a closed bound carries one reason below; the classes partition the remainder.

| class | bytes | share |
| --- | --- | --- |
| residual: no naming entry reaches the byte | 1575782 | 18.8927 % |
| padding: a run of eight or more equal bytes | 1227830 | 14.7209 % |
| data: a run of address-taken words | 4552 | 0.0546 % |
| data: a literal load reads the word | 3004 | 0.0360 % |
| code by a closing entry | 0 | 0.0000 % |
| residual: a decodable run at its null | 5527249 | 66.2684 % |
| residual: closing run below its null bar | 2289 | 0.0274 % |

47902 B proven + 1227830 B padding + 7556 B data + 0 B code + 7105320 B residual = 8388608 B, the image size.

## The channels that claim the remainder

A channel is accepted only when the same rule over the same bytes of a pair-permuted image covers under 5.0 % of the bytes it claims.

| channel | hit rate on the proven code | null | verdict |
| --- | --- | --- | --- |
| a decodable run of 8 or more Thumb halfwords | 32750/47902 B = 68.3688 % | 5570420 B = 100.5736 % of the 5538652 B class | refused |
| a named word whose linear walk of at most 512 instructions reaches a return | 1040/1800 starts = 57.7778 % | 2458 B of the 2289 B it claims = 107.3831 % | refused |