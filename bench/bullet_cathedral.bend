import Base
import ../xf.bend as X
import ../transduce_core.bend as T
import ../vec.bend as Vec
import ./array_partition/bench_clock.bend as Clock

# Bullet Cathedral: a deterministic arena, 512 square, with one moving
# shield drone assigned to each 32x32 cell. Bullets are generated from their
# spawn tick; every bullet queries just the nine nearby owner cells.
type Bullet is Data:
  Bullet{id: U32, frame: U32, x: F32, y: F32,
    old_x: F32, old_y: F32, radius: F32, color: U32, friendly: Bool}

type Nearby is Data:
  Nearby{bullet: Bullet}

type Candidate is Data:
  Candidate{bullet: Bullet, cell_x: U32, cell_y: U32}

type Hit is Data:
  Hit{target: U32, time: U32, x: F32, y: F32, color: U32}

type Damage is Type:
  Damage{health: Array<U32>, score: U32, player_hp: U32,
    accepted: List<&2, Hit>}

type Sprite is Data:
  Sprite{x: F32, y: F32, radius: U32, color: U32}

type SpritePixels is Data:
  SpritePixels{sprite: Sprite}

type PixelSample is Data:
  PixelSample{sprite: Sprite, x: U32, y: U32}

type MeasuredPixel is Data:
  MeasuredPixel{x: U32, y: U32, color: U32,
    distance2: F32, radius2: F32}

type Ink is Data:
  Ink{index: U32, color: U32}

type IndexedHealth is Data:
  IndexedHealth{index: Nat, hp: U32}

type Held is Type:
  Held{world: Damage, pixels: Array<U32>}

type HudCell is Data:
  HudCell{index: U32, lit: Bool}

type HudState is Data:
  HudState{score: U32, player_hp: U32}

def lane(id: U32) -> U32:
  U32.and(id, 127)

def birth(id: U32) -> U32:
  U32.shrn(id, 7n)

def active_ids(+frame: U32) -> T.Range:
  +end = U32.mul(U32.inc(frame), 128)
  +begin = U32.mul(U32.sub(frame, U32.min(frame, 95)), 128)
  T.range_between(begin, end)

def make_bullet_if(is_friendly: Bool, +frame: U32, +id: U32,
  +spoke: U32, +age: U32, +phase: U32, +angle: F32) -> Bullet:
  match is_friendly:
    case True{}:
      +agef = U32.to_f32(age)
      +base_x = F32.add(256.0,
        F32.add(F32.mul(F32.sub(U32.to_f32(spoke), 64.0), 1.25),
          F32.mul(F32.sin(F32.mul(U32.to_f32(birth(id)), 0.17)), 34.0)))
      +drift = F32.mul(F32.sin(angle), 0.65)
      +x = F32.add(base_x, F32.mul(agef, drift))
      +y = F32.sub(500.0, F32.mul(agef, 6.0))
      Bullet{id, frame, x, y, F32.sub(x, drift), F32.add(y, 6.0),
        2.0, 4521983, True{}}
    case False{}:
      +agef = U32.to_f32(age)
      +speed = F32.add(2.7, F32.mul(U32.to_f32(phase), 0.45))
      +turn = F32.add(angle,
        F32.mul(agef, F32.mul(U32.to_f32(phase), 0.006)))
      +vx = F32.mul(speed, F32.cos(turn))
      +vy = F32.mul(speed, F32.sin(turn))
      +x = F32.add(256.0, F32.mul(agef, vx))
      +y = F32.add(150.0, F32.mul(agef, vy))
      Bullet{id, frame, x, y, F32.sub(x, vx), F32.sub(y, vy),
        1.8, Bool.pick(U32, U32.is_lt(phase, 2), 16722617,
          16745284), False{}}

def make_bullet(+frame: U32, +id: U32) -> Bullet:
  +spoke = lane(id)
  +age = U32.sub(frame, birth(id))
  +phase = U32.and(birth(id), 3)
  +angle = F32.add(F32.mul(U32.to_f32(spoke), 0.049087385),
    F32.mul(U32.to_f32(birth(id)), 0.105))
  make_bullet_if(U32.is_eq(U32.and(spoke, 3), 0), frame, id,
    spoke, age, phase, angle)

def bullet_at(frame: U32, id: U32) -> Bullet:
  make_bullet(frame, id)

