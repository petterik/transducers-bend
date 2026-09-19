// Direct C twin of direct.bend. It performs the same four-lane
// map/filter/normalize/reduce over the same seed-ordered balanced batches.
// This is a handwritten scalar reference; it does not allocate an array or
// a list, and it is only a single-threaded comparison language baseline.
#include <stdint.h>
#include <stdio.h>

#ifndef ARRAY_DEPTH
#define ARRAY_DEPTH 8
#endif
#ifndef BATCH_DEPTH
#define BATCH_DEPTH 6
#endif
#ifndef NORMALIZE_ROUNDS
#define NORMALIZE_ROUNDS 32
#endif
#ifndef REPEATS
#define REPEATS 1
#endif

static uint32_t work(uint32_t x) {
  for (uint32_t i = 0; i < NORMALIZE_ROUNDS; ++i) {
    x = (x * 1664525u + 1013904223u) ^ (x >> 13u);
  }
  return x;
}

static uint32_t feed(uint32_t acc, uint32_t x) {
  const uint32_t normalized = work(x ^ 2654435761u);
  if ((normalized & 3u) != 0u) {
    acc += normalized;
  }
  return acc;
}

static uint32_t leaf_run(uint32_t seed) {
  uint32_t acc = 0;
  const uint32_t n = 1u << ARRAY_DEPTH;
  for (uint32_t i = 0; i < n; ++i) {
    const uint32_t s = seed + i;
    acc = feed(acc, s);
    acc = feed(acc, 1664525u);
    acc = feed(acc, 1013904223u);
    acc = feed(acc, 2654435761u);
  }
  return acc;
}

static uint32_t batch_run(uint32_t p, uint32_t seed) {
  if (p == 0u) {
    return leaf_run(seed);
  }
  const uint32_t left = batch_run(p - 1u, seed);
  const uint32_t right_seed = seed + (1u << (ARRAY_DEPTH + p - 1u));
  return left + batch_run(p - 1u, right_seed);
}

int main(void) {
  uint32_t answer = 0;
  for (uint32_t i = 0; i < REPEATS; ++i) {
    answer += batch_run(BATCH_DEPTH, 0u);
  }
  printf("%u\n", answer);
  return 0;
}
