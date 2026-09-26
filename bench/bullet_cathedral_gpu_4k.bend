import Base
import ../xf.bend as X
import ../transduce_core.bend as T
import ./bullet_cathedral_4k_frames.bend as B
import ./array_partition/bench_clock.bend as Clock

# A CPU-built screen-space tree. Each GPU leaf owns a short list of sprites
# overlapping its tile; no GPU task shares a mutable framebuffer.
type Cells is Data:
  Leaf{sprites: List<&2, B.Sprite>}
  Node{tl: Cells, tr: Cells, bl: Cells, br: Cells}

type Scene is Data:
  Scene{cells: Cells, score: U32, shield: U32}

type Bins is Type:
  Bins{buckets: Array<List<&2, B.Sprite>>, level: Nat}

def morton_go(left: Nat, +x: U32, +y: U32,
  +place: U32, +acc: U32) -> U32:
  match left:
    case 0n: acc
    case 1n+p:
      +digit = U32.add(U32.and(x, 1), U32.mul(U32.and(y, 1), 2))
      morton_go(p, U32.shrn(x, 1n), U32.shrn(y, 1n),
        U32.mul(place, 4), U32.add(acc, U32.mul(digit, place)))

def bucket_after(pair: Array<List<&2, B.Sprite>> & List<&2, B.Sprite>,
  sprite: B.Sprite, +index: U32) -> Array<List<&2, B.Sprite>>:
  (buckets, sprites) = pair
  Array.set(List<&2, B.Sprite>, buckets, index, sprite <> sprites)

def bucket_put(buckets: Array<List<&2, B.Sprite>>,
  +index: U32, sprite: B.Sprite) -> Array<List<&2, B.Sprite>>:
  bucket_after(Array.get(List<&2, B.Sprite>, buckets, index),
    sprite, index)

def bucket_row(left: Nat, +x: U32, +y: U32,
  +level: Nat, +sprite: B.Sprite,
  buckets: Array<List<&2, B.Sprite>>) -> Array<List<&2, B.Sprite>>:
  match left:
    case 0n: buckets
    case 1n+p:
      +index = morton_go(level, x, y, 1, 0)
      bucket_row(p, U32.inc(x), y, level, sprite,
        bucket_put(buckets, index, sprite))

def bucket_rows(left: Nat, +y: U32, +x: U32, +width: Nat,
  +level: Nat, +sprite: B.Sprite,
  buckets: Array<List<&2, B.Sprite>>) -> Array<List<&2, B.Sprite>>:
  match left:
    case 0n: buckets
    case 1n+p:
      bucket_rows(p, U32.inc(y), x, width, level, sprite,
        bucket_row(width, x, y, level, sprite, buckets))

def bins_put(bins: Bins, sprite: B.Sprite) -> Bins:
  match bins:
    case Bins{buckets, +level}:
      match sprite:
        case B.Sprite{+x, +y, +radius, +color}:
          +cx = F32.to_u32(x)
          +cy = F32.to_u32(y)
          +size = U32.shrn(4096, level)
          +left = U32.div(U32.sub(cx, U32.min(cx, radius)), size)
          +top = U32.div(U32.sub(cy, U32.min(cy, radius)), size)
          +right = U32.div(U32.min(3839, U32.add(cx, radius)), size)
          +bottom = U32.div(U32.min(2159, U32.add(cy, radius)), size)
          +width = U32.to_nat(U32.inc(U32.sub(right, left)))
          +height = U32.to_nat(U32.inc(U32.sub(bottom, top)))
          Bins{bucket_rows(height, top, left, width, level,
            B.Sprite{x, y, radius, color}, buckets), level}

def bins_put_unscaled(bins: Bins, sprite: B.Sprite) -> Bins:
  bins_put(bins, B.scale_sprite(sprite))

def bins_reducer() -> T.Reducer<B.Sprite, Bins>:
  T.Reducer{Empty, Bins, Bins,
    bins => T.Continue{bins},
    bins => sprite => T.Continue{bins_put_unscaled(bins, sprite)},
    bins => bins}