def onscreen(b: Bullet) -> Bool:
  match b:
    case Bullet{id, frame, +x, +y, old_x, old_y, radius, color, friendly}:
      Bool.and(Bool.and(F32.is_ge(x, 0.0), F32.is_lt(x, 512.0)),
        Bool.and(F32.is_ge(y, 0.0), F32.is_lt(y, 512.0)))

def friendly(b: Bullet) -> Bool:
  match b:
    case Bullet{id, frame, x, y, old_x, old_y, radius, color, friendly}:
      friendly

def hostile(b: Bullet) -> Bool:
  Bool.not(friendly(b))

def player_x(frame: U32) -> F32:
  F32.add(256.0,
    F32.mul(F32.sin(F32.mul(U32.to_f32(frame), 0.08)), 90.0))

def player_hit(b: Bullet) -> Bool:
  match b:
    case Bullet{id, +frame, x, y, +old_x, +old_y, radius, color, friendly}:
      +px = player_x(frame)
      +py = {480.0 : F32}
      +vx = F32.sub(x, old_x)
      +vy = F32.sub(y, old_y)
      +den = F32.add(F32.mul(vx, vx), F32.mul(vy, vy))
      +ratio = F32.div(F32.add(F32.mul(F32.sub(px, old_x), vx),
        F32.mul(F32.sub(py, old_y), vy)), F32.max(den, 0.0001))
      +t = F32.clamp(ratio, 0.0, 1.0)
      +dx = F32.sub(px, F32.add(old_x, F32.mul(t, vx)))
      +dy = F32.sub(py, F32.add(old_y, F32.mul(t, vy)))
      F32.is_le(F32.add(F32.mul(dx, dx), F32.mul(dy, dy)), 118.81)

def player_was_hit(b: Bullet) -> Bool:
  match b:
    case Bullet{id, +frame, x, y, old_x, old_y, radius, color, friendly}:
      +previous = U32.sub(frame, U32.min(frame, 1))
      +dx = F32.sub(old_x, player_x(previous))
      +dy = F32.sub(old_y, 480.0)
      F32.is_le(F32.add(F32.mul(dx, dx), F32.mul(dy, dy)), 118.81)

def player_enter_go(+b: Bullet) -> Bool:
  Bool.and(player_hit(b), Bool.not(player_was_hit(b)))

def player_enter(b: Bullet) -> Bool:
  player_enter_go(b)

def one_bullet(b: Bullet) -> U32:
  1

def incoming(+frame: U32) -> U32:
  X.transduce(X.comp4(
    X.map_with(~U32, ~Bullet, ~U32, ~bullet_at, frame),
    X.filter(~Bullet, ~hostile),
    X.filter(~Bullet, ~player_enter),
    X.map(~Bullet, ~U32, ~one_bullet)),
    X.sum_rf(), 0, active_ids(frame))

def valid_cell(c: Candidate) -> Bool:
  match c:
    case Candidate{bullet, cell_x, cell_y}:
      Bool.and(U32.is_lt(cell_x, 16), U32.is_lt(cell_y, 16))

def near(b: Bullet) -> Nearby:
  Nearby{b}

def candidate_at(+b: Bullet, +slot: U32) -> Candidate:
  match b:
    case Bullet{id, frame, x, y, old_x, old_y, radius, color, friendly}:
      +cx = U32.shrn(F32.to_u32(x), 5n)
      +cy = U32.shrn(F32.to_u32(y), 5n)
      Candidate{b,
        U32.sub(U32.add(cx, U32.mod(slot, 3)), 1),
        U32.sub(U32.add(cy, U32.div(slot, 3)), 1)}

def nearby_loop(~K: Data, ~S: Type,
  ~advance: S -> Candidate -> S, ~inspect: S -> T.Checked<K, S>,
  +b: Bullet, +remaining: Nat, checked: T.Checked<K, S>) -> S:
  match remaining checked:
    case n T.Halted{permit, state}: state
    case 0n T.Ready{state}: state
    case 1n+p T.Ready{state}:
      nearby_loop(~K, ~S, ~advance, ~inspect, b, p,
        inspect(advance(state,
          candidate_at(b, U32.sub(9, U32.from_nat(1n+p))))))

