#!/usr/bin/env python3
"""Compare streaming keep, nested/let-bound Maybe map-fold, and direct folds."""
import argparse
import atexit
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import tempfile
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / 'fixtures/maybe_keep_pipeline.bend'
LANES = ('keep', 'map_fold', 'let_bound_map_fold', 'direct')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--upstream-main', type=Path, required=True)
parser.add_argument('--candidate-main', type=Path, required=True)
parser.add_argument('--fold-region-main', type=Path)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--sessions', type=int, default=16)
parser.add_argument('--measurement-order', default=','.join(LANES),
                    help='comma-separated permutation of timed lanes')
args = parser.parse_args()
assert args.sessions >= 8
measurement_order = tuple(args.measurement_order.split(','))
assert len(measurement_order) == len(LANES) \
    and set(measurement_order) == set(LANES), measurement_order

out = Path(tempfile.mkdtemp(prefix=args.output.stem + '-artifacts-'))
out.mkdir(parents=True, exist_ok=True)
source_text = SOURCE.read_text()
canonical_measurements = {
    'keep': '    kept : Nat & U32 <- measure_keep(keep_inputs)',
    'map_fold': '    map_fold : Nat & U32 <- measure_map_fold(map_fold_inputs)',
    'let_bound_map_fold': '    let_bound_map_fold : Nat & U32 <- measure_let_bound_map_fold(let_bound_inputs)',
    'direct': '    direct : Nat & U32 <- measure_direct(direct_inputs)',
}
for statement in canonical_measurements.values():
    assert source_text.count(statement) == 1, statement
canonical_block = '\n'.join(canonical_measurements[lane] for lane in LANES)
ordered_block = '\n'.join(canonical_measurements[lane]
                           for lane in measurement_order)
assert source_text.count(canonical_block) == 1, 'benchmark main shape changed'
source_text = source_text.replace(canonical_block, ordered_block, 1)
if measurement_order != LANES:
    ordered_source = SOURCE.with_name('_maybe_keep_pipeline_ordered.bend')
    ordered_source.write_text(source_text)
    atexit.register(ordered_source.unlink, missing_ok=True)
    SOURCE = ordered_source
