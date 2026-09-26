#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

typedef struct {
  uint32_t width, mask, shift;
  float scale, cx, cy;
} render_t;

static uint64_t now_us(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return (uint64_t)t.tv_sec * 1000000u + (uint64_t)t.tv_nsec / 1000u;
}

static render_t settings(unsigned depth, uint32_t frame) {
  uint32_t width = 1u << depth;
  float phase = (float)frame;
  return (render_t){width, width - 1u, depth, 3.0f / (float)(2u * width),
    (0.0f - 0.74543f) + phase * 0.0001f,
    0.11301f + phase * 0.00007f};
}

static uint32_t sample(render_t cfg, uint32_t id) {
  uint32_t pixel = id >> 2u;
  uint32_t x = pixel & cfg.mask;
  uint32_t y = pixel >> cfg.shift;
  uint32_t sx = id & 1u;
  uint32_t sy = (id >> 1u) & 1u;
  float zx = (float)(2u * x + sx) * cfg.scale - 1.5f;
  float zy = (float)(2u * y + sy) * cfg.scale - 1.5f;
  uint32_t count = 0;
  for (unsigned left = 32; left != 0; --left) {
    if (zx * zx + zy * zy > 4.0f)
      return count;
    float next_x = (zx * zx - zy * zy) + cfg.cx;
    float next_y = (2.0f * (zx * zy)) + cfg.cy;
    zx = next_x;
    zy = next_y;
    ++count;
  }
  return count;
}

static uint32_t shade(render_t cfg, uint32_t pixel) {
  uint32_t base = 4u * pixel;
  uint32_t a = sample(cfg, base);
  uint32_t b = sample(cfg, base + 1u);
  uint32_t c = sample(cfg, base + 2u);
  uint32_t d = sample(cfg, base + 3u);
  return 2u * ((a + b) + (c + d));
}

int main(int argc, char **argv) {
  if (argc != 3 && argc != 4) {
    fprintf(stderr, "usage: %s depth frame [ppm-path]\n", argv[0]);
    return 2;
  }
  unsigned depth = (unsigned)strtoul(argv[1], NULL, 10);
  uint32_t frame = (uint32_t)strtoul(argv[2], NULL, 10);
  if (depth < 1 || depth > 11) {
    fputs("depth must be 1..11\n", stderr);
    return 2;
  }
  render_t cfg = settings(depth, frame);
  uint32_t pixels = cfg.width * cfg.width;
  FILE *ppm = NULL;
  if (argc == 4) {
    ppm = fopen(argv[3], "wb");
    if (!ppm) { perror("fopen"); return 1; }
    fprintf(ppm, "P6\n%u %u\n255\n", cfg.width, cfg.width);
  }
  uint64_t before = now_us();
  uint32_t total = 0;
  for (uint32_t pixel = 0; pixel < pixels; ++pixel) {
    uint32_t gray = shade(cfg, pixel);
    if (gray >= 32u) total += gray;
    if (ppm) {
      unsigned char g = gray > 255u ? 255u : (unsigned char)gray;
      unsigned char rgb[3] = {g, g, g};
      if (fwrite(rgb, sizeof(rgb), 1, ppm) != 1) {
        perror("fwrite"); fclose(ppm); return 1;
      }
    }
  }
  uint64_t elapsed = now_us() - before;
  if (ppm && fclose(ppm) != 0) { perror("fclose"); return 1; }
  printf("%llu %u\n", (unsigned long long)elapsed, total);
  return 0;
}