def nearby_source(~K: Data, ~S: Type,
  ~advance: S -> Candidate -> S, ~inspect: S -> T.Checked<K, S>,
  source: Nearby, state: S) -> S:
  match source:
    case Nearby{b}: nearby_loop(~K, ~S, ~advance, ~inspect,
      b, 9n, inspect(state))

def Nearby.adapter() -> T.SourceAdapter<Candidate, Nearby,
  (K => S => advance => inspect => ys => state =>
    nearby_source(~K, ~S, ~advance, ~inspect, ys, state))>:
  T.SourceAdapter{}

def enemy_x(+frame: U32, +cell_x: U32, +cell_y: U32) -> F32:
  +id = U32.add(cell_x, U32.mul(cell_y, 16))
  F32.add(F32.add(F32.mul(U32.to_f32(cell_x), 32.0), 16.0),
    F32.mul(F32.sin(F32.add(F32.mul(U32.to_f32(frame), 0.055),
      F32.mul(U32.to_f32(id), 0.27))), 5.0))

def enemy_y(+frame: U32, +cell_x: U32, +cell_y: U32) -> F32:
  +id = U32.add(cell_x, U32.mul(cell_y, 16))
  F32.add(F32.add(F32.mul(U32.to_f32(cell_y), 32.0), 16.0),
    F32.mul(F32.cos(F32.add(F32.mul(U32.to_f32(frame), 0.04),
      F32.mul(U32.to_f32(id), 0.31))), 5.0))

def hit(c: Candidate) -> Bool:
  match c:
    case Candidate{bullet, +cell_x, +cell_y}:
      match bullet:
        case Bullet{id, +frame, +x, +y, +old_x, +old_y, +radius, color, friendly}:
          +ex = enemy_x(frame, cell_x, cell_y)
          +ey = enemy_y(frame, cell_x, cell_y)
          +vx = F32.sub(x, old_x)
          +vy = F32.sub(y, old_y)
          +den = F32.add(F32.mul(vx, vx), F32.mul(vy, vy))
          +ratio = F32.div(F32.add(F32.mul(F32.sub(ex, old_x), vx),
            F32.mul(F32.sub(ey, old_y), vy)), F32.max(den, 0.0001))
          +t = F32.clamp(ratio, 0.0, 1.0)
          +dx = F32.sub(ex, F32.add(old_x, F32.mul(t, vx)))
          +dy = F32.sub(ey, F32.add(old_y, F32.mul(t, vy)))
          F32.is_le(F32.add(F32.mul(dx, dx), F32.mul(dy, dy)),
            F32.mul(F32.add(radius, 7.0), F32.add(radius, 7.0)))

def as_hit(c: Candidate) -> Hit:
  match c:
    case Candidate{bullet, +cell_x, +cell_y}:
      match bullet:
        case Bullet{id, frame, x, y, old_x, old_y, radius, color, friendly}:
          Hit{U32.add(cell_x, U32.mul(cell_y, 16)), frame, x, y, color}

def empty_hits() -> Vec.Vec<Hit>:
  Vec.empty(~Hit, Hit{0, 0, 0.0, 0.0, 0})

def hits(+frame: U32) -> Vec.Vec<Hit>:
  X.into(empty_hits(), X.comp2(X.comp5(
    X.map_with(~U32, ~Bullet, ~U32, ~bullet_at, frame),
    X.filter(~Bullet, ~onscreen),
    X.filter(~Bullet, ~friendly),
    X.map(~Bullet, ~Nearby, ~near),
    X.cat(Nearby.adapter())),
    X.comp3(X.filter(~Candidate, ~valid_cell),
      X.filter(~Candidate, ~hit),
      X.map(~Candidate, ~Hit, ~as_hit))), active_ids(frame))

def apply_hit_if(valid: Bool, health: Array<U32>, +hp: U32,
  +score: U32, player_hp: U32, accepted: List<&2, Hit>, +target: U32,
  time: U32, x: F32, y: F32, color: U32) -> T.Control<Empty, Damage>:
  match valid:
    case False{}: T.Continue{Damage{health, score, player_hp, accepted}}
    case True{}:
      T.Continue{Damage{Array.set(U32, health, target, U32.sub(hp, 1)),
        U32.add(score, 1), player_hp,
        Hit{target, time, x, y, color} <> accepted}}

