// Handwritten C control for public_array_map_filter_sum.bend.
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static uint64_t now_us(void) {
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) abort();
  return (uint64_t)ts.tv_sec * 1000000u + (uint64_t)ts.tv_nsec / 1000u;
}

static uint32_t transform(uint32_t x) {
  uint32_t a = x * UINT32_C(2654435761);
  uint32_t b = a ^ (a >> 16);
  uint32_t c = b * UINT32_C(2246822507);
  return c ^ (c >> 13);
}

int main(int argc, char **argv) {
  if (argc != 3) return 2;
  char *end = NULL;
  unsigned long depth = strtoul(argv[1], &end, 10);
  if (*end != '\0' || depth > 23) return 2;
  unsigned long seed_arg = strtoul(argv[2], &end, 10);
  if (*end != '\0' || seed_arg > UINT32_MAX) return 2;
  uint32_t seed = (uint32_t)seed_arg;
  size_t count = (size_t)1 << depth;
  uint32_t *values = malloc(count * sizeof *values);
  if (values == NULL) return 3;
  for (size_t i = 0; i < count; ++i) {
    values[i] = (uint32_t)i * UINT32_C(1664525) + seed;
  }

  uint64_t before = now_us();
  uint32_t sum = 0;
  for (size_t i = 0; i < count; ++i) {
    uint32_t mapped = transform(values[i]);
    if ((mapped & UINT32_C(255)) < UINT32_C(96)) sum += mapped;
  }
  free(values);
  uint64_t after = now_us();
  printf("%" PRIu64 " %" PRIu32 "\n", after - before, sum);
  return 0;
}
