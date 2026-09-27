# Bullet Cathedral index and broad-phase argument

This is a mathematical argument about the
[`bench/bullet_cathedral.bend`](../bench/bullet_cathedral.bend) source,
**not a machine-checked Bend theorem**. The independent
[oracle](../bench/bullet_cathedral_oracle.py) exhaustively tests the first
120 frames against all 256 drones and is separate evidence.

## Nine-cell coverage

Each drone has one owner cell `(tx, ty)` in a 16×16 grid with 32-pixel cells.
Its center is `(32tx + 16 + 5 sin(...), 32ty + 16 + 5 cos(...))`. Thus each
coordinate lies between `32t + 11` and `32t + 21`, inclusive.

The friendly bullet's current position is `(x, y)`. Its previous position
is `(x - drift, y + 6)`, with `|drift| ≤ 0.65`. The swept-circle test accepts
a drone center only within `2 + 7 = 9` pixels of that segment. For an
onscreen bullet, `cx = floor(x) >> 5` and `cy = floor(y) >> 5`, so its current
coordinate lies in the corresponding 32-pixel cell.

If a drone's owner cell is at least two cells to the right, its smallest x
is `32(cx + 2) + 11`; the greatest possible bullet-segment x is less than
`32(cx + 1) + 0.65`. Their separation exceeds `42.35 > 9`. Two cells to the
left gives the same bound in the other direction. If the owner cell is at
least two cells below, its smallest y is `32(cy + 2) + 11`; the bullet
segment's greatest y is less than `32(cy + 1) + 6`, leaving more than
`37 > 9`. Two cells above leaves at least 43 pixels. A cell farther away
only increases the gap. Therefore a geometric hit can occur only when both
`|tx - cx| ≤ 1` and `|ty - cy| ≤ 1`: one of the nine cells enumerated by
`Nearby`.

This proof uses the scene's current friendly-bullet motion and drone orbit
bounds. Changing those constants requires checking the inequalities again.
It also assumes the usual real-number interpretation of the source F32
expressions. The large margins make ordinary rounding unlikely to threaten
coverage, but this document does not formally prove an IEEE-754 bound for
every native backend.

## Index bounds

An onscreen bullet satisfies `0 ≤ x,y < 512`. Conversion to U32 and shift
by five produce `cx,cy ∈ 0..15`. Each of the nine candidate coordinates is
checked to be `<16` before the source constructs `target = tx + 16ty`, so
`target <256`, the health Array's size. Out-of-grid candidate coordinates
wrap in U32, then fail the `<16` test. The framebuffer's `covered` predicate
checks `x,y <512` before `ink` writes `x + 512y`, so that index is
`<262144`. The HUD range is `0..6143`, also inside the framebuffer.

This establishes the intended source-level bounds if `covered`,
`valid_cell`, and their reducer order remain as written. The per-frame
checksum comparison checks the actual compiled behavior for the 120-frame
run; it is not a proof of compiler, runtime, or graphics backend correctness.