def apply_hit_after(got: Array<U32> & U32, +score: U32,
  player_hp: U32, accepted: List<&2, Hit>, +target: U32,
  time: U32, x: F32, y: F32,
  color: U32) -> T.Control<Empty, Damage>:
  (health, +hp) = got
  apply_hit_if(U32.is_gt(hp, 0), health, hp, score, player_hp,
    accepted, target, time, x, y, color)

def apply_hit(state: Damage, hit: Hit) -> T.Control<Empty, Damage>:
  match state hit:
    case Damage{health, +score, player_hp, accepted}
      Hit{+target, time, x, y, color}:
      apply_hit_after(Array.get(U32, health, target), score, player_hp,
        accepted, target, time, x, y, color)

def damage_rf() -> X.Rf<Hit, Damage,
  T.Reducer{Empty, Damage, Damage,
    state => T.Continue{state}, state => value => apply_hit(state, value),
    state => state}, Damage>:
  X.Rf{state => state}

def damage(initial: Damage, events: Vec.Vec<Hit>) -> Damage:
  X.transduce(X.map(~Hit, ~Hit, ~(x => x)), damage_rf(),
    initial, events)

def initial() -> Damage:
  Damage{Array.new(U32, 8n, 3), 0, 240, []}

def apply_incoming(world: Damage, hits: U32) -> Damage:
  match world:
    case Damage{health, score, +player_hp, accepted}:
      Damage{health, score,
        U32.sub(player_hp, U32.min(player_hp, hits)), accepted}

def step(+frame: U32, world: Damage) -> Damage:
  apply_incoming(damage(world, hits(frame)), incoming(frame))

def simulate(left: Nat, +frame: U32, world: Damage) -> Damage:
  match left:
    case 0n: world
    case 1n+p: simulate(p, U32.inc(frame), step(frame, world))

def score_of(state: Damage) -> U32:
  match state:
    case Damage{health, score, player_hp, accepted}:
      score

def result(frame: U32) -> U32:
  score_of(simulate(U32.to_nat(U32.inc(frame)), 0, initial()))

def hp_of(state: Damage) -> U32:
  match state:
    case Damage{health, score, player_hp, accepted}:
      player_hp

def remaining_shield(frame: U32) -> U32:
  hp_of(simulate(U32.to_nat(U32.inc(frame)), 0, initial()))

# Every visible sprite is a reducible rectangle. The filter below clips it to
# a circle and the screen, and the mapper computes a smooth radial glow.
def sprite_pixels(sprite: Sprite) -> SpritePixels:
  SpritePixels{sprite}

def pixel_at(+sprite: Sprite, +slot: U32) -> PixelSample:
  match sprite:
    case Sprite{+x, +y, +radius, color}:
      +width = U32.add(U32.mul(radius, 2), 1)
      +px = U32.sub(U32.add(F32.to_u32(x), U32.mod(slot, width)), radius)
      +py = U32.sub(U32.add(F32.to_u32(y), U32.div(slot, width)), radius)
      PixelSample{sprite, px, py}

def sprite_pixels_loop(~K: Data, ~S: Type,
  ~advance: S -> PixelSample -> S,
  ~inspect: S -> T.Checked<K, S>, +sprite: Sprite,
  +total: U32, +remaining: Nat, checked: T.Checked<K, S>) -> S:
  match remaining checked:
    case n T.Halted{permit, state}: state
    case 0n T.Ready{state}: state
    case 1n+p T.Ready{state}:
      sprite_pixels_loop(~K, ~S, ~advance, ~inspect, sprite, total, p,
        inspect(advance(state,
          pixel_at(sprite, U32.sub(total, U32.from_nat(1n+p))))))

def sprite_pixels_source(~K: Data, ~S: Type,
  ~advance: S -> PixelSample -> S,
  ~inspect: S -> T.Checked<K, S>, source: SpritePixels,
  state: S) -> S:
  match source:
    case SpritePixels{sprite}:
      match sprite:
        case Sprite{x, y, +radius, color}:
          +width = U32.add(U32.mul(radius, 2), 1)
          +total = U32.mul(width, width)
          sprite_pixels_loop(~K, ~S, ~advance, ~inspect,
            sprite, total, U32.to_nat(total), inspect(state))

