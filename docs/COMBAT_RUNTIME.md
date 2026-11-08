# Original actor graphics and combat access paths

These findings were decoded from the canonical US image, SHA-256
`3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9`,
during DBZ-033. Addresses identify proving accesses, not newly claimed function
boundaries. Runtime examples use mGBA 0.11 and private states; no ROM, artwork,
state or image capture is committed here.

## Cells, palettes and object resources

The measured cell record is sixteen bytes: signed halfword X/Y at `+0/+2`,
unsigned halfword width/height at `+4/+6`, tile count at `+8`, attribute bytes at
`+9..+11`, and tile-data pointer at `+12`. The renderer consumes size at `+10`
and shape at `+11` directly as GBA OAM size/shape codes. In particular, 8x16
and 16x8 rectangles use size zero, not the longest-side exponent. Size one
would render 8x32 and 32x8 and consume adjacent tile data.

Visibility reads the full width/height through the current cell pointer at
`0x0800AF80`; replacing only the draw routine cannot enlarge visibility safely.
The native draw path at `0x0800B02A..0x0800B032` appends to the OAM cursor, and
`0x0800B09A..0x0800B0A6` places the low nibble of object `+0x0D` into palette
bits 12..15. The object field is the raw bank number, not a shifted attribute.

The palette allocator at `0x08005EA6` scans sixteen registered palettes with
reference counts and exact-content reuse. Exhaustion must not be treated as a
free physical palette slot: the fallback index is zero. Runtime palette
ownership and the palette actually used to draw an imported piece are separate
questions. The native red-tint wrapper table at `0x08011F18` requires its registered
tint palette while active, even if a replacement renderer normally supplies
colours from the art definition.

The native pool has 96 actor slots. Per-frame OAM and OBJ tile limits are 128
entries and 1024 32-byte tiles. A quiet scene's cursor is not a combat capacity
proof; safety requires checking the live append cursors before each draw.

## Transformation advancement

Art 32 state 9 uses the advance pointer at `0x08542A5C`, targeting the native
advance body containing `0x0800C9E2..0x0800CA14`. The native tick increments
before the frame-selection site `0x0800C9EC`. Its original transition window
is eighty active updates. A replacement formula at that site must account for
the increment to avoid skipping frame zero. This is an original-engine timing
fact; an eleven-frame donor clip is compatibility behavior, not retail LOG1.

## Player ki and damage

The observed player ki path starts at `0x0800B3DC`: allocation at `0x0800B3E2`
and binding at `0x0800B3F6` create art `0x086B3AA8`, behavior `0x081C7B14`,
with owner pointer at object `+0x3C`. Charge uses initialization `0x0800B4EC`,
update `0x0800B4FA` and advancement `0x0800B4AE`. Flight is the next behavior
row `0x081C7B28`, with initialization `0x0800B554`, update `0x0800B5A2` and
advancement `0x0800AEFA`. Impact uses row `0x081C7B3C` and `0x0800B4CA`.
The latter's original duration is 24 ticks, then deferred removal `0x080028C4`.

The native velocity table `0x08011E68` already moves three pixels per update:
down/up `(0,+3)/(0,-3)`, left/right `(-3,0)/(+3,0)`. The same rows supply
muzzle offsets `(0,8)`, `(0,-8)`, `(-8,-2)` and `(12,-2)`. Native flight
initialization computes power through `0x0800E568` and stores it at `+0x2C`.

Melee acceptance reaches the original damage call at `0x08005690`; projectile
acceptance reaches `0x08005708`. Both call `0x08007416`, retaining the damage
calculation rather than substituting a donor damage constant. Victim HP is a
word at damage-block `+0x4C`; `+0x9C` is an alive flag, not HP.

Runtime `codex-retail-combat-path-01` used starting state SHA-256
`758548f112c53715a09954bc3900e9d793bfb8bbc3ea02266a14cc1d1cc360b8`.
It observed projectile charge at frames 57..60, flight at frame 61 and contact
at frame 62, with native three-pixel motion. This is a selected encounter;
it does not prove every attack, world collision or scene transition.

The address `0x0800573A` initializes a damageable NPC block. It is not the
player projectile constructor and should not anchor projectile instrumentation.
