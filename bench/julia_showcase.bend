import Base
import ../xf.bend as X
import ../transduce_core.bend as T
import ./array_partition/bench_clock.bend as Clock

# A four-sample grayscale Julia-set kernel. Coordinates and iteration counts
# are deterministic; a frame number moves the Julia parameter without input.
type Render is Data:
  Render{shift: Nat, mask: U32, scale: F32, cx: F32, cy: F32}

type Orbit is Data:
  Active{zx: F32, zy: F32, cx: F32, cy: F32, count: U32}
  Escaped{count: U32}

def settings(+depth: Nat, frame: U32) -> Render:
  +width = U32.shln(1, depth)
  +phase = U32.to_f32(frame)
  Render{depth, U32.sub(width, 1),
    F32.div(3.0, U32.to_f32(U32.mul(width, 2))),
    F32.add(F32.sub(0.0, 0.74543), F32.mul(phase, 0.0001)),
    F32.add(0.11301, F32.mul(phase, 0.00007))}

def pixel_samples(pixel: U32) -> T.Range:
  +begin = U32.mul(pixel, 4)
  T.range_between(begin, U32.add(begin, 4))

def orbit_next(active: Bool, +zx: F32, +zy: F32,
  +cx: F32, +cy: F32, count: U32) -> Orbit:
  match active:
    case False{}: Escaped{count}
    case True{}:
      Active{F32.add(F32.sub(F32.mul(zx, zx), F32.mul(zy, zy)), cx),
        F32.add(F32.mul(2.0, F32.mul(zx, zy)), cy),
        cx, cy, U32.inc(count)}

def orbit_step(orbit: Orbit) -> Orbit:
  match orbit:
    case Escaped{count}: Escaped{count}
    case Active{+zx, +zy, +cx, +cy, count}:
      orbit_next(F32.is_le(F32.add(F32.mul(zx, zx),
        F32.mul(zy, zy)), 4.0), zx, zy, cx, cy, count)

def orbit_count(orbit: Orbit) -> U32:
  match orbit:
    case Escaped{count}: count
    case Active{zx, zy, cx, cy, count}: count

def iterate(left: Nat, orbit: Orbit) -> U32:
  match left:
    case 0n: orbit_count(orbit)
    case 1n+p: iterate(p, orbit_step(orbit))

def sample_go(config: Render, +id: U32) -> U32:
  match config:
    case Render{shift, mask, +scale, cx, cy}:
      +pixel = U32.shrn(id, 2n)
      +x = U32.and(pixel, mask)
      +y = U32.shrn(pixel, shift)
      sx = U32.and(id, 1)
      sy = U32.and(U32.shrn(id, 1n), 1)
      zx = F32.sub(F32.mul(U32.to_f32(U32.add(U32.mul(x, 2), sx)),
        scale), 1.5)
      zy = F32.sub(F32.mul(U32.to_f32(U32.add(U32.mul(y, 2), sy)),
        scale), 1.5)
      iterate(32n, Active{zx, zy, cx, cy, 0})

def sample(config: Render, id: U32) -> U32:
  sample_go(config, id)

def shade(samples: U32 & U32 & U32 & U32) -> U32:
  (a, b, c, d) = samples
  U32.mul(U32.add(U32.add(a, b), U32.add(c, d)), 2)

def visible(value: U32) -> Bool:
  U32.is_ge(value, 32)

def add_if(yes: Bool, acc: U32, value: U32) -> U32:
  match yes:
    case True{}: U32.add(acc, value)
    case False{}: acc

def add_visible_go(acc: U32, +value: U32) -> U32:
  add_if(visible(value), acc, value)

def add_visible(acc: U32, value: U32) -> U32:
  add_visible_go(acc, value)

def fused_range(config: Render, begin: U32, end: U32) -> U32:
  X.transduce(X.comp2(X.comp5(
    X.map(~U32, ~T.Range, ~pixel_samples),
    X.cat(T.Range.adapter()),
    X.map_with(~U32, ~U32, ~Render, ~sample, config),
    X.partition4(~U32),
    X.map(~(U32 & U32 & U32 & U32), ~U32, ~shade)),
    X.filter(~U32, ~visible)),
    X.sum_rf(), 0, T.range_between(begin, end))

def fused(config: Render, pixels: U32) -> U32:
  fused_range(config, 0, pixels)

# A tile contains consecutive pixels. Every leaf receives the same number of
# pixels, though escape times still vary with image position.
def tiled(tiles: Nat, +config: Render, +begin: U32, +end: U32) -> U32:
  match tiles:
    case 0n: fused_range(config, begin, end)
    case 1n+ +p:
      +mid = U32.add(begin, U32.shrn(U32.sub(end, begin), 1n))
      a b = tiled(p, config, begin, mid) tiled(p, config, mid, end)
      U32.add(a, b)

def empty_pixels() -> List<U32>:
  []