def SpritePixels.adapter() -> T.SourceAdapter<PixelSample, SpritePixels,
  (K => S => advance => inspect => ys => state =>
    sprite_pixels_source(~K, ~S, ~advance, ~inspect, ys, state))>:
  T.SourceAdapter{}

def covered(sample: PixelSample) -> Bool:
  match sample:
    case PixelSample{sprite, +x, +y}:
      match sprite:
        case Sprite{cx, cy, +radius, color}:
          +dx = F32.sub(U32.to_f32(x), cx)
          +dy = F32.sub(U32.to_f32(y), cy)
          Bool.and(Bool.and(U32.is_lt(x, 512), U32.is_lt(y, 512)),
            F32.is_le(F32.add(F32.mul(dx, dx), F32.mul(dy, dy)),
              F32.mul(U32.to_f32(radius), U32.to_f32(radius))))

def measure_pixel(sample: PixelSample) -> MeasuredPixel:
  match sample:
    case PixelSample{sprite, +x, +y}:
      match sprite:
        case Sprite{+cx, +cy, +radius, color}:
          +dx = F32.sub(U32.to_f32(x), cx)
          +dy = F32.sub(U32.to_f32(y), cy)
          MeasuredPixel{x, y, color,
            F32.add(F32.mul(dx, dx), F32.mul(dy, dy)),
            F32.mul(U32.to_f32(radius), U32.to_f32(radius))}

def covered_measured(sample: MeasuredPixel) -> Bool:
  match sample:
    case MeasuredPixel{+x, +y, color, +distance2, +radius2}:
      Bool.and(Bool.and(U32.is_lt(x, 512), U32.is_lt(y, 512)),
        F32.is_le(distance2, radius2))

def red(color: U32) -> U32:
  U32.and(U32.shrn(color, 16n), 255)

def green(color: U32) -> U32:
  U32.and(U32.shrn(color, 8n), 255)

def blue(color: U32) -> U32:
  U32.and(color, 255)

def rgb(r: U32, g: U32, b: U32) -> U32:
  U32.or(U32.or(U32.shln(U32.min(r, 255), 16n),
    U32.shln(U32.min(g, 255), 8n)), U32.min(b, 255))

def blend(+a: U32, +b: U32) -> U32:
  rgb(U32.add(red(a), red(b)), U32.add(green(a), green(b)),
    U32.add(blue(a), blue(b)))

def scale_channel(channel: U32, intensity: F32) -> U32:
  F32.to_u32(F32.mul(U32.to_f32(channel), intensity))

def pixel_ink(sample: PixelSample) -> Ink:
  match sample:
    case PixelSample{sprite, +x, +y}:
      match sprite:
        case Sprite{cx, cy, +radius, +color}:
          +dx = F32.sub(U32.to_f32(x), cx)
          +dy = F32.sub(U32.to_f32(y), cy)
          +r2 = F32.mul(U32.to_f32(radius), U32.to_f32(radius))
          +falloff = F32.max(0.0,
            F32.sub(1.0, F32.div(F32.add(F32.mul(dx, dx),
              F32.mul(dy, dy)), F32.max(r2, 1.0))))
          +intensity = F32.mul(falloff, falloff)
          Ink{U32.add(x, U32.mul(y, 512)),
            rgb(scale_channel(red(color), intensity),
              scale_channel(green(color), intensity),
              scale_channel(blue(color), intensity))}

def pixel_ink_measured(sample: MeasuredPixel) -> Ink:
  match sample:
    case MeasuredPixel{+x, +y, +color, +distance2, +radius2}:
      +falloff = F32.max(0.0,
        F32.sub(1.0, F32.div(distance2, F32.max(radius2, 1.0))))
      +intensity = F32.mul(falloff, falloff)
      Ink{U32.add(x, U32.mul(y, 512)),
        rgb(scale_channel(red(color), intensity),
          scale_channel(green(color), intensity),
          scale_channel(blue(color), intensity))}

def ink_after(got: Array<U32> & U32, index: U32, color: U32) ->
  T.Control<Empty, Array<U32>>:
  (framebuffer, old) = got
  T.Continue{Array.set(U32, framebuffer, index, blend(old, color))}

def ink_step(framebuffer: Array<U32>, ink: Ink) ->
  T.Control<Empty, Array<U32>>:
  match ink:
    case Ink{+index, color}:
      ink_after(Array.get(U32, framebuffer, index), index, color)

