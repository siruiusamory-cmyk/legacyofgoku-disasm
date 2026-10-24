# What the startup installs

The startup path is every direct call and branch reachable from the reset entry `0x080000c0`, the C
entry `0x08000274` and the interrupt handler `0x08000138`, walked in Thumb and ARM until the frame
loop at `0x08009766` and the thirteen indirect calls listed below. `tools/research/startup_writes.py`
re-derives every row on this page from the image; `tools/research/test_startup_writes.py` asserts them
and shows the check failing on a doctored copy of the copy length.

## The startup block writes two words

| Site | Instruction | Value | Destination | Width |
| --- | --- | --- | --- | --- |
| `0x080000d4` | `e1c100b0 strh r0,[r1]` | `0x0000` (`e3a00000` at `0x080000cc`) | `0x03000004` (pool word at `0x0800010c`) | 16 |
| `0x080000ec` | `e5810000 str r0,[r1]` | `0x08000138` (pool word at `0x08000110`) | `0x03007ffc` (pool word at `0x08000108`) | 32 |

The same block writes two stack pointers, not memory: `e59fd030` at `0x080000c8` loads `sp_irq` from
the pool word `0x03007fa0` at `0x08000100` after `e3a00012`/`e121f000` select IRQ mode with FIQ
unmasked, and `e59fd01c` at `0x080000e0` loads `sp_system` from `0x03007f00` at `0x08000104` after
`e3a0001f` selects system mode. It hands off with `e59f001c` (`0x080000f0`, literal `0x08000275` at
`0x08000114`), `e1a0e00f` (`mov lr,pc`) and `e12fff10` (`bx r0`) at `0x080000f8`: ARM to Thumb at
`0x08000274`, return address `0x080000fc`, where `eaffffef` branches back to `0x080000c0`.

## The vector is moved to IWRAM

`0x0800996e` (called from `0x0800971e`) copies `0x13c` bytes from the image at `0x08000138` to IWRAM
`0x03003bc0` with DMA3, then stores that IWRAM address into the interrupt vector: `63c8` at
`0x080099a0` is `str r0,[r1,#0x3c]` with `r1` loaded from the pool word `0x03007fc0` at `0x08009a14`,
so `0x03007ffc` receives `0x03003bc0`. It then fills the fourteen handler slots at `0x03003b88` with
`0x0800996d` by a fixed-source DMA3 fill.

## Every bulk write the path programmes

`bytes` is `count` times the transfer width taken from control bit 10. `fixed` means the source
address does not increment, so the write repeats one word or halfword.

| Site | Channel | Source | Destination | Count | Control | Bytes | Fixed | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `0x080007ee` | 3 | `0x030047e8` | not resolved | `0x54` | `0x8100` | `0xa8` | yes | zero fill |
| `0x08009702` | 3 | `0x030047ec` | `0x02000000` | `0x0` | `0x8500` | `0x0` | yes | no transfer |
| `0x08009714` | 3 | `0x030047ec` | `0x03000000` | `0x1f80` | `0x8500` | `0x7e00` | yes | zero fill |
| `0x08009912` | 3 | `0x030047e8` | `0x05000000` | `0x100` | `0x8100` | `0x200` | yes | zero fill |
| `0x08009932` | 3 | `0x030047ec` | `0x0202be24` | `0x100` | `0x8500` | `0x400` | yes | zero fill |
| `0x08009980` | 3 | `0x08000138` | `0x03003bc0` | `0x4f` | `0x8400` | `0x13c` | no | code |
| `0x0800999a` | 3 | `0x030047ec` | `0x03003b88` | `0xe` | `0x8500` | `0x38` | yes | pointer fill |
| `0x0800aa4a` | 1 | `0x0203f800` | `0x040000a0` | `0x4` | `0xb660` | `0x10` | no | sound FIFO |
| `0x0800aa58` | 2 | `0x0203fe00` | `0x040000a4` | `0x4` | `0xf660` | `0x10` | no | sound FIFO |
| `0x0800aa70` | 3 | `0x08008814` | `0x03003d44` | `0x2a` | `0x8400` | `0xa8` | no | code bytes, execution not established |
| `0x0800aa80` | 3 | `0x080088bc` | `0x03003dec` | `0x34` | `0x8400` | `0xd0` | no | code bytes, execution not established |
| `0x0800aa8e` | 3 | `0x0800898c` | `0x03003ebc` | `0x35` | `0x8400` | `0xd4` | no | code bytes, execution not established |
| `0x0800aaa4` | 3 | `0x030047ec` | `0x0203ee24` | `0x477` | `0x8500` | `0x11dc` | yes | zero fill |

