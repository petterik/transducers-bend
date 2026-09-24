#!/usr/bin/env python3
"""Measure partition reducers against materialized and chunk-free controls."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import shutil
import statistics
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent
LANES = ('list', 'array', 'direct')
FOLD_LANES = ('list', 'array', 'group_fold', 'materialized', 'direct')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True,
                    help='pinned bendlang/main compiler entry point')
parser.add_argument('--base-commit',
                    help='bendlang/main commit used to prepare this compiler')
parser.add_argument('--compiler-variant',
                    help='label such as upstream or static-callback-candidate')
parser.add_argument('--sessions', type=int, default=12)
parser.add_argument('--pairs', type=int, default=5,
                    help='timed samples per lane in each session')
parser.add_argument('--min-batch-ms', type=int, default=100)
parser.add_argument('--bootstrap', type=int, default=5000)
parser.add_argument('--seed', type=int, default=20260923)
parser.add_argument('--max-repeats', type=int, default=16777216)
parser.add_argument('--cases', nargs='+',
                    choices=['fold_full', 'fold_order', 'fold_bounded', 'fold_bounded_short',
                             'reader_ab', 'retain'],
                    help='selected workloads; default: all')
parser.add_argument('--widths', nargs='+', type=int,
                    choices=list(range(1, 65)), default=[1, 2, 3, 8],
                    help='selected partition widths from 1 through 64')
parser.add_argument('--lanes', nargs='+',
                    choices=FOLD_LANES,
                    help='fold lanes to measure; default: List, Array, direct')
parser.add_argument('--source-size', type=int, default=96,
                    help='source items per operation for non-retained rows (default: 96)')
parser.add_argument('--output', type=Path)
parser.add_argument('--artifact-dir', type=Path)
a = parser.parse_args()
if min(a.sessions, a.pairs, a.min_batch_ms, a.bootstrap,
       a.max_repeats) < 1:
    parser.error('sessions, pairs, min-batch-ms, bootstrap and max-repeats must be positive')
if a.source_size < 1:
    parser.error('source-size must be positive')

compiler = a.bend_main.resolve()
if a.artifact_dir:
    out = a.artifact_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
else:
    out = Path(tempfile.mkdtemp(prefix='array-partition-measure-')).resolve()
env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
SAMPLE_COUNT = a.pairs
SOURCE_SIZE = a.source_size
WORD_MOD = 1 << 32


def lane_functions(kind, lane, width, budget, input_items, sample_count):
    if kind.startswith('fold_') or kind == 'reader_ab':
        if lane == 'list':
            function = 'list_hash_fold' if kind == 'fold_order' else 'list_fold'
            perform = f'F.{function}({width}n, {budget}n, xs)'
            imports = 'import ./fold_probe.bend as F\n'
        elif lane == 'array_two_phase':
            depth = (width - 1).bit_length()
            perform = f'F.array_fold_two_phase({width}n, {depth}n, {budget}n, xs)'
            imports = 'import ./fold_probe.bend as F\n'
        elif lane == 'array':
            depth = (width - 1).bit_length()
            perform = f'F.array_fold({width}n, {depth}n, {budget}n, xs)'
            imports = 'import ./fold_probe.bend as F\n'
        elif lane == 'materialized':
            function = ('materialized_hash_fold' if kind == 'fold_order'
                        else 'materialized_fold')
            perform = f'F.{function}({width}n, {budget}n, xs)'
            imports = 'import ./fold_probe.bend as F\n'
        elif lane == 'group_fold':
            function = ('list_group_hash' if kind == 'fold_order'
                        else 'list_group_sum')
            perform = f'G.{function}({width}n, {budget}n, xs)'
            imports = 'import ./group_fold_probe.bend as G\n'
        else:
            function = 'direct_hash_fold' if kind == 'fold_order' else 'direct_fold'
            perform = f'F.{function}({width}n, {budget}n, xs)'
            imports = 'import ./fold_probe.bend as F\n'
    else:
        depth = (width - 1).bit_length()
        if lane == 'list':
            perform = f'R.list_retain_checksum({width}n, xs)'
        else:
            perform = f'R.array_retain_checksum({width}n, {depth}n, xs)'
        imports = 'import ./retained_probe.bend as R\n'

    text = f'''import Base
import ./semantic_probe.bend as P
{imports}
import ./bench_clock.bend as BenchClock
# Every affine List source is built before its sample's high-resolution timer boundary.
def perform(xs: List<U32>) -> U32:
  {perform}

def build_sources(n: Nat, +size: Nat, xs: List<List<U32>>) -> List<List<U32>>:
  match n:
    case 0n:
      xs
    case 1n+p:
      build_sources(p, size, P.numbers(size, []) <> xs)

def batch(xs: List<List<U32>>, +total: U32) -> U32:
  match xs:
    case Nil{{}}:
      total
    case source <> rest:
      answer = perform(source)
      batch(rest, (total + answer : U32))

def parsed(value: Maybe<&2, Nat>) -> Nat:
  match value:
    case None{{}}:
      0n
    case Some{{n}}:
      n

def argument(args: List<String>) -> Nat:
  match args:
    case Nil{{}}:
      0n
    case h <> rest:
      parsed(Nat.read(h))

def measure_samples(n: Nat, +repeats: Nat) -> IO(Unit):
  match n:
    case 0n:
      IO.pure(Unit, Unit{{}})
    case 1n+p:
      inputs = build_sources(repeats, {input_items}n, [])
      do IO<Unit>:
        before : Nat <- BenchClock.now_us()
        answer : U32 = batch(inputs, 0)
        after : Nat <- BenchClock.now_us()
        IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
        measure_samples(p, repeats)

def measure(repeats: Nat) -> IO(Unit):
  warmup = perform(P.numbers({input_items}n, []))
  do IO<Unit>:
    IO.print("WARM:" ++ U32.show(warmup))
    measure_samples({sample_count}n, repeats)

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    measure(argument(args))
'''
    return text


def make_rows():
    rows = []
    selected = a.cases or [
        'fold_full', 'fold_bounded', 'fold_bounded_short', 'retain']
    for kind in selected:
        for width in a.widths:
            input_items = SOURCE_SIZE
            if kind == 'reader_ab':
                budget = (SOURCE_SIZE + width - 1) // width
                lanes = ('array_two_phase', 'array')
            elif kind == 'fold_full':
                budget = (SOURCE_SIZE + width - 1) // width
                lanes = tuple(a.lanes) if a.lanes else LANES
            elif kind == 'fold_order':
                budget = (SOURCE_SIZE + width - 1) // width
                lanes = (tuple(a.lanes) if a.lanes else
                         ('list', 'materialized', 'direct'))
                if 'array' in lanes:
                    parser.error('fold_order has no Array consumer implementation')
            elif kind == 'fold_bounded':
                budget = 2
                lanes = tuple(a.lanes) if a.lanes else LANES
            elif kind == 'fold_bounded_short':
                budget = 2
                input_items = 2 * width + 1
                lanes = tuple(a.lanes) if a.lanes else LANES
            elif kind == 'retain':
                input_items = SOURCE_SIZE + 1
                budget = (input_items + width - 1) // width
                lanes = ('list', 'array')
            else:
                budget = (SOURCE_SIZE + width - 1) // width
                lanes = ('list', 'array')
            rows.append({'kind': kind, 'width': width, 'budget': budget,
                         'lanes': list(lanes), 'input_items': input_items})
    return rows


def expected_per_input(row):
    count = row['input_items']
    width = row['width']
    if row['kind'] in ('fold_bounded', 'fold_bounded_short'):
        count = min(count, row['budget'] * width)
    if row['kind'] == 'fold_order':
        total = 0
        for value in range(count):
            total = (total * 33 + value + 1) % WORD_MOD
        return total
    total = count * (count - 1) // 2
    if row['kind'] == 'retain':
        total += (row['input_items'] + width - 1) // width
    return total % WORD_MOD


def timing_thresholds(row):
    if row['kind'] == 'fold_bounded_short':
        floor = min(a.min_batch_ms, 20) * 1000
        return floor, math.ceil(floor * 1.25)
    floor = a.min_batch_ms * 1000
    return floor, math.ceil(floor * 1.5)


def parse_output(output, expected, sample_count):
    lines = output.splitlines()
    assert lines and lines[0].startswith('WARM:'), output
    warm = int(lines[0].split(':', 1)[1])
    samples = []
    for line in lines[1:]:
        value, micros = map(int, line.split(':'))
        assert value == expected, (expected, line)
        samples.append(micros)
    assert len(samples) == sample_count, (sample_count, output)
    return warm, samples


def run(command, timeout=300, check=True):
    result = subprocess.run([str(item) for item in command], env=env,
                            capture_output=True, text=True, timeout=timeout)
    if check:
        assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result


def compile_source(stem, row, lane, sample_count):
    source = lane_functions(row['kind'], lane, row['width'], row['budget'],
                            row['input_items'], sample_count)
    bend_path = stem.with_suffix('.bend')
    bend_path.write_text(source)
    started = time.perf_counter()
    result = run(['bun', compiler, bend_path, '-o', stem,
                  '-o', stem.with_suffix('.js'), '-o', stem.with_suffix('.c')],
                 timeout=180, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return {
        'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'build_seconds': time.perf_counter() - started,
        'c_bytes': stem.with_suffix('.c').stat().st_size,
        'c_sha256': hashlib.sha256(stem.with_suffix('.c').read_bytes()).hexdigest(),
        'js_bytes': stem.with_suffix('.js').stat().st_size,
        'js_sha256': hashlib.sha256(stem.with_suffix('.js').read_bytes()).hexdigest(),
    }


def run_batch(stem, repeats, row, sample_count):
    result = run([stem, '--threads', '1', '--gpu', 'off', '--', repeats])
    expected = expected_per_input(row) * repeats % WORD_MOD
    warm, samples = parse_output(result.stdout, expected, sample_count)
    expected_warm = expected_per_input(row)
    assert warm == expected_warm, (warm, expected_warm, result.stdout)
    return samples


def balanced_lane_orders(lanes):
    """Rotate forward and reversed lane orders to balance timing position."""
    base = list(lanes)
    orders = []
    for source in (base, list(reversed(base))):
        for offset in range(len(source)):
            order = tuple(source[offset:] + source[:offset])
            if order not in orders:
                orders.append(order)
    return orders


def geometric_mean(values):
    return math.exp(statistics.fmean(math.log(value) for value in values))


def bootstrap_interval(values, rng):
    estimates = []
    for _ in range(a.bootstrap):
        sample = [values[rng.randrange(len(values))] for _ in values]
        estimates.append(geometric_mean(sample))
    estimates.sort()
    low = estimates[max(0, math.floor(0.025 * len(estimates)))]
    high = estimates[min(len(estimates) - 1,
                         math.ceil(0.975 * len(estimates)) - 1)]
    return {'lower_95': low, 'upper_95': high,
            'resamples': a.bootstrap, 'seed': a.seed}


# The allocation map tracks active List Cons and array chunk blocks by their
# heap locations. This lets heap_free classify frees even when term_drop is
# bypassed by generated code that directly releases a known-owned node.
ALLOC_INSTRUMENTATION = r'''
typedef struct { Loc loc; u32 kind; } StatsMark;
static StatsMark* stats_marks = NULL;
static size_t stats_mark_cap = 0;
static size_t stats_mark_used = 0;
static size_t stats_mark_occupied = 0;
static u64 stats_heap_allocs = 0, stats_heap_frees = 0;
static u64 stats_free_list_hits = 0;
static u64 stats_list_allocs = 0, stats_list_frees = 0;
static u64 stats_array_allocs = 0, stats_array_frees = 0;
static u64 stats_live_array_blocks = 0, stats_peak_array_blocks = 0;
static u64 stats_timed_peak_array_blocks = 0;
static u64 stats_live_words = 0, stats_peak_words = 0;
static u64 stats_timed_peak_words = 0;
static u64 stats_start_heap_allocs = 0, stats_start_heap_frees = 0;
static u64 stats_start_free_list_hits = 0;
static u64 stats_start_list_allocs = 0, stats_start_list_frees = 0;
static u64 stats_start_array_allocs = 0, stats_start_array_frees = 0;
static u64 stats_start_live_words = 0;
static u64 stats_start_live_array_blocks = 0;
static u64 stats_end_heap_allocs = 0, stats_end_heap_frees = 0;
static u64 stats_end_free_list_hits = 0;
static u64 stats_end_list_allocs = 0, stats_end_list_frees = 0;
static u64 stats_end_array_allocs = 0, stats_end_array_frees = 0;
static u64 stats_end_live_words = 0;
static u64 stats_end_live_array_blocks = 0;
static u32 stats_timer_calls = 0;
static bool stats_in_timed_region = false;

static void stats_note_array_alloc(void) {
  stats_array_allocs += 1;
  stats_live_array_blocks += 1;
  if (stats_live_array_blocks > stats_peak_array_blocks) {
    stats_peak_array_blocks = stats_live_array_blocks;
  }
  if (stats_in_timed_region &&
      stats_live_array_blocks > stats_timed_peak_array_blocks) {
    stats_timed_peak_array_blocks = stats_live_array_blocks;
  }
}

static void stats_note_array_free(void) {
  stats_array_frees += 1;
  if (stats_live_array_blocks) stats_live_array_blocks -= 1;
}

static size_t stats_hash(Loc loc) {
  loc ^= loc >> 30;
  loc *= 0xbf58476d1ce4e5b9ull;
  loc ^= loc >> 27;
  loc *= 0x94d049bb133111ebull;
  loc ^= loc >> 31;
  return (size_t)loc;
}

static void stats_grow(void) {
  size_t old_cap = stats_mark_cap;
  StatsMark* old = stats_marks;
  stats_mark_cap = old_cap ? old_cap * 2 : 1024;
  stats_marks = calloc(stats_mark_cap, sizeof(StatsMark));
  if (!stats_marks) { fprintf(stderr, "stats allocation map failed\n"); exit(2); }
  stats_mark_used = 0;
  stats_mark_occupied = 0;
  for (size_t i = 0; i < old_cap; i++) {
    if (old[i].loc && old[i].kind) {
      size_t at = stats_hash(old[i].loc) & (stats_mark_cap - 1);
      while (stats_marks[at].loc) at = (at + 1) & (stats_mark_cap - 1);
      stats_marks[at] = old[i];
      stats_mark_used += 1;
      stats_mark_occupied += 1;
    }
  }
  free(old);
}

static void stats_mark_alloc(Loc loc, u32 kind) {
  if (!loc) return;
  if (!stats_mark_cap || (stats_mark_occupied + 1) * 10 >= stats_mark_cap * 7) {
    stats_grow();
  }
  size_t at = stats_hash(loc) & (stats_mark_cap - 1);
  size_t tomb = (size_t)-1;
  while (stats_marks[at].loc) {
    if (stats_marks[at].loc == loc) {
      if (stats_marks[at].kind) return;
      stats_mark_used += 1;
      stats_marks[at].kind = kind;
      if (kind == 1) stats_list_allocs += 1;
      if (kind == 2) stats_note_array_alloc();
      return;
    }
    if (!stats_marks[at].kind && tomb == (size_t)-1) tomb = at;
    at = (at + 1) & (stats_mark_cap - 1);
  }
  if (tomb != (size_t)-1) at = tomb;
  else {
    stats_mark_used += 1;
    stats_mark_occupied += 1;
  }
  stats_marks[at].loc = loc;
  stats_marks[at].kind = kind;
  if (kind == 1) stats_list_allocs += 1;
  if (kind == 2) stats_note_array_alloc();
}

static void stats_mark_free(Loc loc) {
  if (!loc || !stats_mark_cap) return;
  size_t at = stats_hash(loc) & (stats_mark_cap - 1);
  while (stats_marks[at].loc) {
    if (stats_marks[at].loc == loc) {
      u32 kind = stats_marks[at].kind;
      stats_marks[at].kind = 0;
      if (kind == 1) stats_list_frees += 1;
      if (kind == 2) stats_note_array_free();
      return;
    }
    at = (at + 1) & (stats_mark_cap - 1);
  }
}

static void stats_note_alloc(Cls cls) {
  stats_heap_allocs += 1;
  stats_live_words += 1ull << cls;
  if (stats_live_words > stats_peak_words) stats_peak_words = stats_live_words;
  if (stats_in_timed_region && stats_live_words > stats_timed_peak_words) {
    stats_timed_peak_words = stats_live_words;
  }
}

static void stats_note_free(Cls cls, Loc loc) {
  stats_heap_frees += 1;
  stats_mark_free(loc);
  u64 words = 1ull << cls;
  stats_live_words = stats_live_words >= words ? stats_live_words - words : 0;
}

static void stats_note_list_node(u32 cid, Loc loc) {
  if (cid == CID_CON) stats_mark_alloc(loc, 1);
}

static void stats_record_start(void) {
  stats_in_timed_region = true;
  stats_start_heap_allocs = stats_heap_allocs;
  stats_start_heap_frees = stats_heap_frees;
  stats_start_free_list_hits = stats_free_list_hits;
  stats_start_list_allocs = stats_list_allocs;
  stats_start_list_frees = stats_list_frees;
  stats_start_array_allocs = stats_array_allocs;
  stats_start_array_frees = stats_array_frees;
  stats_start_live_words = stats_live_words;
  stats_start_live_array_blocks = stats_live_array_blocks;
  stats_timed_peak_words = stats_live_words;
  stats_timed_peak_array_blocks = stats_live_array_blocks;
}

static void stats_record_end(void) {
  stats_in_timed_region = false;
  stats_end_heap_allocs = stats_heap_allocs;
  stats_end_heap_frees = stats_heap_frees;
  stats_end_free_list_hits = stats_free_list_hits;
  stats_end_list_allocs = stats_list_allocs;
  stats_end_list_frees = stats_list_frees;
  stats_end_array_allocs = stats_array_allocs;
  stats_end_array_frees = stats_array_frees;
  stats_end_live_words = stats_live_words;
  stats_end_live_array_blocks = stats_live_array_blocks;
}

static void stats_tick(void) {
  if (stats_timer_calls++ == 0) stats_record_start();
  else if (stats_timer_calls == 2) stats_record_end();
}

static void stats_report(void) {
  fprintf(stderr,
    "ALLOC_STATS {\"heap_allocs_total\":%llu,\"heap_frees_total\":%llu,"
    "\"free_list_hits_total\":%llu,\"list_allocs_total\":%llu,"
    "\"list_frees_total\":%llu,\"array_allocs_total\":%llu,"
    "\"array_frees_total\":%llu,\"live_array_blocks_at_start\":%llu,"
    "\"peak_live_array_blocks_total\":%llu,"
    "\"timed_peak_live_array_blocks\":%llu,"
    "\"live_array_blocks_at_end\":%llu,\"live_words_at_start\":%llu,"
    "\"peak_live_words_total\":%llu,\"timed_peak_live_words\":%llu,"
    "\"live_words_at_end\":%llu,\"timed_heap_allocs\":%llu,"
    "\"timed_heap_frees\":%llu,\"timed_free_list_hits\":%llu,"
    "\"timed_list_allocs\":%llu,\"timed_list_frees\":%llu,"
    "\"timed_array_allocs\":%llu,\"timed_array_frees\":%llu}\n",
    (unsigned long long)stats_heap_allocs,
    (unsigned long long)stats_heap_frees,
    (unsigned long long)stats_free_list_hits,
    (unsigned long long)stats_list_allocs,
    (unsigned long long)stats_list_frees,
    (unsigned long long)stats_array_allocs,
    (unsigned long long)stats_array_frees,
    (unsigned long long)stats_start_live_array_blocks,
    (unsigned long long)stats_peak_array_blocks,
    (unsigned long long)stats_timed_peak_array_blocks,
    (unsigned long long)stats_end_live_array_blocks,
    (unsigned long long)stats_start_live_words,
    (unsigned long long)stats_peak_words,
    (unsigned long long)stats_timed_peak_words,
    (unsigned long long)stats_end_live_words,
    (unsigned long long)(stats_end_heap_allocs - stats_start_heap_allocs),
    (unsigned long long)(stats_end_heap_frees - stats_start_heap_frees),
    (unsigned long long)(stats_end_free_list_hits - stats_start_free_list_hits),
    (unsigned long long)(stats_end_list_allocs - stats_start_list_allocs),
    (unsigned long long)(stats_end_list_frees - stats_start_list_frees),
    (unsigned long long)(stats_end_array_allocs - stats_start_array_allocs),
    (unsigned long long)(stats_end_array_frees - stats_start_array_frees));
}
'''


def instrument_c(text):
    anchors = {
        '#define ALC_AT(e, i)': ALLOC_INSTRUMENTATION + '\n#define ALC_AT(e, i)',
        '#define term_ctr(cid, loc) term_make(TAG_CTR, cid, loc)':
            '#define term_ctr(cid, loc) term_make(TAG_CTR, cid, loc)',
        '  if (!got) {\n    got = bank_pop(H, cls);\n  }':
            '  if (!got) {\n    got = bank_pop(H, cls);\n  }\n  if (got) stats_free_list_hits += 1;',
        'INLINE Loc heap_alloc(Env e, Cls cls) {\n  Loc h = ALC_AT(e, cls);\n  if (h) {\n    ALC_AT(e, cls)   = e.mem[h];\n    ALC_LEN(e, cls) -= 1ull << cls;\n    return h;\n  }\n  return heap_alloc_miss(e, cls);\n}':
            'INLINE Loc heap_alloc(Env e, Cls cls) {\n  Loc h = ALC_AT(e, cls);\n  if (h) {\n    ALC_AT(e, cls)   = e.mem[h];\n    ALC_LEN(e, cls) -= 1ull << cls;\n    stats_free_list_hits += 1;\n    stats_note_alloc(cls);\n    return h;\n  }\n  Loc loc = heap_alloc_miss(e, cls);\n  if (loc != HEAP_OFF) stats_note_alloc(cls);\n  return loc;\n}',
        'INLINE void heap_free(Env e, Cls cls, Loc loc) {\n  if (err_seen(e.mem)) {\n    return;\n  }\n  e.mem[loc]       = ALC_AT(e, cls);':
            'INLINE void heap_free(Env e, Cls cls, Loc loc) {\n  if (err_seen(e.mem)) {\n    return;\n  }\n  stats_note_free(cls, loc);\n  e.mem[loc]       = ALC_AT(e, cls);',
        'static u64 io_tick(void) {\n  struct timespec ts;':
            'static u64 io_tick(void) {\n  stats_tick();\n  struct timespec ts;',
        '  int code  = io_loop(H);\n  io_sync();\n  return code;':
            '  int code  = io_loop(H);\n  io_sync();\n  stats_report();\n  return code;',
    }
    for old, new in anchors.items():
        assert text.count(old) == 1, f'instrumentation anchor count {text.count(old)}: {old[:80]!r}'
        text = text.replace(old, new, 1)

    term_ctr = '#define term_ctr(cid, loc) term_make(TAG_CTR, cid, loc)'
    text = text.replace(term_ctr, term_ctr + '''\nstatic Term stats_term_ctr(u32 cid, Loc loc) {
  stats_note_list_node(cid, loc);
  return term_make(TAG_CTR, cid, loc);
}''', 1)
    text, list_ctor_calls = re.subn(
        r'term_ctr\(CID_CON,\s*([A-Za-z_]\w*)\)',
        r'stats_term_ctr(CID_CON, \1)', text)
    assert list_ctor_calls > 0, 'no dynamic List Cons constructors were found'

    array_anchors = [
        ('  BLK_ALLOC(dst, cls)\n  blk_fill',
         '  BLK_ALLOC(dst, cls)\n  stats_mark_alloc(dst, 2);\n  blk_fill'),
        ('  BLK_ALLOC(n, arr ? c + 1 : c)\n  if (!arr && c == 0)',
         '  BLK_ALLOC(n, arr ? c + 1 : c)\n  stats_mark_alloc(n, 2);\n  if (!arr && c == 0)'),
        ('  BLK_ALLOC(n, cw)\n  if (!arr && c == 0)',
         '  BLK_ALLOC(n, cw)\n  stats_mark_alloc(n, 2);\n  if (!arr && c == 0)'),
        ('  BLK_ALLOC(l, arr ? c : buf_wcls(c))\n  for (u32 j',
         '  BLK_ALLOC(l, arr ? c : buf_wcls(c))\n  stats_mark_alloc(l, 2);\n  for (u32 j'),
    ]
    for old, new in array_anchors:
        assert text.count(old) == 1, f'Array allocation anchor count {text.count(old)}: {old[:80]!r}'
        text = text.replace(old, new, 1)
    return text


def instrumented_run(stem, row, lane, repeats, case_dir):
    instrument_repeats = min(repeats, 256)
    source_stem = case_dir / f'{row["kind"]}-w{row["width"]}-{lane}-alloc'
    build = compile_source(source_stem, row, lane, 1)
    c_path = source_stem.with_suffix('.c')
    instrumented = instrument_c(c_path.read_text())
    c_path.write_text(instrumented)
    binary = source_stem.with_name(source_stem.name + '-instrumented')
    started = time.perf_counter()
    compiled = run(['clang', '-std=c11', '-O3', c_path, '-lpthread', '-lm', '-o', binary],
                   timeout=180, check=False)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    compile_seconds = time.perf_counter() - started
    result = run([binary, '--threads', '1', '--gpu', 'off', '--', instrument_repeats], timeout=600)
    expected = expected_per_input(row) * instrument_repeats % WORD_MOD
    warm, samples = parse_output(result.stdout, expected, 1)
    assert warm == expected_per_input(row)
    match = None
    for line in result.stderr.splitlines():
        if line.startswith('ALLOC_STATS '):
            match = line[len('ALLOC_STATS '):]
            break
    assert match is not None, result.stderr
    stats = json.loads(match)
    assert stats['list_allocs_total'] == stats['list_frees_total'], stats
    assert stats['timed_array_allocs'] == stats['timed_array_frees'], stats
    assert (stats['live_array_blocks_at_end'] ==
            stats['live_array_blocks_at_start']), stats
    stats.update({
        'lane': lane, 'kind': row['kind'], 'width': row['width'],
        'budget': row['budget'], 'input_items': row['input_items'],
        'repeats_per_sample': instrument_repeats,
        'calibrated_repeats_per_sample': repeats, 'timed_sample_us': samples[0],
        'unmodified_generated_c_bytes': build['c_bytes'],
        'instrumented_c_bytes': c_path.stat().st_size,
        'instrumented_c_sha256': hashlib.sha256(c_path.read_bytes()).hexdigest(),
        'instrumented_compile_seconds': compile_seconds,
        'instrumentation_out_of_timing_samples': True,
        'timed_peak_extra_words': max(
            0, stats['timed_peak_live_words'] - stats['live_words_at_start']),
        'timed_peak_extra_bytes': max(
            0, stats['timed_peak_live_words'] - stats['live_words_at_start']) * 8,
        'timed_peak_extra_array_blocks': max(
            0, stats['timed_peak_live_array_blocks'] -
            stats['live_array_blocks_at_start']),
    })
    if lane in ('array', 'array_two_phase'):
        assert stats['timed_array_allocs'] > 0, stats
        if row['kind'] == 'retain':
            retained_groups = ((row['input_items'] + row['width'] - 1) //
                               row['width'])
            assert stats['timed_peak_extra_array_blocks'] == retained_groups, (
                retained_groups, stats)
    else:
        assert stats['timed_array_allocs'] == 0, stats
    return stats


report = {
    'platform': platform.platform(),
    'bendlang_main_commit': a.base_commit,
    'compiler_variant': a.compiler_variant,
    'compiler_entry_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
    'compiler_source_sha256': hashlib.sha256(
        (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
    'library_sha256': hashlib.sha256((ROOT / 'transduce.bend').read_bytes()).hexdigest(),
    'fixtures_sha256': {
        name: hashlib.sha256((FIXTURE_DIR / name).read_bytes()).hexdigest()
        for name in ('semantic_probe.bend', 'fold_probe.bend', 'retained_probe.bend',
                     'group_fold_probe.bend', 'bench_clock.bend', 'bench_clock.c',
                     'bench_clock.js')
    },
    'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'pinned bendlang/main compiler input; prebuilt affine List sources; sequential native CPU; --threads 1; GPU off',
    'lane_meanings': {
        'list': 'public List partition_all transducer and consumer',
        'array': 'fixture Array partition and consumer',
        'group_fold': 'bench-only reducer that folds values into explicit per-group state and emits group summaries without building chunks; it is a different API contract from partition_all',
        'materialized': 'handwritten loop that builds ordered List chunks, then consumes each chunk',
        'direct': 'handwritten loop that consumes source values without materializing chunks',
    },
    'protocol': {
        'sessions': a.sessions, 'paired_samples_per_session': a.pairs,
        'requested_min_batch_ms': a.min_batch_ms,
        'min_batch_us': a.min_batch_ms * 1000,
        'calibration_target_us': math.ceil(a.min_batch_ms * 1000 * 1.5),
        'short_input_min_batch_us': min(a.min_batch_ms, 20) * 1000,
        'short_input_calibration_target_us': math.ceil(
            min(a.min_batch_ms, 20) * 1000 * 1.25),
        'timing_unit': 'microseconds',
        'timer': 'BenchClock.now_us returns microseconds: native uses monotonic io_tick nanoseconds divided by 1000; JS scales performance.now to microseconds; effective precision is host-dependent',
        'bootstrap_resamples': a.bootstrap, 'seed': a.seed,
        'base_source_items': SOURCE_SIZE,
        'source_building': 'one fresh source List per repetition is built before BenchClock.now_us from ordered U32 values 0..n-1; each result row records n as input_items',
        'consumers': 'fold_full and fold_bounded use U32 sum; fold_order uses an order-sensitive U32 rolling hash; group_fold uses explicit per-group callbacks and equivalent summary consumers',
        'calibration': 'each lane has its own repeat count, calibrated to the same minimum batch duration; comparisons normalize elapsed microseconds by lane repeats',
        'timed_region': 'batch traversal, transduction and result consumption; source cleanup during traversal included',
        'instrumentation': 'separate instrumented C builds, excluded from native timing binaries',
        'lane_order': 'cycle through forward and reversed lane rotations, which balances each lane across timing positions; use a session count divisible by the schedule length for exact balance',
    },
    'artifacts': str(out), 'results': [], 'allocation_results': [],
}
rng = random.Random(a.seed)


for row in make_rows():
    label = f'{row["kind"]}_w{row["width"]}'
    row_min_batch_us, calibration_target_us = timing_thresholds(row)
    case_dir = out / label
    local_sources = case_dir / 'bench' / 'array_partition'
    local_sources.mkdir(parents=True)
    shutil.copy2(ROOT / 'transduce.bend', case_dir / 'transduce.bend')
    for name in ('semantic_probe.bend', 'fold_probe.bend', 'retained_probe.bend',
                 'group_fold_probe.bend', 'bench_clock.bend', 'bench_clock.c',
                 'bench_clock.js'):
        shutil.copy2(FIXTURE_DIR / name, local_sources / name)
    row_report = {**row, 'case': label, 'expected_per_input': expected_per_input(row),
                  'builds': {}, 'calibration': {}, 'sessions': [],
                  'samples_us': {lane: [] for lane in row['lanes']},
                  'min_batch_us': row_min_batch_us,
                  'calibration_target_us': calibration_target_us}
    stems = {}
    lane_orders = balanced_lane_orders(row['lanes'])
    for lane in row['lanes']:
        stem = local_sources / f'{label}-{lane}'
        row_report['builds'][lane] = compile_source(stem, row, lane, SAMPLE_COUNT)
        stems[lane] = stem

    repeats_by_lane = {}
    for lane in row['lanes']:
        lane_repeats = 1
        row_report['calibration'][lane] = []
        while lane_repeats <= a.max_repeats:
            samples = run_batch(stems[lane], lane_repeats, row, SAMPLE_COUNT)
            minimum = min(samples)
            row_report['calibration'][lane].append({
                'repeats_per_sample': lane_repeats,
                'samples_us': samples,
                'minimum_us': minimum,
            })
            if minimum >= calibration_target_us:
                break
            lane_repeats *= 2
        assert lane_repeats <= a.max_repeats, (
            label, lane, 'failed to calibrate', row_report['calibration'][lane][-3:])
        repeats_by_lane[lane] = lane_repeats
    row_report['repeats_per_sample'] = repeats_by_lane
    row_report['expected_batch'] = {
        lane: expected_per_input(row) * repeats % WORD_MOD
        for lane, repeats in repeats_by_lane.items()
    }

    for session in range(a.sessions):
        lanes = list(lane_orders[session % len(lane_orders)])
        session_samples = {}
        for lane in lanes:
            samples = run_batch(stems[lane], repeats_by_lane[lane],
                                row, SAMPLE_COUNT)
            assert min(samples) >= row_min_batch_us, (label, lane, samples)
            session_samples[lane] = samples
            row_report['samples_us'][lane].extend(samples)
        row_report['sessions'].append({
            'session': session, 'lane_order': lanes,
            'samples_us': session_samples,
            'repeats_per_sample': repeats_by_lane,
        })

    comparisons = {}
    reference_lane = 'list' if 'list' in row['lanes'] else row['lanes'][0]
    row_report['reference_lane'] = reference_lane
    comparison_pairs = [(lane, reference_lane) for lane in row['lanes']
                        if lane != reference_lane]
    if 'materialized' in row['lanes'] and 'direct' in row['lanes']:
        comparison_pairs.append(('materialized', 'direct'))
    if 'group_fold' in row['lanes']:
        if 'materialized' in row['lanes']:
            comparison_pairs.append(('group_fold', 'materialized'))
        if 'direct' in row['lanes']:
            comparison_pairs.append(('group_fold', 'direct'))
    for lane, denominator in comparison_pairs:
        session_ratios = []
        for session in row_report['sessions']:
            lane_us_per_operation = (
                sum(session['samples_us'][lane]) / repeats_by_lane[lane])
            reference_us_per_operation = (
                sum(session['samples_us'][denominator]) /
                repeats_by_lane[denominator])
            session_ratios.append(
                lane_us_per_operation / reference_us_per_operation)
        estimate = geometric_mean(session_ratios)
        comparisons[f'{lane}_over_{denominator}'] = {
            'geometric_mean_ratio': estimate,
            'bootstrap_95': bootstrap_interval(session_ratios, rng),
            'session_ratios': session_ratios,
        }
    row_report['median_sample_us'] = {
        lane: statistics.median(samples)
        for lane, samples in row_report['samples_us'].items()
    }
    row_report['median_us_per_operation'] = {
        lane: statistics.median(samples) / repeats_by_lane[lane]
        for lane, samples in row_report['samples_us'].items()
    }
    row_report['comparisons'] = comparisons
    report['results'].append(row_report)
    print(label, 'median_us_per_operation', row_report['median_us_per_operation'],
          'median_sample_us', row_report['median_sample_us'], flush=True)

    for lane in row['lanes']:
        stats = instrumented_run(stems[lane], row, lane,
                                 repeats_by_lane[lane], local_sources)
        report['allocation_results'].append(stats)
    if a.output:
        a.output.write_text(json.dumps(report, indent=2) + '\n')

if a.output:
    a.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