def ink_reducer() -> T.Reducer<Ink, Array<U32>>:
  T.Reducer{Empty, Array<U32>, Array<U32>,
    image => T.Continue{image}, image => ink => ink_step(image, ink),
    image => image}

def ink_rf() -> X.Rf<Ink, Array<U32>, ink_reducer(), Array<U32>>:
  X.Rf{image => image}

def draw_sprites(framebuffer: Array<U32>, sprites: List<Sprite>) ->
  Array<U32>:
  X.transduce(X.comp4(
    X.map(~Sprite, ~SpritePixels, ~sprite_pixels),
    X.cat(SpritePixels.adapter()),
    X.filter(~PixelSample, ~covered),
    X.map(~PixelSample, ~Ink, ~pixel_ink)),
    ink_rf(), framebuffer, sprites)

def bullet_sprite(bullet: Bullet) -> Sprite:
  match bullet:
    case Bullet{id, frame, x, y, old_x, old_y, radius, color, friendly}:
      Sprite{x, y, 4, color}

def draw_bullets(framebuffer: Array<U32>, +frame: U32) -> Array<U32>:
  X.transduce(X.comp2(X.comp5(
    X.map_with(~U32, ~Bullet, ~U32, ~bullet_at, frame),
    X.filter(~Bullet, ~onscreen),
    X.map(~Bullet, ~Sprite, ~bullet_sprite),
    X.map(~Sprite, ~SpritePixels, ~sprite_pixels),
    X.cat(SpritePixels.adapter())),
    X.comp3(X.map(~PixelSample, ~MeasuredPixel, ~measure_pixel),
      X.filter(~MeasuredPixel, ~covered_measured),
      X.map(~MeasuredPixel, ~Ink, ~pixel_ink_measured))),
    ink_rf(), framebuffer, active_ids(frame))

def hit_sprite_go(+frame: U32, hit: Hit) -> Sprite:
  match hit:
    case Hit{target, +time, x, y, color}:
      +age = U32.sub(frame, time)
      +power = U32.div(255, U32.add(age, 1))
      Sprite{x, y, U32.add(3, U32.min(age, 10)),
        rgb(power, U32.div(U32.mul(power, 2), 3),
          U32.div(power, 3))}

def hit_sprite(frame: U32, hit: Hit) -> Sprite:
  hit_sprite_go(frame, hit)

def sprite_active(sprite: Sprite) -> Bool:
  match sprite:
    case Sprite{x, y, radius, color}: U32.is_gt(red(color), 18)

def owned_hits(xs: List<&2, Hit>) -> List<Hit>:
  match xs:
    case Nil{}: []
    case Con{h, t}: h <> owned_hits(t)

def draw_hits(framebuffer: Array<U32>, hits: List<&2, Hit>, frame: U32) ->
  Array<U32>:
  X.transduce(X.comp2(X.comp5(
    X.map_with(~Hit, ~Sprite, ~U32, ~hit_sprite, frame),
    X.filter(~Sprite, ~sprite_active),
    X.map(~Sprite, ~SpritePixels, ~sprite_pixels),
    X.cat(SpritePixels.adapter()),
    X.filter(~PixelSample, ~covered)),
    X.map(~PixelSample, ~Ink, ~pixel_ink)),
    ink_rf(), framebuffer, owned_hits(hits))

def drone_sprite(+frame: U32, index: Nat, +hp: U32) -> Sprite:
  +cell = U32.from_nat(index)
  +cx = U32.and(cell, 15)
  +cy = U32.shrn(cell, 4n)
  Sprite{enemy_x(frame, cx, cy), enemy_y(frame, cx, cy),
    8, rgb(U32.mul(hp, 24), U32.mul(hp, 52), 180)}

def drone_if(frame: U32, index: Nat, hp: U32, alive: Bool) ->
  Maybe<Sprite>:
  match alive:
    case False{}: None{}
    case True{}: Some{drone_sprite(frame, index, hp)}

def drone_at(frame: U32, index: Nat, +hp: U32) -> Maybe<Sprite>:
  drone_if(frame, index, hp, U32.is_gt(hp, 0))

def indexed_health(index: Nat, hp: U32) -> IndexedHealth:
  IndexedHealth{index, hp}