The row at `0x080007ee` leaves its destination unresolved because the DMA base is the function's own
argument; the one call in the path passes `r0 = 0x03000028` (`0x08000286` loads the pool word at
`0x080002b0`) and calls `0x080007d2` at `0x08000288`. Its control `0x8100` is a 16-bit fill of the
halfword at `0x030047e8`, which `0x080007de` has just set to zero.

## The IWRAM result

`0x13c` bytes of the image at `0x08000138` are copied to `0x03003bc0` and that address is written to
the interrupt vector, so the CPU branches into IWRAM on every interrupt. The source is the ARM handler
itself: `e3a03640` at `0x08000138` is `mov r3,#0x04000000`, `e5b32200` at `0x0800013c` is
`ldr r2,[r3,#0x200]!`, and `e12fff1e` at `0x08000264` is `bx lr`; the copy ends at `0x08000274`, the
Thumb C entry. This is the only copy the path proves is executed.

The three copies at `0x0800aa70`, `0x0800aa80` and `0x0800aa8e` move `0x24c` further bytes of image
code to `0x03003d44`, `0x03003dec` and `0x03003ebc`. Each source decodes as an ARM routine that ends
in `bx lr`: `0x08008814` opens with `push {r4,r5,r6,r7}` and returns at `0x080088b8` after
`0x080088b4 pop {r4,r5,r6,r7}`, `0x080088bc` opens with `push {r4,r5,r6,r7,r8}`, and `0x0800898c`
opens with `push {r4,r5,r6,r7,r8,sb}`. So the bytes are code, but nothing in the image names the
destinations: the only words equal
to `0x03003d44` and `0x03003ebc` are the DMA destination literals at `0x0800ab68` and `0x0800ab6c`,
there is no `0x03003d45`, and no branch reaches either destination. Whether they run from IWRAM is
**not established** and a runtime read would settle it.

## What the path does not use

No CPU copy loop: the only `ldm`/`stm` in the path with a resolved IWRAM base is `c303` at
`0x08005c38`, which stores two registers (8 B) to `0x03000984`. No `CpuSet` and no `CpuFastSet`: the
six software interrupts in the path are `df02` at `0x080099ea`, `df06` at `0x0800a854`, `0x0800a8ac`,
`0x0800a912` and `0x0800a96a`, and `df00` at `0x0800dc04`. Image-wide the halfwords `df0b` and `df0c`
occur 57 times, between `0x0815a5ac` and `0x0826a15c`, outside every span this walk decodes.

## Where the startup path ends

`0x08009766` is the frame loop: its body at `0x0800976c` calls the table entry at `+0x8` through
`0x0800e4a2` (`bx r1`), waits on `df02`, calls the entry at `+0xc`, and branches back while the result
is zero. When that loop returns, the C entry restores its stack and returns to `0x080000fc`. Thirteen
indirect calls are not followed: `0x08000248`, `0x0800e258`, `0x0800e324`, `0x0800e4a0`,
`0x0800e4a2`, `0x0800e4a6`, `0x0800e4d0`, `0x0800e4e6`, `0x0800e7a0`, `0x0800e7fc`, `0x0800e87e`,
`0x0800e910` and `0x0800e98a`. A bulk write reached only through one of them is not in the table
above; the walk covers 169 starts and 13 indirect edges, and no walk reached its step cap.