env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
N = 200_000
BATCHES = 8
JS_N = 256
JS_BATCHES = 2
WORD_MOD = 1 << 32
expected = (BATCHES * N * (N - 1) // 2) % WORD_MOD
js_expected = (JS_BATCHES * JS_N * (JS_N - 1) // 2) % WORD_MOD


def run(command, timeout=180, check=True):
    result = subprocess.run(list(map(str, command)), env=env,
                            capture_output=True, text=True, timeout=timeout)
    if check:
        assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result


def compile_lane(name, compiler, stem):
    c_path = stem.with_suffix('.c')
    js_path = stem.with_suffix('.js')
    run(['bun', compiler, SOURCE, '-o', c_path, '-o', js_path])
    started = time.perf_counter()
    built = run(['clang', '-std=c11', '-O3', c_path, '-lpthread', '-lm',
                 '-o', stem], timeout=180)
    compile_seconds = time.perf_counter() - started
    return {
        'name': name,
        'compiler': str(compiler),
        'binary': str(stem),
        'c_path': str(c_path),
        'js_path': str(js_path),
        'clang_compile_seconds': compile_seconds,
        'c_bytes': c_path.stat().st_size,
        'c_sha256': hashlib.sha256(c_path.read_bytes()).hexdigest(),
        'js_bytes': js_path.stat().st_size,
        'compiler_sha256': hashlib.sha256(
            (compiler.parent / 'comp.ts').read_bytes()).hexdigest(),
    }


def smoke_js(item, compiler):
    # Large recursive List construction is not suitable for the JS stack.
    # Run the same three operations on a small source for JS semantic parity.
    text = SOURCE.read_text().replace('200000n', f'{JS_N}n').replace(
        '8n', f'{JS_BATCHES}n')
    assert text != SOURCE.read_text()
    smoke_source = SOURCE.with_name('_maybe_keep_pipeline_smoke.bend')
    smoke_stem = out / (item['name'] + '-smoke')
    try:
        smoke_source.write_text(text)
        js_path = smoke_stem.with_suffix('.js')
        run(['bun', compiler, smoke_source, '-o', js_path])
        rows = parse_rows(run(['bun', js_path], timeout=180).stdout.strip().splitlines())
    finally:
        smoke_source.unlink(missing_ok=True)
    assert all(row['checksum'] == js_expected for row in rows.values()), (item['name'], rows)
    return rows


def parse_rows(lines):
    rows = {}
    for line in lines:
        name, elapsed, checksum = line.split()
        assert name in LANES and name not in rows, line
        rows[name] = {'time_us': int(elapsed), 'checksum': int(checksum)}
    assert set(rows) == set(LANES), rows
    return rows


def instrument_c(text):
    declarations = r'''
static u64 maybe_allocations = 0;
static u64 maybe_starts[4] = {0, 0, 0, 0};
static u64 maybe_ends[4] = {0, 0, 0, 0};
static u32 maybe_clock_count = 0;
static void maybe_clock_mark(void) {
  u32 interval = maybe_clock_count / 2;
  if (interval < 4) {
    if ((maybe_clock_count & 1) == 0) maybe_starts[interval] = maybe_allocations;
    else maybe_ends[interval] = maybe_allocations;
  }
  maybe_clock_count += 1;
}
static void maybe_allocation_report(void) {
  fprintf(stderr, "MAYBE_ALLOC {\"clock_ticks\":%u,\"requests\":[%llu,%llu,%llu,%llu]}\n",
    maybe_clock_count,
    (unsigned long long)(maybe_ends[0] - maybe_starts[0]),
    (unsigned long long)(maybe_ends[1] - maybe_starts[1]),
    (unsigned long long)(maybe_ends[2] - maybe_starts[2]),
    (unsigned long long)(maybe_ends[3] - maybe_starts[3]));
}
'''
    insert = '#define ALC_AT(e, i)'
    assert text.count(insert) == 1
    text = text.replace(insert, declarations + '\n' + insert, 1)
    old_alloc = '''INLINE Loc heap_alloc(Env e, Cls cls) {
  Loc h = ALC_AT(e, cls);
  if (h) {
    ALC_AT(e, cls)   = e.mem[h];
    ALC_LEN(e, cls) -= 1ull << cls;
    return h;
  }
  return heap_alloc_miss(e, cls);
}'''
    new_alloc = '''INLINE Loc heap_alloc(Env e, Cls cls) {
  Loc h = ALC_AT(e, cls);
  if (h) {
    ALC_AT(e, cls)   = e.mem[h];
    ALC_LEN(e, cls) -= 1ull << cls;
    maybe_allocations += 1;
    return h;
  }
  Loc loc = heap_alloc_miss(e, cls);
  if (loc != HEAP_OFF) maybe_allocations += 1;
  return loc;
}'''
    assert text.count(old_alloc) == 1
    text = text.replace(old_alloc, new_alloc, 1)
    old_tick = '''static u64 io_tick(void) {
  struct timespec ts;'''
    new_tick = '''static u64 io_tick(void) {
  maybe_clock_mark();
  struct timespec ts;'''
    assert text.count(old_tick) == 1
    text = text.replace(old_tick, new_tick, 1)
    old_report = '''  int code  = io_loop(H);
  io_sync();
  return code;'''
    new_report = '''  int code  = io_loop(H);
  io_sync();
  maybe_allocation_report();
  return code;'''
    assert text.count(old_report) == 1
    return text.replace(old_report, new_report, 1)


def instrumented_allocations(item):
    c_path = Path(item['c_path'])
    instrumented_path = c_path.with_name(c_path.stem + '-alloc.c')
    instrumented_path.write_text(instrument_c(c_path.read_text()))
    binary = instrumented_path.with_suffix('')
    run(['clang', '-std=c11', '-O3', instrumented_path, '-lpthread', '-lm',
         '-o', binary], timeout=180)
    result = run([binary, '--threads', '1', '--gpu', 'off'], timeout=180)
    for line in result.stdout.strip().splitlines():
        assert int(line.split()[2]) == expected, (item['name'], line)
    line = next((line for line in result.stderr.splitlines()
                 if line.startswith('MAYBE_ALLOC ')), None)
    assert line is not None, result.stderr
    stats = json.loads(line[len('MAYBE_ALLOC '):])
    assert stats['clock_ticks'] == 8, (item['name'], stats)
    return {
        'requests_by_lane': stats['requests'],
        'instrumented_c_bytes': instrumented_path.stat().st_size,
        'instrumented_c_sha256': hashlib.sha256(
            instrumented_path.read_bytes()).hexdigest(),
    }


items = {
    'upstream': compile_lane(
        'upstream', args.upstream_main, out / 'upstream'),
    'candidate': compile_lane(
        'static_callback_candidate', args.candidate_main,
        out / 'static_callback_candidate'),
}
if args.fold_region_main is not None:
    items['fold_region_candidate'] = compile_lane(
        'fold_region_candidate', args.fold_region_main,
        out / 'fold_region_candidate')
for item in items.values():
    allocation_report = instrumented_allocations(item)
    item['allocation_requests_by_lane'] = dict(zip(
        measurement_order, allocation_report['requests_by_lane']))
    item['instrumented_c_bytes'] = allocation_report['instrumented_c_bytes']
    item['instrumented_c_sha256'] = allocation_report['instrumented_c_sha256']
    item['js_smoke_rows'] = smoke_js(item, Path(item['compiler']))

rng = random.Random(20260924)
samples = {compiler: {lane: [] for lane in LANES} for compiler in items}
for _session in range(args.sessions):
    order = list(items)
    rng.shuffle(order)
    for compiler in order:
        result = run([items[compiler]['binary'], '--threads', '1', '--gpu', 'off'],
                     timeout=180)
        rows = parse_rows(result.stdout.strip().splitlines())
        for lane, row in rows.items():
            assert row['checksum'] == expected, (compiler, lane, row)
            samples[compiler][lane].append(row['time_us'])

summary = {}
for lane in LANES:
    base = samples['upstream'][lane]
    comparisons = {}
    for compiler in items:
        current = samples[compiler][lane]
        def paired_ratio(numerator, denominator):
            ratios = [new / old for new, old in zip(numerator, denominator)
                      if old]
            boot = sorted(statistics.median(rng.choices(ratios, k=len(ratios)))
                          for _ in range(10_000))
            return {
                'median': statistics.median(ratios),
                'ci95': [boot[249], boot[9749]],
            }
        comparisons[compiler] = {
            'median_us': statistics.median(current),
            'paired_over_upstream': paired_ratio(current, base),
            'paired_over_direct': paired_ratio(current,
                                                samples[compiler]['direct']),
            'paired_over_static_callback': paired_ratio(
                current, samples['candidate'][lane]),
            'samples_us': current,
            'allocation_requests': items[compiler]['allocation_requests_by_lane'][lane],
        }
    summary[lane] = {
        'versions': comparisons,
    }

report = {
    'base_commit': subprocess.run(
        ['git', '-C', str(ROOT.parent / 'bend'), 'rev-parse', 'HEAD'],
        check=True, capture_output=True, text=True).stdout.strip(),
    'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'input_items_per_batch': N,
    'prebuilt_batches_per_lane': BATCHES,
    'js_smoke_items_per_batch': JS_N,
    'js_smoke_batches_per_lane': JS_BATCHES,
    'lanes': list(LANES),
    'measurement_order': list(measurement_order),
    'sessions': args.sessions,
    'clock': 'BenchClock.now_us; native monotonic nanoseconds converted to microseconds',
    'allocation_instrumentation': 'separate C builds; successful heap allocator requests between each pair of lane clock marks',
    'expected_checksum_per_lane': expected,
    'items': items,
    'summary': summary,
    'artifacts': str(out),
}
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