def drone_from_pair(frame: U32, pair: IndexedHealth) -> Maybe<Sprite>:
  match pair:
    case IndexedHealth{index, hp}: drone_at(frame, index, hp)

def draw_drones(framebuffer: Array<U32>, health: Array<U32>, frame: U32) ->
  Array<U32>:
  X.transduce(X.comp2(X.comp5(
    X.map_indexed(~U32, ~IndexedHealth, ~indexed_health),
    X.map_with(~IndexedHealth, ~Maybe<Sprite>, ~U32,
      ~drone_from_pair, frame),
    X.keep(~Maybe<Sprite>, ~Sprite, ~(x => x)),
    X.map(~Sprite, ~SpritePixels, ~sprite_pixels),
    X.cat(SpritePixels.adapter())),
    X.comp2(X.filter(~PixelSample, ~covered),
      X.map(~PixelSample, ~Ink, ~pixel_ink))),
    ink_rf(), framebuffer, health)

def icons(+frame: U32, score: U32, player_hp: U32) -> List<Sprite>:
  +core = Bool.pick(U32, U32.is_ge(score, 192), 16727887, 16759065)
  +ship = Bool.pick(U32, U32.is_lt(player_hp, 80), 16737792, 16639)
  +ship_x = player_x(frame)
  Sprite{256.0, 150.0, 33, 5571584} <>
  Sprite{256.0, 150.0, 23, core} <>
  Sprite{256.0, 150.0, 10, 16777215} <>
  Sprite{ship_x, 480.0, 13, ship} <>
  Sprite{F32.sub(ship_x, 12.0), 489.0, 7, 45055} <>
  Sprite{F32.add(ship_x, 12.0), 489.0, 7, 45055} <>
  Sprite{ship_x, 497.0, 6, 65535} <> []

def hud_cell_go(+score: U32, player_hp: U32, +index: U32) -> HudCell:
  +x = U32.and(index, 511)
  +y = U32.shrn(index, 9n)
  +boss_bar = Bool.and(U32.is_ge(x, 16),
    U32.is_lt(x, U32.add(16, U32.min(220, score))))
  +player_bar = Bool.and(U32.is_ge(x, 290),
    U32.is_lt(x, U32.add(290, U32.min(206, player_hp))))
  HudCell{index, Bool.and(Bool.or(boss_bar, player_bar),
    Bool.and(U32.is_ge(y, 7), U32.is_lt(y, 11)))}

def hud_cell(config: HudState, +index: U32) -> HudCell:
  match config:
    case HudState{score, player_hp}:
      hud_cell_go(score, player_hp, index)

def hud_at(config: HudState, index: U32) -> HudCell:
  hud_cell(config, index)

def hud_lit(cell: HudCell) -> Bool:
  match cell:
    case HudCell{index, lit}: lit

def hud_ink(cell: HudCell) -> Ink:
  match cell:
    case HudCell{+index, lit}:
      Ink{index, Bool.pick(U32, U32.is_lt(U32.and(index, 511), 256),
        16757920, 45055)}

def draw_hud(framebuffer: Array<U32>, score: U32,
  player_hp: U32) -> Array<U32>:
  X.transduce(X.comp3(
    X.map_with(~U32, ~HudCell, ~HudState, ~hud_at,
      HudState{score, player_hp}),
    X.filter(~HudCell, ~hud_lit),
    X.map(~HudCell, ~Ink, ~hud_ink)),
    ink_rf(), framebuffer, T.range(6144))

def sky(+index: U32) -> Ink:
  +x = U32.and(index, 511)
  +y = U32.shrn(index, 9n)
  +dx = U32.sub(U32.max(x, 256), U32.min(x, 256))
  +dy = U32.sub(U32.max(y, 150), U32.min(y, 150))
  +dist = U32.add(U32.mul(dx, dx), U32.mul(dy, dy))
  +aura = U32.div(24000, U32.add(U32.shrn(dist, 8n), 180))
  +grid = U32.is_eq(U32.and(x, 31), 0)
  +grid2 = U32.is_eq(U32.and(y, 31), 0)
  +line = Bool.pick(U32, Bool.or(grid, grid2), 5, 0)
  +hash = U32.xor(U32.mul(x, 2654435761), U32.mul(y, 2246822507))
  +star = Bool.pick(U32, U32.is_lt(U32.and(hash, 4095), 3), 60, 0)
  Ink{index, rgb(U32.add(7, U32.add(U32.shrn(aura, 1n), line)),
    U32.add(8, U32.add(aura, star)),
    U32.add(25, U32.add(U32.mul(aura, 2), U32.add(line, star))))}

