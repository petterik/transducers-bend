#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

typedef struct {
  unsigned shift;
  uint32_t width, pixel_mask, sub_mask, offset_x, offset_y;
} render_t;

static uint64_t now_us(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return (uint64_t)t.tv_sec * 1000000u + (uint64_t)t.tv_nsec / 1000u;
}

static render_t settings(unsigned depth, uint32_t frame) {
  uint32_t width = 1u << depth;
  return (render_t){depth, width, width - 1u, 2u * width - 1u,
    3u * frame, frame};
}

static uint32_t cell_hash(uint32_t x, uint32_t y) {
  uint32_t a = x * 2654435761u ^ y * 2246822507u;
  uint32_t b = a ^ (a >> 16u);
  uint32_t c = b * 3266489909u;
  return c ^ (c >> 15u);
}

static uint32_t distance(uint32_t a, uint32_t b) {
  return a < b ? b - a : a - b;
}

static uint32_t star_light(uint32_t gx, uint32_t gy) {
  uint32_t hash = cell_hash(gx >> 5u, gy >> 5u);
  uint32_t dx = distance(gx & 31u, hash & 31u);
  uint32_t dy = distance(gy & 31u, (hash >> 5u) & 31u);
  uint32_t radius = dx * dx + dy * dy;
  if (radius > 8u) return 0u;
  uint32_t strength = 128u + ((hash >> 18u) & 127u);
  return ((9u - radius) * strength) >> 3u;
}

static uint32_t sample(render_t cfg, uint32_t id) {
  uint32_t pixel = id >> 2u;
  uint32_t x = pixel & cfg.pixel_mask;
  uint32_t y = pixel >> cfg.shift;
  uint32_t sx = id & 1u;
  uint32_t sy = (id >> 1u) & 1u;
  uint32_t gx = ((2u * x + sx) + cfg.offset_x) & cfg.sub_mask;
  uint32_t gy = ((2u * y + sy) + cfg.offset_y) & cfg.sub_mask;
  return star_light(gx, gy);
}

static inline __attribute__((always_inline))
uint32_t shade(render_t cfg, uint32_t pixel) {
  uint32_t base = 4u * pixel;
  uint32_t a = sample(cfg, base);
  uint32_t b = sample(cfg, base + 1u);
  uint32_t c = sample(cfg, base + 2u);
  uint32_t d = sample(cfg, base + 3u);
  uint32_t gray = ((a + b) + (c + d)) >> 2u;
  return gray < 255u ? gray : 255u;
}

int main(int argc, char **argv) {
  if (argc != 3 && argc != 4) {
    fprintf(stderr, "usage: %s depth frame [ppm-path]\n", argv[0]);
    return 2;
  }
  unsigned depth = (unsigned)strtoul(argv[1], NULL, 10);
  uint32_t frame = (uint32_t)strtoul(argv[2], NULL, 10);
  if (depth < 1 || depth > 10) {
    fputs("depth must be 1..10\n", stderr);
    return 2;
  }
  render_t cfg = settings(depth, frame);
  uint32_t pixels = cfg.width * cfg.width;
  uint64_t before = now_us();
  uint32_t total = 0;
  for (uint32_t pixel = 0; pixel < pixels; ++pixel) {
    uint32_t gray = shade(cfg, pixel);
    if (gray > 0u) total += gray;
  }
  uint64_t elapsed = now_us() - before;
  if (argc == 4) {
    FILE *ppm = fopen(argv[3], "wb");
    if (!ppm) { perror("fopen"); return 1; }
    fprintf(ppm, "P6\n%u %u\n255\n", cfg.width, cfg.width);
    for (uint32_t pixel = 0; pixel < pixels; ++pixel) {
      uint32_t gray = shade(cfg, pixel);
      unsigned char g = (unsigned char)gray;
      unsigned char rgb[3] = {g, g, g};
      if (fwrite(rgb, sizeof(rgb), 1, ppm) != 1) {
        perror("fwrite"); fclose(ppm); return 1;
      }
    }
    if (fclose(ppm) != 0) { perror("fclose"); return 1; }
  }
  printf("%llu %u\n", (unsigned long long)elapsed, total);
  return 0;
}
