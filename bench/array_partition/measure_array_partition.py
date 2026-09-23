#!/usr/bin/env python3
"""Measure Array/List/direct partition consumers and separate C allocation counts."""
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
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bend-main', type=Path, required=True,
                    help='pinned bendlang/main compiler entry point')
parser.add_argument('--sessions', type=int, default=10)
parser.add_argument('--pairs', type=int, default=5,
                    help='timed samples per lane in each session')
parser.add_argument('--min-batch-ms', type=int, default=100)
parser.add_argument('--bootstrap', type=int, default=5000)
parser.add_argument('--seed', type=int, default=20260923)
parser.add_argument('--max-repeats', type=int, default=1048576)
parser.add_argument('--cases', nargs='+',
                    choices=['fold_full', 'fold_bounded', 'retain'],
                    help='selected workloads; default: all')
parser.add_argument('--widths', nargs='+', type=int, choices=[1, 2, 3, 8],
                    default=[1, 2, 3, 8], help='selected partition widths')
parser.add_argument('--output', type=Path)
parser.add_argument('--artifact-dir', type=Path)
a = parser.parse_args()
if min(a.sessions, a.pairs, a.min_batch_ms, a.bootstrap,
       a.max_repeats) < 1:
    parser.error('sessions, pairs, min-batch-ms, bootstrap and max-repeats must be positive')

compiler = a.bend_main.resolve()
if a.artifact_dir:
    out = a.artifact_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
else:
    out = Path(tempfile.mkdtemp(prefix='array-partition-measure-')).resolve()
env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
SAMPLE_COUNT = a.pairs
SOURCE_SIZE = 96
WORD_MOD = 1 << 32


def lane_functions(kind, lane, width, budget, sample_count):
    if kind.startswith('fold_'):
        if lane == 'list':
            perform = f'F.list_fold({width}n, {budget}n, xs)'
            imports = 'import ./fold_probe.bend as F\n'
        elif lane == 'array':
            depth = (width - 1).bit_length()
            perform = f'F.array_fold({width}n, {depth}n, {budget}n, xs)'
            imports = 'import ./fold_probe.bend as F\n'
        else:
            perform = f'F.direct_fold({width}n, {budget}n, xs)'
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
# Every affine List source is built before its sample's IO.now boundary.
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
      inputs = build_sources(repeats, {SOURCE_SIZE}n, [])
      do IO<Unit>:
        before : Nat <- IO.now()
        answer : U32 = batch(inputs, 0)
        after : Nat <- IO.now()
        IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
        measure_samples(p, repeats)

def measure(repeats: Nat) -> IO(Unit):
  warmup = perform(P.numbers({SOURCE_SIZE}n, []))
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
    selected = a.cases or ['fold_full', 'fold_bounded', 'retain']
    for kind in selected:
        for width in a.widths:
            if kind == 'fold_full':
                budget = SOURCE_SIZE // width
                lanes = LANES
            elif kind == 'fold_bounded':
                budget = 2
                lanes = LANES
            else:
                budget = SOURCE_SIZE // width
                lanes = ('list', 'array')
            rows.append({'kind': kind, 'width': width, 'budget': budget,
                         'lanes': list(lanes), 'input_items': SOURCE_SIZE})
    return rows


def expected_per_input(row):
    count = row['input_items']
    width = row['width']
    if row['kind'] == 'fold_bounded':
        count = min(count, row['budget'] * width)
    total = count * (count - 1) // 2
    if row['kind'] == 'retain':
        total += (row['input_items'] + width - 1) // width
    return total % WORD_MOD


def parse_output(output, expected, sample_count):
    lines = output.splitlines()
    assert lines and lines[0].startswith('WARM:'), output
    warm = int(lines[0].split(':', 1)[1])
    samples = []
    for line in lines[1:]:
        value, millis = map(int, line.split(':'))
        assert value == expected, (expected, line)
        samples.append(millis)
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
                            sample_count)
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
static u64 stats_live_words = 0, stats_peak_words = 0;
static u64 stats_timed_peak_words = 0;
static u64 stats_start_heap_allocs = 0, stats_start_heap_frees = 0;
static u64 stats_start_free_list_hits = 0;
static u64 stats_start_list_allocs = 0, stats_start_list_frees = 0;
static u64 stats_start_array_allocs = 0, stats_start_array_frees = 0;
static u64 stats_start_live_words = 0;
static u64 stats_end_heap_allocs = 0, stats_end_heap_frees = 0;
static u64 stats_end_free_list_hits = 0;
static u64 stats_end_list_allocs = 0, stats_end_list_frees = 0;
static u64 stats_end_array_allocs = 0, stats_end_array_frees = 0;
static u64 stats_end_live_words = 0;
static u32 stats_timer_calls = 0;
static bool stats_in_timed_region = false;

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
      if (kind == 2) stats_array_allocs += 1;
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
  if (kind == 2) stats_array_allocs += 1;
}

