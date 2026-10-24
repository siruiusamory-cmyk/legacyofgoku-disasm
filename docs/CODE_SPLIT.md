# The code and data split

`tools/split/census.py` derives this page from the retail image and `--check` re-derives it.

## Channels

| channel | entries it starts |
| --- | --- |
| vector | 2 |
| copy | 5 |
| call | 223 |
| pool | 7 |
| table | 420 |
| repeated | 49 |

The address-taken channel sees 6063 odd in-image words, 4333 distinct addresses, in 265 runs of two or more consecutive words.
The copy channel reads the DMA3 setup at `0x0800996e`: 316 B from `0x08000138` to IWRAM `0x03003bc0`.

## Starts and ends

1520 starts, 1520 with an end, 0 open; 0 fragment entries lie inside another start.

| reason | starts |
| --- | --- |
| - | 513 |
| next-start | 2 |
| pool | 0 |
| no-return | 1005 |
| no-body | 0 |

Entry flags:

| flag | starts |
| --- | --- |
| data | 17 |
| undecodable | 0 |
| clobber | 0 |

A `no-return` end is where the walk stopped at a halfword the CPU cannot execute before it met a return, so it is a measured stop and not a return. Runtime-only entries: none, because this title carries no runtime capture, so no row here is credited by one.

## Instruction bytes

The walk marks 46766 B of instructions: 25088 B proven, 21678 B filtered, 0 B table-held. The closed bounds hold 45106 B, which is less because a bound stops at the next start or at the first halfword the CPU cannot execute.

## The image's byte classes

| class | bytes | share |
| --- | --- | --- |
| proven code | 25088 | 0.2991 % |
| filtered pointer-entry code | 21678 | 0.2584 % |
| table-held code | 0 | 0.0000 % |
| literal pool | 2976 | 0.0355 % |
| unclassified | 8338866 | 99.4070 % |

## Code-shaped remainder

8343502 B outside every closed bound: 1227830 B padding, 5540964 B decodable runs of 8 or more Thumb halfwords, 1574708 B neither (275 extents).

The same decodable-run rule over the same bytes of a pair-permuted image gives 5572576 B, 100.5705 % of the 5540964 B class, so the class is a chance shape.
