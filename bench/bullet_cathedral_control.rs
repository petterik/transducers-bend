// Rust control for the 512x512 Bullet Cathedral Bend scene.
use std::time::Instant;

const SIDE: usize = 512;
const CELLS: usize = 256;
const PIXELS: usize = SIDE * SIDE;

#[derive(Clone, Copy)]
struct Bullet {
    x: f32, y: f32, ox: f32, oy: f32,
    radius: f32, color: u32, friendly: bool,
}
#[derive(Clone, Copy)]
struct Sprite { x: f32, y: f32, radius: u32, color: u32 }
#[derive(Clone, Copy)]
struct Hit { target: usize, time: u32, x: f32, y: f32, color: u32 }
struct World {
    health: [u32; CELLS], score: u32, player_hp: u32,
    accepted: Vec<Hit>,
}
impl World {
    fn new() -> Self {
        Self { health: [3; CELLS], score: 0, player_hp: 240,
               accepted: Vec::new() }
    }
}

#[inline] fn sin(x: f32) -> f32 { (x as f64).sin() as f32 }
#[inline] fn cos(x: f32) -> f32 { (x as f64).cos() as f32 }
#[inline] fn rgb(r: u32, g: u32, b: u32) -> u32 {
    r.min(255) << 16 | g.min(255) << 8 | b.min(255)
}
#[inline] fn red(c: u32) -> u32 { (c >> 16) & 255 }
#[inline] fn green(c: u32) -> u32 { (c >> 8) & 255 }
#[inline] fn blue(c: u32) -> u32 { c & 255 }
#[inline] fn blend(a: u32, b: u32) -> u32 {
    rgb(red(a) + red(b), green(a) + green(b), blue(a) + blue(b))
}
#[inline] fn player_x(frame: u32) -> f32 {
    256.0 + sin(frame as f32 * 0.08) * 90.0
}
fn bullet_at(frame: u32, id: u32) -> Bullet {
    let spoke = id & 127;
    let birth = id >> 7;
    let age = frame - birth;
    let phase = birth & 3;
    let angle = spoke as f32 * 0.049087385 + birth as f32 * 0.105;
    if spoke & 3 == 0 {
        let base_x = 256.0 + ((spoke as f32 - 64.0) * 1.25
                            + sin(birth as f32 * 0.17) * 34.0);
        let drift = sin(angle) * 0.65;
        let x = base_x + age as f32 * drift;
        let y = 500.0 - age as f32 * 6.0;
        Bullet { x, y, ox: x - drift, oy: y + 6.0,
                 radius: 2.0, color: 4521983, friendly: true }
    } else {
        let speed = 2.7 + phase as f32 * 0.45;
        let turn = angle + age as f32 * (phase as f32 * 0.006);
        let vx = speed * cos(turn);
        let vy = speed * sin(turn);
        let x = 256.0 + age as f32 * vx;
        let y = 150.0 + age as f32 * vy;
        Bullet { x, y, ox: x - vx, oy: y - vy, radius: 1.8,
                 color: if phase < 2 {16722617} else {16745284},
                 friendly: false }
    }
}
#[inline] fn onscreen(b: Bullet) -> bool {
    b.x >= 0.0 && b.x < 512.0 && b.y >= 0.0 && b.y < 512.0
}
#[inline] fn enemy_x(frame: u32, cx: u32, cy: u32) -> f32 {
    let id = cx + cy * 16;
    (cx as f32 * 32.0 + 16.0)
        + sin(frame as f32 * 0.055 + id as f32 * 0.27) * 5.0
}
#[inline] fn enemy_y(frame: u32, cx: u32, cy: u32) -> f32 {
    let id = cx + cy * 16;
    (cy as f32 * 32.0 + 16.0)
        + cos(frame as f32 * 0.04 + id as f32 * 0.31) * 5.0
}
#[inline] fn swept(b: Bullet, ex: f32, ey: f32, radius2: f32) -> bool {
    let vx = b.x - b.ox;
    let vy = b.y - b.oy;
    let den = vx * vx + vy * vy;
    let ratio = ((ex - b.ox) * vx + (ey - b.oy) * vy) / den.max(0.0001);
    let t = ratio.max(0.0).min(1.0);
    let dx = ex - (b.ox + t * vx);
    let dy = ey - (b.oy + t * vy);
    dx * dx + dy * dy <= radius2
}
#[inline] fn player_entered(frame: u32, b: Bullet) -> bool {
    if !swept(b, player_x(frame), 480.0, 118.81) { return false; }
    let dx = b.ox - player_x(frame - frame.min(1));
    let dy = b.oy - 480.0;
    dx * dx + dy * dy > 118.81
}
fn step(world: &mut World, frame: u32) {
    let begin = (frame - frame.min(95)) * 128;
    let end = (frame + 1) * 128;
    let mut events: Vec<Hit> = Vec::new();
    let mut incoming = 0;
    for id in begin..end {
        let b = bullet_at(frame, id);
        if b.friendly {
            if !onscreen(b) { continue; }
            let cx = (b.x as u32) >> 5;
            let cy = (b.y as u32) >> 5;
            for slot in 0u32..9 {
                let tx = cx.wrapping_add(slot % 3).wrapping_sub(1);
                let ty = cy.wrapping_add(slot / 3).wrapping_sub(1);
                if tx >= 16 || ty >= 16 { continue; }
                if swept(b, enemy_x(frame, tx, ty), enemy_y(frame, tx, ty),
                         (b.radius + 7.0) * (b.radius + 7.0)) {
                    events.push(Hit { target: (tx + ty * 16) as usize,
                                      time: frame, x: b.x, y: b.y,
                                      color: b.color });
                }
            }
        } else if player_entered(frame, b) {
            incoming += 1;
        }
    }
    for hit in events {
        if world.health[hit.target] > 0 {
            world.health[hit.target] -= 1;
            world.score += 1;
            world.accepted.push(hit);
        }
    }
    world.player_hp -= world.player_hp.min(incoming);
}
#[inline] fn ink(pixels: &mut [u32], index: usize, color: u32) {
    pixels[index] = blend(pixels[index], color);
}
fn draw_sprite(pixels: &mut [u32], s: Sprite) {
    let width = s.radius * 2 + 1;
    let origin_x = s.x as u32;
    let origin_y = s.y as u32;
    for slot in 0..width * width {
        let x = origin_x.wrapping_add(slot % width).wrapping_sub(s.radius);
        let y = origin_y.wrapping_add(slot / width).wrapping_sub(s.radius);
        if x >= SIDE as u32 || y >= SIDE as u32 { continue; }
        let dx = x as f32 - s.x;
        let dy = y as f32 - s.y;
        let r2 = s.radius as f32 * s.radius as f32;
        if dx * dx + dy * dy > r2 { continue; }
        let falloff = (1.0 - (dx * dx + dy * dy) / r2.max(1.0)).max(0.0);
        let intensity = falloff * falloff;
        let color = rgb((red(s.color) as f32 * intensity) as u32,
                        (green(s.color) as f32 * intensity) as u32,
                        (blue(s.color) as f32 * intensity) as u32);
        ink(pixels, (x + y * SIDE as u32) as usize, color);
    }
}
fn sky(index: u32) -> u32 {
    let x = index & 511;
    let y = index >> 9;
    let dx = x.max(256) - x.min(256);
    let dy = y.max(150) - y.min(150);
    let dist = dx * dx + dy * dy;
    let aura = 24000 / ((dist >> 8) + 180);
    let line = if x & 31 == 0 || y & 31 == 0 {5} else {0};
    let hash = x.wrapping_mul(2_654_435_761) ^ y.wrapping_mul(2_246_822_507);
    let star = if hash & 4095 < 3 {60} else {0};
    rgb(7 + (aura >> 1) + line, 8 + aura + star,
        25 + aura * 2 + line + star)
}
fn render(world: &World, frame: u32, pixels: &mut [u32]) -> u32 {
    for (i, pixel) in pixels.iter_mut().enumerate() { *pixel = sky(i as u32); }
    let begin = (frame - frame.min(95)) * 128;
    for id in begin..(frame + 1) * 128 {
        let b = bullet_at(frame, id);
        if onscreen(b) {
            draw_sprite(pixels, Sprite { x: b.x, y: b.y, radius: 4,
                                         color: b.color });
        }
    }
    for i in 0..CELLS {
        let hp = world.health[i];
        if hp == 0 { continue; }
        let cx = i as u32 & 15;
        let cy = i as u32 >> 4;
        draw_sprite(pixels, Sprite { x: enemy_x(frame, cx, cy),
            y: enemy_y(frame, cx, cy), radius: 8,
            color: rgb(hp * 24, hp * 52, 180) });
    }
    for h in world.accepted.iter().rev() {
        let age = frame - h.time;
        let power = 255 / (age + 1);
        let s = Sprite { x: h.x, y: h.y, radius: 3 + age.min(10),
                         color: rgb(power, power * 2 / 3, power / 3) };
        if red(s.color) > 18 { draw_sprite(pixels, s); }
    }
    let core = if world.score >= 192 {16727887} else {16759065};
    let ship = if world.player_hp < 80 {16737792} else {16639};
    let ship_x = player_x(frame);
    let icons = [
        Sprite {x: 256.0, y: 150.0, radius: 33, color: 5571584},
        Sprite {x: 256.0, y: 150.0, radius: 23, color: core},
        Sprite {x: 256.0, y: 150.0, radius: 10, color: 16777215},
        Sprite {x: ship_x, y: 480.0, radius: 13, color: ship},
        Sprite {x: ship_x - 12.0, y: 489.0, radius: 7, color: 45055},
        Sprite {x: ship_x + 12.0, y: 489.0, radius: 7, color: 45055},
        Sprite {x: ship_x, y: 497.0, radius: 6, color: 65535},
    ];
    for s in icons { draw_sprite(pixels, s); }
    for i in 0u32..6144 {
        let x = i & 511;
        let y = i >> 9;
        let boss = x >= 16 && x < 16 + world.score.min(220);
        let player = x >= 290 && x < 290 + world.player_hp.min(206);
        if (boss || player) && y >= 7 && y < 11 {
            ink(pixels, i as usize, if x < 256 {16757920} else {45055});
        }
    }
    pixels.iter().copied().fold(0u32, u32::wrapping_add)
}
pub fn main() {
    let mut args = std::env::args().skip(1);
    let count: u32 = args.next().unwrap().parse().unwrap();
    assert!(count <= 240);
    let mode = args.next();
    assert!(args.next().is_none());
    let fresh = mode.as_deref() == Some("new");
    #[cfg(alloc_meter)]
    crate::alloc_meter::start();
    let before = Instant::now();
    let mut world = World::new();
    let mut pixels = if fresh {Vec::new()} else {vec![0u32; PIXELS]};
    let mut sum = 0u32;
    for frame in 0..count {
        if fresh {pixels = vec![0u32; PIXELS];}
        step(&mut world, frame);
        let checksum = render(&world, frame, &mut pixels);
        sum = sum.wrapping_add(checksum);
        if mode.as_deref() == Some("frames") {
            println!("{checksum} {} {}", world.score, world.player_hp);
        }
        if fresh {pixels = Vec::new();}
    }
    let score = world.score;
    let player_hp = world.player_hp;
    drop(pixels);
    drop(world);
    let elapsed = before.elapsed().as_micros();
    #[cfg(alloc_meter)]
    eprintln!("TIMED_ALLOC {}", crate::alloc_meter::stop());
    if mode.as_deref() == Some("frames") {
        // Per-frame output was emitted in the loop.
    } else if mode.as_deref() == Some("stats") {
        println!("{score} {player_hp}");
    } else {
        println!("{elapsed} {sum}");
    }
}
