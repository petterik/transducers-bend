// Handwritten C control for the 512x512 Bullet Cathedral Bend scene.
#include <inttypes.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

enum { SIDE = 512, CELLS = 256, PIXELS = SIDE * SIDE };
typedef struct { float x, y, ox, oy, radius; uint32_t color; bool friendly; } Bullet;
typedef struct { float x, y; uint32_t radius, color; } Sprite;
typedef struct { uint32_t target, time; float x, y; uint32_t color; } Hit;
typedef struct {
  uint32_t health[CELLS], score, player_hp;
  Hit accepted[CELLS * 3];
  size_t accepted_len;
} World;

static uint64_t now_us(void) {
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) abort();
  return (uint64_t)ts.tv_sec * 1000000u + (uint64_t)ts.tv_nsec / 1000u;
}
static inline uint32_t umin(uint32_t a, uint32_t b) { return a < b ? a : b; }
static inline uint32_t umax(uint32_t a, uint32_t b) { return a > b ? a : b; }
static inline uint32_t rgb(uint32_t r, uint32_t g, uint32_t b) {
  return (umin(r, 255) << 16) | (umin(g, 255) << 8) | umin(b, 255);
}
static inline uint32_t red(uint32_t c) { return (c >> 16) & 255; }
static inline uint32_t green(uint32_t c) { return (c >> 8) & 255; }
static inline uint32_t blue(uint32_t c) { return c & 255; }
static inline uint32_t blend(uint32_t a, uint32_t b) {
  return rgb(red(a) + red(b), green(a) + green(b), blue(a) + blue(b));
}
static inline float bend_sin(float x) { return (float)sin((double)x); }
static inline float bend_cos(float x) { return (float)cos((double)x); }
static inline float player_x(uint32_t frame) {
  return 256.0f + bend_sin((float)frame * 0.08f) * 90.0f;
}
static Bullet bullet_at(uint32_t frame, uint32_t id) {
  uint32_t spoke = id & 127, birth = id >> 7, age = frame - birth;
  uint32_t phase = birth & 3;
  float angle = (float)spoke * 0.049087385f + (float)birth * 0.105f;
  if ((spoke & 3) == 0) {
    float base_x = 256.0f + (((float)spoke - 64.0f) * 1.25f
      + bend_sin((float)birth * 0.17f) * 34.0f);
    float drift = bend_sin(angle) * 0.65f;
    float x = base_x + (float)age * drift;
    float y = 500.0f - (float)age * 6.0f;
    return (Bullet){x, y, x - drift, y + 6.0f, 2.0f, 4521983, true};
  }
  float speed = 2.7f + (float)phase * 0.45f;
  float turn = angle + (float)age * ((float)phase * 0.006f);
  float vx = speed * bend_cos(turn), vy = speed * bend_sin(turn);
  float x = 256.0f + (float)age * vx;
  float y = 150.0f + (float)age * vy;
  return (Bullet){x, y, x - vx, y - vy, 1.8f,
    phase < 2 ? 16722617 : 16745284, false};
}
static inline bool onscreen(Bullet b) {
  return b.x >= 0.0f && b.x < 512.0f && b.y >= 0.0f && b.y < 512.0f;
}
static inline float enemy_x(uint32_t frame, uint32_t cx, uint32_t cy) {
  uint32_t id = cx + cy * 16;
  return (float)cx * 32.0f + 16.0f
    + bend_sin((float)frame * 0.055f + (float)id * 0.27f) * 5.0f;
}
static inline float enemy_y(uint32_t frame, uint32_t cx, uint32_t cy) {
  uint32_t id = cx + cy * 16;
  return (float)cy * 32.0f + 16.0f
    + bend_cos((float)frame * 0.04f + (float)id * 0.31f) * 5.0f;
}
static inline bool swept(Bullet b, float ex, float ey, float radius2) {
  float vx = b.x - b.ox, vy = b.y - b.oy;
  float den = vx * vx + vy * vy;
  float ratio = ((ex - b.ox) * vx + (ey - b.oy) * vy)
    / fmaxf(den, 0.0001f);
  float t = fmaxf(0.0f, fminf(ratio, 1.0f));
  float dx = ex - (b.ox + t * vx), dy = ey - (b.oy + t * vy);
  return dx * dx + dy * dy <= radius2;
}
static inline bool player_entered(uint32_t frame, Bullet b) {
  if (!swept(b, player_x(frame), 480.0f, 118.81f)) return false;
  float dx = b.ox - player_x(frame - umin(frame, 1));
  float dy = b.oy - 480.0f;
  return dx * dx + dy * dy > 118.81f;
}
static void step(World *world, uint32_t frame) {
  uint32_t begin = (frame - umin(frame, 95)) * 128;
  uint32_t end = (frame + 1) * 128;
  // Bend first collects friendly hits in source order, then reduces them.
  Hit events[9 * 12288];
  size_t event_len = 0;
  uint32_t incoming = 0;
  for (uint32_t id = begin; id < end; ++id) {
    Bullet b = bullet_at(frame, id);
    if (b.friendly) {
      if (!onscreen(b)) continue;
      uint32_t cx = (uint32_t)b.x >> 5, cy = (uint32_t)b.y >> 5;
      for (uint32_t slot = 0; slot < 9; ++slot) {
        uint32_t tx = cx + slot % 3 - 1, ty = cy + slot / 3 - 1;
        if (tx >= 16 || ty >= 16) continue;
        if (swept(b, enemy_x(frame, tx, ty), enemy_y(frame, tx, ty),
                  (b.radius + 7.0f) * (b.radius + 7.0f))) {
          events[event_len++] = (Hit){tx + ty * 16, frame, b.x, b.y, b.color};
        }
      }
    } else if (player_entered(frame, b)) {
      ++incoming;
    }
  }
  for (size_t n = 0; n < event_len; ++n) {
    Hit hit = events[n];
    if (world->health[hit.target] > 0) {
      --world->health[hit.target];
      ++world->score;
      if (world->accepted_len >= CELLS * 3) abort();
      world->accepted[world->accepted_len++] = hit;
    }
  }
  world->player_hp -= umin(world->player_hp, incoming);
}
static inline void ink(uint32_t *pixels, uint32_t index, uint32_t color) {
  pixels[index] = blend(pixels[index], color);
}
static void draw_sprite(uint32_t *pixels, Sprite s) {
  uint32_t width = s.radius * 2 + 1;
  uint32_t origin_x = (uint32_t)s.x, origin_y = (uint32_t)s.y;
  for (uint32_t slot = 0; slot < width * width; ++slot) {
    uint32_t x = origin_x + slot % width - s.radius;
    uint32_t y = origin_y + slot / width - s.radius;
    if (x >= SIDE || y >= SIDE) continue;
    float dx = (float)x - s.x, dy = (float)y - s.y;
    float r2 = (float)s.radius * (float)s.radius;
    if (dx * dx + dy * dy > r2) continue;
    float falloff = fmaxf(0.0f, 1.0f - (dx * dx + dy * dy) / fmaxf(r2, 1.0f));
    float intensity = falloff * falloff;
    uint32_t color = rgb((uint32_t)((float)red(s.color) * intensity),
                         (uint32_t)((float)green(s.color) * intensity),
                         (uint32_t)((float)blue(s.color) * intensity));
    ink(pixels, x + y * SIDE, color);
  }
}
static uint32_t sky(uint32_t index) {
  uint32_t x = index & 511, y = index >> 9;
  uint32_t dx = umax(x, 256) - umin(x, 256);
  uint32_t dy = umax(y, 150) - umin(y, 150);
  uint32_t dist = dx * dx + dy * dy;
  uint32_t aura = 24000 / ((dist >> 8) + 180);
  uint32_t line = ((x & 31) == 0 || (y & 31) == 0) ? 5 : 0;
  uint32_t hash = x * UINT32_C(2654435761) ^ y * UINT32_C(2246822507);
  uint32_t star = (hash & 4095) < 3 ? 60 : 0;
  return rgb(7 + (aura >> 1) + line, 8 + aura + star,
             25 + aura * 2 + line + star);
}
static uint32_t render(World *world, uint32_t frame, uint32_t *pixels) {
  for (uint32_t i = 0; i < PIXELS; ++i) pixels[i] = sky(i);
  uint32_t begin = (frame - umin(frame, 95)) * 128;
  for (uint32_t id = begin; id < (frame + 1) * 128; ++id) {
    Bullet b = bullet_at(frame, id);
    if (onscreen(b)) draw_sprite(pixels, (Sprite){b.x, b.y, 4, b.color});
  }
  for (uint32_t i = 0; i < CELLS; ++i) {
    uint32_t hp = world->health[i];
    if (hp == 0) continue;
    uint32_t cx = i & 15, cy = i >> 4;
    draw_sprite(pixels, (Sprite){enemy_x(frame, cx, cy),
      enemy_y(frame, cx, cy), 8, rgb(hp * 24, hp * 52, 180)});
  }
  for (size_t n = world->accepted_len; n > 0; --n) {
    Hit h = world->accepted[n - 1];
    uint32_t age = frame - h.time;
    uint32_t power = 255 / (age + 1);
    Sprite s = {h.x, h.y, 3 + umin(age, 10),
      rgb(power, power * 2 / 3, power / 3)};
    if (red(s.color) > 18) draw_sprite(pixels, s);
  }
  uint32_t core = world->score >= 192 ? 16727887 : 16759065;
  uint32_t ship = world->player_hp < 80 ? 16737792 : 16639;
  float ship_x = player_x(frame);
  Sprite icons[] = {
    {256, 150, 33, 5571584}, {256, 150, 23, core},
    {256, 150, 10, 16777215}, {ship_x, 480, 13, ship},
    {ship_x - 12, 489, 7, 45055}, {ship_x + 12, 489, 7, 45055},
    {ship_x, 497, 6, 65535},
  };
  for (size_t i = 0; i < sizeof icons / sizeof *icons; ++i)
    draw_sprite(pixels, icons[i]);
  for (uint32_t i = 0; i < 6144; ++i) {
    uint32_t x = i & 511, y = i >> 9;
    bool boss = x >= 16 && x < 16 + umin(220, world->score);
    bool player = x >= 290 && x < 290 + umin(206, world->player_hp);
    if ((boss || player) && y >= 7 && y < 11)
      ink(pixels, i, x < 256 ? 16757920 : 45055);
  }
  uint32_t checksum = 0;
  for (uint32_t i = 0; i < PIXELS; ++i) checksum += pixels[i];
  return checksum;
}
int main(int argc, char **argv) {
  if (argc < 2 || argc > 3) return 2;
  unsigned long count = strtoul(argv[1], NULL, 10);
  if (count > 240) return 2;
  bool fresh = argc == 3 && argv[2][0] == 'n';
  uint64_t before = now_us();
  World world = {.player_hp = 240};
  for (size_t i = 0; i < CELLS; ++i) world.health[i] = 3;
  uint32_t *pixels = fresh ? NULL : malloc((size_t)PIXELS * sizeof *pixels);
  if (!fresh && pixels == NULL) return 3;
  uint32_t sum = 0;
  for (uint32_t frame = 0; frame < count; ++frame) {
    if (fresh) {
      pixels = malloc((size_t)PIXELS * sizeof *pixels);
      if (pixels == NULL) abort();
    }
    step(&world, frame);
    uint32_t checksum = render(&world, frame, pixels);
    sum += checksum;
    if (argc == 3 && argv[2][0] == 'f')
      printf("%" PRIu32 " %" PRIu32 " %" PRIu32 "\n",
             checksum, world.score, world.player_hp);
    if (fresh) free(pixels);
  }
  if (!fresh) free(pixels);
  uint64_t elapsed = now_us() - before;
  if (argc == 3 && argv[2][0] == 'f') {
    // Per-frame output was emitted in the loop.
  } else if (argc == 3 && argv[2][0] == 's') {
    printf("%" PRIu32 " %" PRIu32 "\n", world.score, world.player_hp);
  } else {
    printf("%" PRIu64 " %" PRIu32 "\n", elapsed, sum);
  }
  return 0;
}
