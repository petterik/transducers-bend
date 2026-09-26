import Base
import ../xf.bend as X
import ../transduce_core.bend as T
import ../vec.bend as Vec
import ./array_partition/bench_clock.bend as Clock

# One deterministic star per 32x32 subpixel cell. Four subpixels make a pixel.
# A frame scrolls the field; all per-sample arithmetic is integer and bounded.
type Render is Data:
  Render{shift: Nat, pixel_mask: U32, sub_mask: U32,
    offset_x: U32, offset_y: U32}

def settings(+depth: Nat, +frame: U32) -> Render:
  +width = U32.shln(1, depth)
  Render{depth, U32.sub(width, 1), U32.sub(U32.mul(width, 2), 1),
    U32.mul(frame, 3), frame}

def pixel_samples(pixel: U32) -> T.Range:
  +begin = U32.mul(pixel, 4)
  T.range_between(begin, U32.add(begin, 4))

def cell_hash(x: U32, y: U32) -> U32:
  +a = U32.xor(U32.mul(x, 2654435761), U32.mul(y, 2246822507))
  +b = U32.xor(a, U32.shrn(a, 16n))
  +c = U32.mul(b, 3266489909)
  U32.xor(c, U32.shrn(c, 15n))

def distance_if(less: Bool, a: U32, b: U32) -> U32:
  match less:
    case True{}: U32.sub(b, a)
    case False{}: U32.sub(a, b)

def distance(+a: U32, +b: U32) -> U32:
  distance_if(U32.is_lt(a, b), a, b)

def light_if(near: Bool, radius: U32, hash: U32) -> U32:
  match near:
    case False{}: 0
    case True{}:
      strength = U32.add(128, U32.and(U32.shrn(hash, 18n), 127))
      U32.shrn(U32.mul(U32.sub(9, radius), strength), 3n)

def star_light(+gx: U32, +gy: U32) -> U32:
  +hash = cell_hash(U32.shrn(gx, 5n), U32.shrn(gy, 5n))
  +dx = distance(U32.and(gx, 31), U32.and(hash, 31))
  +dy = distance(U32.and(gy, 31), U32.and(U32.shrn(hash, 5n), 31))
  +radius = U32.add(U32.mul(dx, dx), U32.mul(dy, dy))
  light_if(U32.is_le(radius, 8), radius, hash)

def sample_go(config: Render, +id: U32) -> U32:
  match config:
    case Render{shift, pixel_mask, +sub_mask, offset_x, offset_y}:
      +pixel = U32.shrn(id, 2n)
      x = U32.and(pixel, pixel_mask)
      y = U32.shrn(pixel, shift)
      sx = U32.and(id, 1)
      sy = U32.and(U32.shrn(id, 1n), 1)
      gx = U32.and(U32.add(U32.add(U32.mul(x, 2), sx), offset_x),
        sub_mask)
      gy = U32.and(U32.add(U32.add(U32.mul(y, 2), sy), offset_y),
        sub_mask)
      star_light(gx, gy)

def sample(config: Render, id: U32) -> U32:
  sample_go(config, id)

def shade(samples: U32 & U32 & U32 & U32) -> U32:
  (a, b, c, d) = samples
  U32.min(255, U32.shrn(U32.add(U32.add(a, b), U32.add(c, d)), 2n))

def visible(value: U32) -> Bool:
  U32.is_gt(value, 0)

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

def tiled(tiles: Nat, +config: Render, +begin: U32, +end: U32) -> U32:
  match tiles:
    case 0n: fused_range(config, begin, end)
    case 1n+ +p:
      +mid = U32.add(begin, U32.shrn(U32.sub(end, begin), 1n))
      a b = tiled(p, config, begin, mid) tiled(p, config, mid, end)
      U32.add(a, b)

def empty_u32() -> List<U32>:
  []