def bins_rf() -> X.Rf<B.Sprite, Bins, bins_reducer(), Bins>:
  X.Rf{bins => bins}

def make_bullets(pool: B.BulletPool, +frame: U32, bins: Bins) -> Bins:
  X.transduce(X.comp2(
    X.filter(~B.Bullet, ~B.onscreen),
    X.map(~B.Bullet, ~B.Sprite, ~B.bullet_sprite)),
    bins_rf(), bins, B.PoolSource.source(B.PoolSource{pool, frame}))

def make_drones(health: Array<U32>, +frame: U32, bins: Bins) -> Bins:
  X.transduce(X.comp3(
    X.map_indexed(~U32, ~B.IndexedHealth, ~B.indexed_health),
    X.map_with(~B.IndexedHealth, ~Maybe<B.Sprite>, ~U32,
      ~B.drone_from_pair, frame),
    X.keep(~Maybe<B.Sprite>, ~B.Sprite, ~(x => x))),
    bins_rf(), bins, health)

def make_hits(hits: List<&2, B.Hit>, +frame: U32, bins: Bins) -> Bins:
  X.transduce(X.comp2(
    X.map_with(~B.Hit, ~B.Sprite, ~U32, ~B.hit_sprite, frame),
    X.filter(~B.Sprite, ~B.sprite_active)),
    bins_rf(), bins, B.owned_hits(hits))

def same_sprite(sprite: B.Sprite) -> B.Sprite:
  sprite

def make_icons(+frame: U32, +score: U32, +shield: U32,
  bins: Bins) -> Bins:
  X.transduce(X.map(~B.Sprite, ~B.Sprite, ~same_sprite),
    bins_rf(), bins, B.icons(frame, score, shield))

def cells_of(level: Nat,
  buckets: Array<List<&2, B.Sprite>>) -> Cells:
  match level buckets:
    case 0n ALeaf{sprites}: Leaf{sprites}
    case 1n+ +p ANode{ANode{tl, tr}, ANode{bl, br}}:
      Node{cells_of(p, tl), cells_of(p, tr),
        cells_of(p, bl), cells_of(p, br)}
    case _ _: Leaf{[]}

def scene_of(bins: Bins, +score: U32, +shield: U32) -> Scene:
  match bins:
    case Bins{buckets, level}:
      Scene{cells_of(level, buckets), score, shield}

def prepare(world: B.Damage, +frame: U32, +level: Nat) -> Scene:
  match world:
    case B.Damage{health, +score, +player_hp, accepted}:
      bullets = make_bullets(B.build_pool(frame), frame,
        Bins{Array.new(List<&2, B.Sprite>, Nat.mul(level, 2n), []), level})
      drones = make_drones(health, frame, bullets)
      hits = make_hits(accepted, frame, drones)
      scene_of(make_icons(frame, score, player_hp, hits),
        score, player_hp)

def ink_color(ink: B.Ink) -> U32:
  match ink:
    case B.Ink{index, color}: color

def shade_if(covered: Bool, sprite: B.Sprite, +x: U32, +y: U32,
  color: U32) -> U32:
  match covered:
    case False{}: color
    case True{}:
      B.blend(color, ink_color(B.pixel_ink(B.PixelSample{sprite, x, y})))

def shade_sprite(+sprite: B.Sprite, +x: U32, +y: U32,
  color: U32) -> U32:
  shade_if(B.covered(B.PixelSample{sprite, x, y}),
    sprite, x, y, color)

def shade_sprites(sprites: List<&2, B.Sprite>, +x: U32, +y: U32,
  color: U32) -> U32:
  match sprites:
    case Nil{}: color
    case sprite <> rest:
      shade_sprites(rest, x, y, shade_sprite(sprite, x, y, color))

def hud_if(lit: Bool, +index: U32, color: U32) -> U32:
  match lit:
    case False{}: color
    case True{}:
      B.blend(color, ink_color(B.hud_ink(B.HudCell{index, True{}})))

