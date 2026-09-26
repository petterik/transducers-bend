// Handwritten C controls for public_list_map_fold.bend.
// Build the input before timing; traverse and release it inside the timed interval.
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

typedef struct Node {
  uint32_t value;
  struct Node *next;
} Node;

static uint64_t now_us(void) {
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) abort();
  return (uint64_t)ts.tv_sec * 1000000u + (uint64_t)ts.tv_nsec / 1000u;
}

int main(int argc, char **argv) {
  if (argc != 3) return 2;
  char *end = NULL;
  unsigned long count = strtoul(argv[2], &end, 10);
  if (*end != '\0' || count > UINT32_MAX) return 2;

  if (argv[1][0] == 'f') {
    uint32_t *values = malloc((count ? count : 1) * sizeof *values);
    if (values == NULL) return 3;
    for (uint32_t i = 0; i < count; ++i) values[i] = i;
    uint64_t before = now_us();
    uint32_t sum = 0;
    for (uint32_t i = 0; i < count; ++i) sum += values[i] + 1u;
    free(values);
    uint64_t after = now_us();
    printf("%" PRIu64 " %" PRIu32 "\n", after - before, sum);
    return 0;
  }
  if (argv[1][0] == 'a') {
    Node *nodes = malloc((count ? count : 1) * sizeof *nodes);
    if (nodes == NULL) return 3;
    for (uint32_t i = 0; i < count; ++i) {
      nodes[i].value = i;
      nodes[i].next = i + 1 < count ? &nodes[i + 1] : NULL;
    }
    uint64_t before = now_us();
    uint32_t sum = 0;
    Node *cursor = count ? nodes : NULL;
    while (cursor != NULL) {
      sum += cursor->value + 1u;
      cursor = cursor->next;
    }
    free(nodes);
    uint64_t after = now_us();
    printf("%" PRIu64 " %" PRIu32 "\n", after - before, sum);
    return 0;
  }
  if (argv[1][0] != 'l') return 2;
  Node *head = NULL;
  // Prepending in reverse order gives the Bend fixture's 0, 1, ... sequence.
  for (uint32_t i = (uint32_t)count; i > 0; --i) {
    Node *node = malloc(sizeof *node);
    if (node == NULL) return 3;
    node->value = i - 1;
    node->next = head;
    head = node;
  }

  uint64_t before = now_us();
  uint32_t sum = 0;
  while (head != NULL) {
    Node *next = head->next;
    sum += head->value + 1u;
    free(head);
    head = next;
  }
  uint64_t after = now_us();
  printf("%" PRIu64 " %" PRIu32 "\n", after - before, sum);
  return 0;
}