def image_pixels(config: Render, pixels: U32) -> List<U32>:
  List.reverse(&1, U32,
    X.into(empty_u32(), X.comp5(
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

# This constructs only final pixels, preserving the distinction from staging.
def pixel_list(config: Render, pixels: U32) -> U32:
  List.foldl(~&1, ~U32, ~U32, ~add_visible,
    image_pixels(config, pixels), 0)

def empty_ranges() -> List<T.Range>:
  []

def list_ranges(pixels: U32) -> List<T.Range>:
  List.reverse(&1, T.Range,
    X.into(empty_ranges(), X.map(~U32, ~T.Range, ~pixel_samples),
      T.range(pixels)))

def list_ids(ranges: List<T.Range>) -> List<U32>:
  List.reverse(&1, U32,
    X.into(empty_u32(), X.cat(T.Range.adapter()), ranges))

def list_counts(config: Render, ids: List<U32>) -> List<U32>:
  List.reverse(&1, U32,
    X.into(empty_u32(),
      X.map_with(~U32, ~U32, ~Render, ~sample, config), ids))

def empty_groups() -> List<(U32 & U32 & U32 & U32)>:
  []

def list_groups(counts: List<U32>) -> List<(U32 & U32 & U32 & U32)>:
  List.reverse(&1, (U32 & U32 & U32 & U32),
    X.into(empty_groups(), X.partition4(~U32), counts))

def list_shades(groups: List<(U32 & U32 & U32 & U32)>) -> List<U32>:
  List.reverse(&1, U32,
    X.into(empty_u32(),
      X.map(~(U32 & U32 & U32 & U32), ~U32, ~shade), groups))

def list_visible(shades: List<U32>) -> List<U32>:
  List.reverse(&1, U32,
    X.into(empty_u32(), X.filter(~U32, ~visible), shades))

def list_staged(config: Render, pixels: U32) -> U32:
  List.foldl(~&1, ~U32, ~U32, ~U32.add,
    list_visible(list_shades(list_groups(list_counts(config,
      list_ids(list_ranges(pixels)))))), 0)

# Vec is backed by Bend's indexed Array. This control materializes the flat
# numeric boundaries and uses an ordered, growable destination. The tuple
# partition and shade map stay fused because Vec's public API requires Data.
def vec_ranges(pixels: U32) -> Vec.Vec<T.Range>:
  X.into(Vec.empty(~T.Range, T.range(0)),
    X.map(~U32, ~T.Range, ~pixel_samples), T.range(pixels))

def vec_ids(ranges: Vec.Vec<T.Range>) -> Vec.Vec<U32>:
  X.into(Vec.empty(~U32, 0), X.cat(T.Range.adapter()), ranges)

def vec_counts(config: Render, ids: Vec.Vec<U32>) -> Vec.Vec<U32>:
  X.into(Vec.empty(~U32, 0),
    X.map_with(~U32, ~U32, ~Render, ~sample, config), ids)

def vec_shades(counts: Vec.Vec<U32>) -> Vec.Vec<U32>:
  X.into(Vec.empty(~U32, 0),
    X.comp2(X.partition4(~U32),
      X.map(~(U32 & U32 & U32 & U32), ~U32, ~shade)), counts)

def identity(value: U32) -> U32:
  value

def vec_staged(config: Render, pixels: U32) -> U32:
  shades = vec_shades(vec_counts(config, vec_ids(vec_ranges(pixels))))
  selected = X.into(Vec.empty(~U32, 0), X.filter(~U32, ~visible), shades)
  X.transduce(X.map(~U32, ~U32, ~identity), X.sum_rf(), 0, selected)

def choose(mode: Nat, config: Render, pixels: U32) -> U32:
  match mode:
    case 0n: fused(config, pixels)
    case 1n: direct(config, pixels)
    case 3n: pixel_list(config, pixels)
    case 4n: list_staged(config, pixels)
    case 5n: vec_staged(config, pixels)
    case 6n: tiled(6n, config, 0, pixels)
    case 7n: tiled!(12n, config, 0, pixels)
    case 8n: tiled!(6n, config, 0, pixels)
    case 9n: tiled!(10n, config, 0, pixels)
    case _: fused(config, pixels)

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
