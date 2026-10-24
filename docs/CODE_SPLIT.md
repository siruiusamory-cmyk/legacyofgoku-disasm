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

The address-taken channel sees 6063 odd in-image words, 4333 distinct addresses, in 265 runs of two or more consecutive words.
The copy channel reads the DMA3 setup at `0x0800996e`: 316 B from `0x08000138` to IWRAM `0x03003bc0`.

## Starts and ends

1518 starts, 1518 with an end, 0 open; 0 fragment entries lie inside another start.

A seed that falls inside an instruction of a row in the other mode is not a start.

| reason | starts |
| --- | --- |
| - | 513 |
| next-start | 0 |
| pool | 0 |
| no-return | 1005 |
| no-body | 0 |

Entry flags:

| flag | starts |
| --- | --- |
| data | 17 |
| undecodable | 0 |
| clobber | 0 |

A `data` start is one whose first instructions are a data prefix before its own prologue, unless a copy names its first byte and its save is the routine's own frame save; or one whose body carries a Thumb halfword with an empty register list, which no assembler emits and no ARMv4T core executes as code.


A `no-return` end is where the walk stopped at a halfword the CPU cannot execute before it met a return, so it is a measured stop and not a return. Runtime-only entries: none, because this title carries no runtime capture, so no row here is credited by one.

## Instruction bytes

The walk marks 46766 B of instructions: 25088 B proven, 21678 B filtered, 0 B table-held. The closed bounds hold 45158 B, which is less because a bound stops at the next start or at the first halfword the CPU cannot execute.

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
| residual: no naming entry reaches the byte | 1576276 | 18.8924 % |
| padding: a run of eight or more equal bytes | 1227830 | 14.7161 % |
| data: a run of address-taken words | 4552 | 0.0546 % |
| data: a literal load reads the word | 3004 | 0.0360 % |
| code by a closing entry | 0 | 0.0000 % |
| residual: a decodable run at its null | 5529473 | 66.2732 % |
| residual: closing run below its null bar | 2315 | 0.0277 % |

45158 B proven + 1227830 B padding + 7556 B data + 0 B code + 7108064 B residual = 8388608 B, the image size.

## The channels that claim the remainder

A channel is accepted only when the same rule over the same bytes of a pair-permuted image covers under 5.0 % of the bytes it claims.

| channel | hit rate on the proven code | null | verdict |
| --- | --- | --- | --- |
| a decodable run of 8 or more Thumb halfwords | 31196/45158 B = 69.0819 % | 5572524 B = 100.5703 % of the 5540922 B class | refused |
| a named word whose linear walk of at most 512 instructions reaches a return | 866/1518 starts = 57.0487 % | 2586 B of the 2315 B it claims = 111.7063 % | refused |