#!/usr/bin/env python3
"""Measure materialized, transducer, and direct map/filter/fold implementations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import statistics
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).with_name('fold_region_map_filter_bench.bend')
MODES = {'materialized': 0, 'transducer': 1, 'handwritten': 2}
SAMPLES = 16
DEFAULT_ITEMS = 300_000
SEED = 20260925

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--upstream-main', type=Path, required=True)
parser.add_argument('--static-main', type=Path, required=True,
                    help='candidate with checked static-callback optimization only')
parser.add_argument('--fold-region-main', type=Path, required=True,
                    help='candidate with static-callback and producer/fold-region passes')
parser.add_argument('--items', type=int, default=DEFAULT_ITEMS)
parser.add_argument('--sessions', type=int, default=SAMPLES)
parser.add_argument('--seed', type=int, default=SEED)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if min(args.items, args.sessions) < 1:
    parser.error('--items and --sessions must be positive')

ENV = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, env=ENV, timeout=300):
    result = subprocess.run([str(x) for x in command], env=env,
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'command failed: {command}\n{result.stdout}\n{result.stderr}')
    return result


def expected_hash(items):
    acc = 5381
    for mapped in range(1, items + 1):
        if mapped % 2 == 0:
            acc = (acc * 33 + mapped) & 0xFFFFFFFF
    return acc


def parse_output(output, expected):
    fields = output.strip().split()
    assert len(fields) == 2, output
    elapsed_us, answer = map(int, fields)
    assert answer == expected, (answer, expected, output)
    return elapsed_us


def compile_compiler(compiler, name, temp, env):
    c_file = temp / f'{name}.c'
    js_file = temp / f'{name}.js'
    binary = temp / name
    fold_report = temp / f'{name}-fold-report.json'
    compile_env = dict(env)
    if name == 'fold_region':
        compile_env['BEND_FOLD_REGION_REPORT'] = str(fold_report)
    started = time.perf_counter()
    run(['bun', compiler, FIXTURE, '-o', c_file, '-o', js_file], compile_env)
    bend_compile_seconds = time.perf_counter() - started
    started = time.perf_counter()
    run(['clang', '-O3', c_file, '-o', binary], env)
    clang_seconds = time.perf_counter() - started
    code = c_file.read_text()
    comp = compiler.parent / 'comp.ts'
    cons_sites = len(re.findall(r'term_ctr\(CID_CON,\s*_nd_\d+\)', code))
    report = {
        'compiler_main_sha256': sha256(compiler),
        'compiler_comp_sha256': sha256(comp),
        'bend_compile_seconds': bend_compile_seconds,
        'clang_O3_seconds': clang_seconds,
        'c_bytes': c_file.stat().st_size,
        'js_bytes': js_file.stat().st_size,
        'c_sha256': sha256(c_file),
        'js_sha256': sha256(js_file),
        'dynamic_list_cons_sites': cons_sites,
    }
    if name == 'fold_region':
        report['fold_region'] = json.loads(fold_report.read_text())
        stats = report['fold_region']
        assert stats['fused'] > 0 and stats['helpers'] > 0 \
            and stats['rechecked'] == stats['helpers'], stats
        region = stats['region']
        assert region['branches'] > 0 and region['emits'] > 0 \
            and region['skips'] > 0, region
    return report, c_file, js_file, binary


STATS_C = r'''
static u64 stats_heap_alloc_calls = 0, stats_heap_free_calls = 0;
static u64 stats_timed_heap_alloc_calls = 0, stats_timed_heap_free_calls = 0;
static u64 stats_dynamic_cons = 0, stats_timed_dynamic_cons = 0;
static u32 stats_clock_calls = 0;
static bool stats_in_timed_region = false;
static void stats_note_alloc(void) {
  stats_heap_alloc_calls += 1;
  if (stats_in_timed_region) stats_timed_heap_alloc_calls += 1;
}
static void stats_note_free(void) {
  stats_heap_free_calls += 1;
  if (stats_in_timed_region) stats_timed_heap_free_calls += 1;
}
static void stats_note_cons(void) {
  stats_dynamic_cons += 1;
  if (stats_in_timed_region) stats_timed_dynamic_cons += 1;
}
static void stats_tick(void) {
  if (stats_clock_calls == 0) stats_in_timed_region = true;
  else if (stats_clock_calls == 1) stats_in_timed_region = false;
  stats_clock_calls += 1;
}
static void stats_report(void) {
  fprintf(stderr,
    "ALLOC_STATS calls=%llu frees=%llu timed_calls=%llu timed_frees=%llu "
    "dynamic_cons=%llu timed_dynamic_cons=%llu clock_calls=%u\n",
    (unsigned long long)stats_heap_alloc_calls,
    (unsigned long long)stats_heap_free_calls,
    (unsigned long long)stats_timed_heap_alloc_calls,
    (unsigned long long)stats_timed_heap_free_calls,
    (unsigned long long)stats_dynamic_cons,
    (unsigned long long)stats_timed_dynamic_cons,
    stats_clock_calls);
}
'''


def instrument_c(source):
    anchor = '#define ALC_AT(e, i)'
    assert source.count(anchor) == 1
    source = source.replace(anchor, STATS_C + '\n' + anchor, 1)
    term_macro = '#define term_ctr(cid, loc) term_make(TAG_CTR, cid, loc)'
    assert source.count(term_macro) == 1
    source = source.replace(term_macro, term_macro + '''
static Term stats_term_ctr(u32 cid, Loc loc) {
  if (cid == CID_CON) stats_note_cons();
  return term_make(TAG_CTR, cid, loc);
}''', 1)
    source, cons_sites = re.subn(
        r'term_ctr\(CID_CON,\s*(_nd_\d+)\)',
        r'stats_term_ctr(CID_CON, \1)', source)
    assert cons_sites > 0, 'no dynamic List constructor call sites found'

    alloc_anchor = 'INLINE Loc heap_alloc(Env e, Cls cls) {\n'
    assert source.count(alloc_anchor) == 1
    source = source.replace(alloc_anchor,
                            alloc_anchor + '  stats_note_alloc();\n', 1)
    free_anchor = ('INLINE void heap_free(Env e, Cls cls, Loc loc) {\n'
                   '  if (err_seen(e.mem)) {\n'
                   '    return;\n'
                   '  }\n')
    assert source.count(free_anchor) == 1
    source = source.replace(free_anchor, free_anchor + '  stats_note_free();\n', 1)
    tick_anchor = 'static u64 io_tick(void) {\n'
    assert source.count(tick_anchor) == 1
    source = source.replace(tick_anchor, tick_anchor + '  stats_tick();\n', 1)
    exit_anchor = '  io_sync();\n  return code;'
    assert source.count(exit_anchor) == 1
    source = source.replace(exit_anchor,
                            '  io_sync();\n  stats_report();\n  return code;', 1)
    return source, cons_sites


def allocation_counts(c_file, compiler_name, temp, lane, items, expected):
    c_text, cons_sites = instrument_c(c_file.read_text())
    inst_c = temp / f'{compiler_name}-alloc.c'
    binary = temp / f'{compiler_name}-{lane}-alloc'
    inst_c.write_text(c_text)
    run(['clang', '-O3', inst_c, '-o', binary])
    result = run([binary, '--threads', '1', '--gpu', 'off', '--',
                  str(MODES[lane]), str(items)])
    elapsed_us = parse_output(result.stdout, expected)
    match = re.search(
        r'ALLOC_STATS calls=(\d+) frees=(\d+) timed_calls=(\d+) '
        r'timed_frees=(\d+) dynamic_cons=(\d+) timed_dynamic_cons=(\d+) '
        r'clock_calls=(\d+)', result.stderr)
    assert match, result.stderr
    calls, frees, timed_calls, timed_frees, cons, timed_cons, clock_calls = \
        map(int, match.groups())
    assert clock_calls == 2, result.stderr
    return {
        'lane': lane,
        'instrumented_elapsed_us_not_for_timing': elapsed_us,
        'heap_alloc_calls_total': calls,
        'heap_free_calls_total': frees,
        'timed_heap_alloc_calls': timed_calls,
        'timed_heap_free_calls': timed_frees,
        'dynamic_list_cons_total': cons,
        'timed_dynamic_list_cons': timed_cons,
        'clock_calls': clock_calls,
        'instrumented_dynamic_list_cons_sites': cons_sites,
    }


def bootstrap_interval(values, seed):
    rng = random.Random(seed)
    medians = sorted(statistics.median(
        values[rng.randrange(len(values))] for _ in values)
        for _ in range(20_000))
    return [medians[500], medians[19_499]]


def main():
    args.output.parent.mkdir(parents=True, exist_ok=True)
    env = {**ENV, 'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
    upstream = args.upstream_main.resolve()
    static_main = args.static_main.resolve()
    fold_region_main = args.fold_region_main.resolve()
    expected = expected_hash(args.items)
    with tempfile.TemporaryDirectory(prefix='fold-region-map-filter-') as tmp_name:
        temp = Path(tmp_name)
        upstream_report, upstream_c, upstream_js, upstream_bin = \
            compile_compiler(upstream, 'upstream', temp, env)
        static_report, static_c, static_js, static_bin = \
            compile_compiler(static_main, 'static_callback', temp, env)
        fold_region_report, fold_region_c, fold_region_js, fold_region_bin = \
            compile_compiler(fold_region_main, 'fold_region', temp, env)

        correctness = {}
        for name, js_file, binary in [
                ('upstream', upstream_js, upstream_bin),
                ('static_callback', static_js, static_bin),
                ('fold_region', fold_region_js, fold_region_bin)]:
            for lane, mode in MODES.items():
                js_out = run(['bun', js_file, mode, 4096]).stdout
                native_out = run([binary, '--threads', '1', '--gpu', 'off',
                                  '--', mode, 4096]).stdout
                js_value = parse_output(js_out, expected_hash(4096))
                native_value = parse_output(native_out, expected_hash(4096))
                correctness[f'{name}_{lane}'] = {
                    'js_checksum': expected_hash(4096),
                    'native_checksum': expected_hash(4096),
                    'js_elapsed_us': js_value,
                    'native_elapsed_us': native_value,
                }

        allocation_results = {}
        for compiler_name, c_file in [
                ('upstream', upstream_c),
                ('static_callback', static_c),
                ('fold_region', fold_region_c)]:
            allocation_results[compiler_name] = {
                lane: allocation_counts(c_file, compiler_name, temp, lane,
                                        args.items, expected)
                for lane in MODES
            }

        rng = random.Random(args.seed)
        samples = {
            compiler: {lane: [] for lane in MODES}
            for compiler in ('upstream', 'static_callback', 'fold_region')
        }
        sessions = []
        binaries = {
            'upstream': upstream_bin,
            'static_callback': static_bin,
            'fold_region': fold_region_bin,
        }
        implementation_ratios = {
            compiler: {lane: [] for lane in ('materialized', 'transducer')}
            for compiler in binaries
        }
        compiler_pair_names = (
            'static_callback_over_upstream',
            'fold_region_over_static_callback',
            'fold_region_over_upstream',
        )
        compiler_pairs = {
            name: {lane: [] for lane in MODES}
            for name in compiler_pair_names
        }
        for session_index in range(args.sessions):
            order = [(compiler, lane) for compiler in binaries
                     for lane in MODES]
            rng.shuffle(order)
            session = {}
            for compiler, lane in order:
                result = run([binaries[compiler], '--threads', '1',
                              '--gpu', 'off', '--', MODES[lane], args.items])
                elapsed_us = parse_output(result.stdout, expected)
                session[f'{compiler}_{lane}'] = elapsed_us
                samples[compiler][lane].append(elapsed_us)
            for lane in MODES:
                compiler_pairs['static_callback_over_upstream'][lane].append(
                    session[f'static_callback_{lane}'] / session[f'upstream_{lane}'])
                compiler_pairs['fold_region_over_static_callback'][lane].append(
                    session[f'fold_region_{lane}'] /
                    session[f'static_callback_{lane}'])
                compiler_pairs['fold_region_over_upstream'][lane].append(
                    session[f'fold_region_{lane}'] / session[f'upstream_{lane}'])
            for compiler in binaries:
                direct = session[f'{compiler}_handwritten']
                for lane in ('materialized', 'transducer'):
                    implementation_ratios[compiler][lane].append(
                        session[f'{compiler}_{lane}'] / direct)
            sessions.append(session)

        timings = {}
        for compiler in binaries:
            medians = {lane: statistics.median(samples[compiler][lane])
                       for lane in MODES}
            timings[compiler] = {
                'samples_us': samples[compiler],
                'median_elapsed_us': medians,
                'median_nanoseconds_per_source_item': {
                    lane: medians[lane] * 1000 / args.items for lane in MODES
                },
                'paired_ratios_over_handwritten': {
                    lane: {
                        'median': statistics.median(implementation_ratios[compiler][lane]),
                        'bootstrap_95_interval': bootstrap_interval(
                            implementation_ratios[compiler][lane],
                            args.seed + (10 if compiler == 'upstream' else
                                         20 if compiler == 'static_callback' else 30)
                            + index),
                        'session_ratios': implementation_ratios[compiler][lane],
                    }
                    for index, lane in enumerate(('materialized', 'transducer'))
                },
            }

        compiler_comparisons = {}
        for pair_index, pair_name in enumerate(compiler_pair_names):
            compiler_comparisons[pair_name] = {}
            for lane_index, lane in enumerate(MODES):
                ratios = compiler_pairs[pair_name][lane]
                compiler_comparisons[pair_name][lane] = {
                    'median': statistics.median(ratios),
                    'paired_bootstrap_95_interval': bootstrap_interval(
                        ratios, args.seed + pair_index * 10 + lane_index + 1),
                    'session_ratios': ratios,
                }

        report = {
            'measured_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'map plus even-filter plus ordered hash fold over a runtime-built List<U32>',
            'base_commit': '2f50df1ed36fcc3ebe6c75a2046e94001a44645d',
            'fixture': str(FIXTURE.relative_to(ROOT)),
            'fixture_sha256': sha256(FIXTURE),
            'benchmark_runner_sha256': sha256(Path(__file__).resolve()),
            'upstream': upstream_report,
            'static_callback': static_report,
            'fold_region_candidate': fold_region_report,
            'items_per_sample': args.items,
            'sessions': args.sessions,
            'session_order': 'all compiler/lane runs randomized within each session; matched by session index',
            'timing_unit': 'microseconds from the native monotonic clock; input construction occurs before the timed interval',
            'time_per_item_unit': 'nanoseconds per source element, derived from median microseconds / input length',
            'correctness': correctness,
            'allocation_note': 'heap allocation/free and dynamic List constructor counts use separate instrumented -O3 C binaries; allocation results are not timing results',
            'allocations': allocation_results,
            'timings': timings,
            'compiler_comparisons': compiler_comparisons,
            'paired_sessions': sessions,
            'environment': {
                'platform': platform.platform(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'python': platform.python_version(),
                'clang': run(['clang', '--version']).stdout.splitlines()[0],
            },
        }
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({
            'output': str(args.output),
            'allocation_results': allocation_results,
            'median_elapsed_us': {
                name: value['median_elapsed_us'] for name, value in timings.items()
            },
            'nanoseconds_per_source_item': {
                name: value['median_nanoseconds_per_source_item']
                for name, value in timings.items()
            },
            'ratios_to_handwritten': {
                name: {
                    lane: value['median']
                    for lane, value in value['paired_ratios_over_handwritten'].items()
                }
                for name, value in timings.items()
            },
            'paired_compiler_comparisons': {
                pair: {lane: value['median'] for lane, value in lanes.items()}
                for pair, lanes in compiler_comparisons.items()
            },
        }, indent=2))


main()