static void stats_mark_free(Loc loc) {
  if (!loc || !stats_mark_cap) return;
  size_t at = stats_hash(loc) & (stats_mark_cap - 1);
  while (stats_marks[at].loc) {
    if (stats_marks[at].loc == loc) {
      u32 kind = stats_marks[at].kind;
      stats_marks[at].kind = 0;
      if (kind == 1) stats_list_frees += 1;
      if (kind == 2) stats_array_frees += 1;
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
  stats_timed_peak_words = stats_live_words;
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
    "\"array_frees_total\":%llu,\"live_words_at_start\":%llu,"
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
    stats.update({
        'lane': lane, 'kind': row['kind'], 'width': row['width'],
        'budget': row['budget'], 'input_items': row['input_items'],
        'repeats_per_sample': instrument_repeats,
        'calibrated_repeats_per_sample': repeats, 'timed_sample_ms': samples[0],
        'unmodified_generated_c_bytes': build['c_bytes'],
        'instrumented_c_bytes': c_path.stat().st_size,
        'instrumented_c_sha256': hashlib.sha256(c_path.read_bytes()).hexdigest(),
        'instrumented_compile_seconds': compile_seconds,
        'instrumentation_out_of_timing_samples': True,
        'timed_peak_extra_words': max(
            0, stats['timed_peak_live_words'] - stats['live_words_at_start']),
        'timed_peak_extra_bytes': max(
            0, stats['timed_peak_live_words'] - stats['live_words_at_start']) * 8,
    })
    if lane == 'array':
        assert stats['timed_array_allocs'] > 0, stats
    else:
        assert stats['timed_array_allocs'] == 0, stats
    return stats


report = {
    'platform': platform.platform(),
    'compiler_entry_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
    'compiler_source_sha256': hashlib.sha256(
        (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
    'library_sha256': hashlib.sha256((ROOT / 'transduce.bend').read_bytes()).hexdigest(),
    'fixtures_sha256': {
        name: hashlib.sha256((FIXTURE_DIR / name).read_bytes()).hexdigest()
        for name in ('semantic_probe.bend', 'fold_probe.bend', 'retained_probe.bend')
    },
    'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'candidate bendlang/main compiler; prebuilt affine List sources; sequential native CPU; --threads 1; GPU off',
    'protocol': {
        'sessions': a.sessions, 'paired_samples_per_session': a.pairs,
        'min_batch_ms': a.min_batch_ms,
        'calibration_target_ms': math.ceil(a.min_batch_ms * 1.5),
        'bootstrap_resamples': a.bootstrap, 'seed': a.seed,
        'source_items_per_operation': SOURCE_SIZE,
        'source_building': 'one fresh source List per repetition, built before IO.now; same ordered values 0..95 in every lane',
        'timed_region': 'batch traversal, transduction and result consumption; source cleanup during traversal included',
        'instrumentation': 'separate instrumented C builds, excluded from native timing binaries',
        'lane_order': 'rotate forward and reverse lane order by session; pair equal sample positions within each session',
    },
    'artifacts': str(out), 'results': [], 'allocation_results': [],
}
rng = random.Random(a.seed)


for row in make_rows():
    label = f'{row["kind"]}_w{row["width"]}'
    case_dir = out / label
    local_sources = case_dir / 'bench' / 'array_partition'
    local_sources.mkdir(parents=True)
    shutil.copy2(ROOT / 'transduce.bend', case_dir / 'transduce.bend')
    for name in ('semantic_probe.bend', 'fold_probe.bend', 'retained_probe.bend'):
        shutil.copy2(FIXTURE_DIR / name, local_sources / name)
    row_report = {**row, 'case': label, 'expected_per_input': expected_per_input(row),
                  'builds': {}, 'calibration': [], 'sessions': [],
                  'samples_ms': {lane: [] for lane in row['lanes']}}
    stems = {}
    for lane in row['lanes']:
        stem = local_sources / f'{label}-{lane}'
        row_report['builds'][lane] = compile_source(stem, row, lane, SAMPLE_COUNT)
        stems[lane] = stem

    repeats = 1
    calibration_target = math.ceil(a.min_batch_ms * 1.5)
    while repeats <= a.max_repeats:
        calibration_samples = {}
        for lane in row['lanes']:
            calibration_samples[lane] = run_batch(
                stems[lane], repeats, row, SAMPLE_COUNT)
        minimum = min(value for values in calibration_samples.values()
                      for value in values)
        row_report['calibration'].append({
            'repeats_per_sample': repeats,
            'samples_ms': calibration_samples,
            'minimum_ms': minimum,
        })
        if minimum >= calibration_target:
            break
        repeats *= 2
    assert repeats <= a.max_repeats, (
        label, 'failed to calibrate all lanes', row_report['calibration'][-3:])
    row_report['repeats_per_sample'] = repeats
    row_report['calibration_target_ms'] = calibration_target
    row_report['expected_batch'] = expected_per_input(row) * repeats % WORD_MOD

    for session in range(a.sessions):
        lanes = list(row['lanes'])
        if session % 2:
            lanes.reverse()
        session_samples = {}
        for lane in lanes:
            samples = run_batch(stems[lane], repeats, row, SAMPLE_COUNT)
            assert min(samples) >= a.min_batch_ms, (label, lane, samples)
            session_samples[lane] = samples
            row_report['samples_ms'][lane].extend(samples)
        row_report['sessions'].append({
            'session': session, 'lane_order': lanes,
            'samples_ms': session_samples,
        })

    comparisons = {}
    for lane in row['lanes']:
        if lane == 'list':
            continue
        session_ratios = []
        for session in row_report['sessions']:
            lane_total = sum(session['samples_ms'][lane])
            list_total = sum(session['samples_ms']['list'])
            session_ratios.append(lane_total / list_total)
        estimate = geometric_mean(session_ratios)
        comparisons[f'{lane}_over_list'] = {
            'geometric_mean_ratio': estimate,
            'bootstrap_95': bootstrap_interval(session_ratios, rng),
            'session_ratios': session_ratios,
        }
    row_report['median_sample_ms'] = {
        lane: statistics.median(samples)
        for lane, samples in row_report['samples_ms'].items()
    }
    row_report['comparisons'] = comparisons
    report['results'].append(row_report)
    print(label, row_report['median_sample_ms'], flush=True)

    for lane in row['lanes']:
        stats = instrumented_run(stems[lane], row, lane, repeats, local_sources)
        report['allocation_results'].append(stats)
    if a.output:
        a.output.write_text(json.dumps(report, indent=2) + '\n')

if a.output:
    a.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