def hud_color(cell: B.HudCell, color: U32) -> U32:
  match cell:
    case B.HudCell{index, lit}:
      hud_if(lit, index, color)

def pixel_visible(sprites: List<&2, B.Sprite>, +x: U32, +y: U32,
  +score: U32, +shield: U32) -> U32:
  +index = U32.add(x, U32.mul(y, 3840))
  background = ink_color(B.sky(index))
  color = shade_sprites(sprites, x, y, background)
  hud_color(B.hud_cell_go(score, shield, index), color)

def pixel_if(visible: Bool, sprites: List<&2, B.Sprite>,
  +x: U32, +y: U32, +score: U32, +shield: U32) -> U32:
  match visible:
    case False{}: 0
    case True{}: pixel_visible(sprites, x, y, score, shield)

def pixel(sprites: List<&2, B.Sprite>, +x: U32, +y: U32,
  +score: U32, +shield: U32) -> U32:
  pixel_if(Bool.and(U32.is_lt(x, 3840), U32.is_lt(y, 2160)),
    sprites, x, y, score, shield)

def tile_loop(left: Nat, +at: U32, +x: U32, +y: U32,
  +size: U32, +sprites: List<&2, B.Sprite>,
  +score: U32, +shield: U32, acc: U32) -> U32:
  match left:
    case 0n: acc
    case 1n+p:
      +px = U32.add(x, U32.mod(at, size))
      +py = U32.add(y, U32.div(at, size))
      tile_loop(p, U32.inc(at), x, y, size, sprites, score, shield,
        U32.add(acc, pixel(sprites, px, py, score, shield)))

def draw(level: Nat, cells: Cells, +x: U32, +y: U32,
  +size: U32, +score: U32, +shield: U32, active: Bool) -> U32:
  match level cells active:
    case _ _ False{}: 0
    case 0n Leaf{sprites} True{}:
      tile_loop(U32.to_nat(U32.mul(size, size)), 0, x, y, size,
        sprites, score, shield, 0)
    case 1n+ +p Node{tl, tr, bl, br} True{}:
      +half = U32.shrn(size, 1n)
      +x1 = U32.add(x, half)
      +y1 = U32.add(y, half)
      a b c d = draw(p, tl, x, y, half, score, shield, True{})
        draw(p, tr, x1, y, half, score, shield, U32.is_lt(x1, 3840))
        draw(p, bl, x, y1, half, score, shield, U32.is_lt(y1, 2160))
        draw(p, br, x1, y1, half, score, shield,
          Bool.and(U32.is_lt(x1, 3840), U32.is_lt(y1, 2160)))
      U32.add(U32.add(a, b), U32.add(c, d))
    case _ _ _: 0

def tile_set_if(visible: Bool, pixels: Array<U32>,
  +index: U32, color: U32) -> Array<U32>:
  match visible:
    case False{}: pixels
    case True{}: Array.set(U32, pixels, index, color)

def tile_into(left: Nat, +at: U32, +x: U32, +y: U32,
  +size: U32, +sprites: List<&2, B.Sprite>,
  +score: U32, +shield: U32, pixels: Array<U32>) -> Array<U32>:
  match left:
    case 0n: pixels
    case 1n+p:
      +px = U32.add(x, U32.mod(at, size))
      +py = U32.add(y, U32.div(at, size))
      +index = U32.add(px, U32.mul(py, 3840))
      tile_into(p, U32.inc(at), x, y, size, sprites, score, shield,
        tile_set_if(Bool.and(U32.is_lt(px, 3840),
          U32.is_lt(py, 2160)), pixels, index,
          pixel(sprites, px, py, score, shield)))