def sky_at(index: U32) -> Ink:
  sky(index)

def sky_color_after(ink: Ink) -> U32:
  match ink:
    case Ink{index, color}: color

def sky_color(index: U32) -> U32:
  sky_color_after(sky(index))

def background() -> Array<U32>:
  Array.fill(~U32, ~sky_color, Array.new(U32, 18n, 0))

def draw_frame(world: Damage, +frame: U32) -> Array<U32>:
  match world:
    case Damage{health, +score, +player_hp, accepted}:
      bullets_image = draw_bullets(background(), frame)
      drones_image = draw_drones(bullets_image, health, frame)
      hits_image = draw_hits(drones_image, accepted, frame)
      icons_image = draw_sprites(hits_image,
        icons(frame, score, player_hp))
      draw_hud(icons_image, score, player_hp)

def rendered(+frame: U32) -> Array<U32>:
  draw_frame(simulate(U32.to_nat(U32.inc(frame)), 0, initial()), frame)

def same_u32(value: U32) -> U32:
  value

def render_copy_after(pair: Array<U32> & Array<U32>,
  +score: U32, +player_hp: U32, +accepted: List<&2, Hit>, frame: U32) -> Held:
  (keep_health, draw_health) = pair
  image = draw_frame(Damage{draw_health, score, player_hp, accepted}, frame)
  Held{Damage{keep_health, score, player_hp, accepted}, image}

def render_copy(world: Damage, frame: U32) -> Held:
  match world:
    case Damage{health, +score, +player_hp, accepted}:
      render_copy_after(Array.clone(U32, health), score, player_hp,
        accepted, frame)

def pixels_checksum(pixels: Array<U32>) -> U32:
  X.transduce(X.map(~U32, ~U32, ~same_u32), X.sum_rf(), 0, pixels)

def run_frames(left: Nat, +frame: U32,
  previous: Held, acc: U32) -> U32:
  match left previous:
    case 0n Held{world, pixels}:
      U32.add(acc, pixels_checksum(pixels))
    case 1n+p Held{world, pixels}:
      run_frames(p, U32.inc(frame),
        render_copy(step(frame, world), frame),
        U32.add(acc, pixels_checksum(pixels)))

def dump(frame: U32) -> IO(Unit):
  IO.print(List.show(~&1, ~U32, ~U32.show,
    Array.to_list(~U32, rendered(frame))))

def frame_checksum(frame: U32) -> U32:
  pixels_checksum(rendered(frame))

def parsed_u32(value: Maybe<&2, U32>) -> U32:
  match value:
    case None{}: 0
    case Some{n}: n

def parsed_nat(value: Maybe<&2, Nat>) -> Nat:
  match value:
    case None{}: 0n
    case Some{n}: n

def dispatch(mode: Nat, frame: U32) -> IO(Unit):
  match mode:
    case 1n: IO.print(U32.show(result(frame)))
    case 2n: IO.print(U32.show(remaining_shield(frame)))
    case _: dump(frame)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case count <> mode <> extra <> rest:
      do IO<Unit>:
        before : Nat <- Clock.now_us()
        checksum : U32 <- IO.pure(U32,
          run_frames(U32.to_nat(parsed_u32(U32.read(count))), 0,
            Held{initial(), Array.new(U32, 18n, 0)}, 0))
        after : Nat <- Clock.now_us()
        IO.print(Nat.show(Nat.sub(after, before)) ++ " " ++
          U32.show(checksum))
    case frame <> mode <> rest:
      dispatch(parsed_nat(Nat.read(mode)), parsed_u32(U32.read(frame)))
    case frame <> rest:
      do IO<Unit>:
        before : Nat <- Clock.now_us()
        score : U32 <- IO.pure(U32,
          frame_checksum(parsed_u32(U32.read(frame))))
        after : Nat <- Clock.now_us()
        IO.print(Nat.show(Nat.sub(after, before)) ++ " " ++ U32.show(score))
    case _: IO.print(U32.show(frame_checksum(48)))

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