# Image export path: the same five stages emit every grayscale pixel.
# List construction and text output are outside the checksum benchmark.
def image_pixels(config: Render, pixels: U32) -> List<U32>:
  List.reverse(&1, U32,
    X.into(empty_pixels(), X.comp5(
      X.map(~U32, ~T.Range, ~pixel_samples),
      X.cat(T.Range.adapter()),
      X.map_with(~U32, ~U32, ~Render, ~sample, config),
      X.partition4(~U32),
      X.map(~(U32 & U32 & U32 & U32), ~U32, ~shade)),
      T.range(pixels)))

def direct_loop(left: Nat, +pixel: U32, +config: Render,
  acc: U32) -> U32:
  match left:
    case 0n: acc
    case 1n+p:
      +begin = U32.mul(pixel, 4)
      value = shade((sample(config, begin),
        sample(config, U32.add(begin, 1)),
        sample(config, U32.add(begin, 2)),
        sample(config, U32.add(begin, 3))))
      direct_loop(p, U32.inc(pixel), config, add_visible(acc, value))

def direct(config: Render, pixels: U32) -> U32:
  direct_loop(U32.to_nat(pixels), 0, config, 0)

def materialized(config: Render, pixels: U32) -> U32:
  List.foldl(~&1, ~U32, ~U32, ~add_visible,
    image_pixels(config, pixels), 0)

def choose(mode: Nat, config: Render, pixels: U32) -> U32:
  match mode:
    case 0n: fused(config, pixels)
    case 1n: direct(config, pixels)
    case 4n: tiled(6n, config, 0, pixels)
    case 5n: tiled!(6n, config, 0, pixels)
    case 6n: tiled!(10n, config, 0, pixels)
    case 7n: tiled!(12n, config, 0, pixels)
    case _: materialized(config, pixels)

def parsed_nat(value: Maybe<&2, Nat>) -> Nat:
  match value:
    case None{}: 0n
    case Some{n}: n

def parsed_u32(value: Maybe<&2, U32>) -> U32:
  match value:
    case None{}: 0
    case Some{n}: n

def measure(mode: Nat, +depth: Nat, frame: U32) -> IO(Unit):
  config = settings(depth, frame)
  pixels = U32.shln(1, Nat.mul(depth, 2n))
  do IO<Unit>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, choose(mode, config, pixels))
    after : Nat <- Clock.now_us()
    IO.print(Nat.show(Nat.sub(after, before)) ++ " " ++ U32.show(answer))

def frames(left: Nat, +mode: Nat, +depth: Nat,
  +frame: U32, acc: U32) -> U32:
  match left:
    case 0n: acc
    case 1n+p:
      pixels = U32.shln(1, Nat.mul(depth, 2n))
      value = choose(mode, settings(depth, frame), pixels)
      frames(p, mode, depth, U32.inc(frame), U32.add(acc, value))

# Warm one frame before timing; different frame numbers keep every iteration
# semantically distinct. Output is elapsed-us, total checksum, warm checksum.
def measure_repeated(+mode: Nat, +depth: Nat,
  +frame: U32, count: Nat) -> IO(Unit):
  do IO<Unit>:
    warm : U32 <- IO.pure(U32, frames(1n, mode, depth, frame, 0))
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, frames(count, mode, depth,
      U32.inc(frame), 0))
    after : Nat <- Clock.now_us()
    IO.print(Nat.show(Nat.sub(after, before)) ++ " " ++
      U32.show(answer) ++ " " ++ U32.show(warm))

def measure_series(left: Nat, +mode: Nat, +depth: Nat,
  +frame: U32, +count: Nat) -> IO(Unit):
  match left:
    case 0n: IO.pure(Unit, Unit{})
    case 1n+p:
      do IO<Unit>:
        measure_repeated(mode, depth, frame, count)
        measure_series(p, mode, depth,
          U32.add(frame, U32.inc(U32.from_nat(count))), count)

def dump(+depth: Nat, frame: U32) -> IO(Unit):
  config = settings(depth, frame)
  pixels = U32.shln(1, Nat.mul(depth, 2n))
  IO.print(List.show(~&1, ~U32, ~U32.show,
    image_pixels(config, pixels)))

def dispatch(mode: Nat, depth: Nat, frame: U32) -> IO(Unit):
  match mode:
    case 2n: dump(depth, frame)
    case _: measure(mode, depth, frame)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> depth <> frame <> repeats <> sessions <> rest:
      measure_series(parsed_nat(Nat.read(sessions)),
        parsed_nat(Nat.read(mode)), parsed_nat(Nat.read(depth)),
        parsed_u32(U32.read(frame)), parsed_nat(Nat.read(repeats)))
    case mode <> depth <> frame <> repeats <> rest:
      measure_repeated(parsed_nat(Nat.read(mode)),
        parsed_nat(Nat.read(depth)), parsed_u32(U32.read(frame)),
        parsed_nat(Nat.read(repeats)))
    case mode <> depth <> frame <> rest:
      dispatch(parsed_nat(Nat.read(mode)), parsed_nat(Nat.read(depth)),
        parsed_u32(U32.read(frame)))
    case _: measure(0n, 7n, 0)

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