def draw_into(level: Nat, cells: Cells, +x: U32, +y: U32,
  +size: U32, +score: U32, +shield: U32,
  pixels: Array<U32>) -> Array<U32>:
  match level cells:
    case 0n Leaf{sprites}:
      tile_into(U32.to_nat(U32.mul(size, size)), 0, x, y, size,
        sprites, score, shield, pixels)
    case 1n+ +p Node{tl, tr, bl, br}:
      +half = U32.shrn(size, 1n)
      +x1 = U32.add(x, half)
      +y1 = U32.add(y, half)
      first = draw_into(p, tl, x, y, half, score, shield, pixels)
      second = draw_into(p, tr, x1, y, half, score, shield, first)
      third = draw_into(p, bl, x, y1, half, score, shield, second)
      draw_into(p, br, x1, y1, half, score, shield, third)
    case _ _: pixels

def draw_cpu(scene: Scene, +level: Nat) -> U32:
  match scene:
    case Scene{cells, +score, +shield}:
      draw(level, cells, 0, 0, 4096, score, shield, True{})

# Returning the scene keeps GPU readers borrowed rather than transferring
# ownership of all candidate lists into the device call.
def draw_gpu(scene: Scene, +level: Nat) -> U32 & Scene:
  match scene:
    case Scene{+cells, +score, +shield}:
      (draw!(level, cells, 0, 0, 4096, score, shield, True{}),
        Scene{cells, score, shield})

def gpu_result(result: U32 & Scene) -> U32:
  (checksum, scene) = result
  checksum

def choose(gpu: Bool, scene: Scene, +level: Nat) -> IO(U32):
  match gpu:
    case True{}: IO.pure(U32, gpu_result(draw_gpu(scene, level)))
    case False{}: IO.pure(U32, draw_cpu(scene, level))

def measure(+frame: U32, +level: Nat, gpu: Bool) -> IO(Unit):
  do IO<Unit>:
    before : Nat <- Clock.now_us()
    world : B.Damage <- IO.pure(B.Damage,
      B.simulate(U32.to_nat(U32.inc(frame)), 0, B.initial()))
    +simulated : Nat <- Clock.now_us()
    scene : Scene <- IO.pure(Scene,
      prepare(world, frame, level))
    +built : Nat <- Clock.now_us()
    seam : Nat <- IO.now()
    checksum : U32 <- choose(gpu, scene, level)
    after : Nat <- Clock.now_us()
    IO.print(Nat.show(Nat.sub(simulated, before)) ++ " " ++
      Nat.show(Nat.sub(built, simulated)) ++ " " ++
      Nat.show(Nat.sub(after, built)) ++ " " ++ U32.show(checksum))

def samples(left: Nat, +frame: U32, +level: Nat, +gpu: Bool) -> IO(Unit):
  match left:
    case 0n: IO.pure(Unit, Unit{})
    case 1n+p:
      do IO<Unit>:
        Unit <- measure(frame, level, gpu)
        samples(p, frame, level, gpu)

def dump_scene(scene: Scene, +level: Nat) -> IO(Unit):
  match scene:
    case Scene{cells, +score, +shield}:
      IO.print(List.show(~&1, ~U32, ~U32.show,
        Array.to_list(~U32,
          draw_into(level, cells, 0, 0, 4096, score, shield,
            Array.new(U32, 23n, 0)))))

def dump(+frame: U32, +level: Nat) -> IO(Unit):
  dump_scene(prepare(B.simulate(U32.to_nat(U32.inc(frame)),
    0, B.initial()), frame, level), level)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case frame <> level <> mode <> repeat <> rest:
      samples(B.parsed_nat(Nat.read(repeat)),
        B.parsed_u32(U32.read(frame)), B.parsed_nat(Nat.read(level)),
        U32.is_gt(B.parsed_u32(U32.read(mode)), 0))
    case frame <> level <> mode <> rest:
      measure(B.parsed_u32(U32.read(frame)),
        B.parsed_nat(Nat.read(level)),
        U32.is_gt(B.parsed_u32(U32.read(mode)), 0))
    case frame <> level <> rest:
      dump(B.parsed_u32(U32.read(frame)),
        B.parsed_nat(Nat.read(level)))
    case _: IO.print("expected frame, tile depth, mode (0=CPU, 1=GPU)")

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
