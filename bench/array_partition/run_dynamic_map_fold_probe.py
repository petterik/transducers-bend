#!/usr/bin/env python3
"""Compare dynamic List.map/fold with the streaming transducer fold."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import tempfile
import time


HERE = Path(__file__).resolve().parent
PROBE = HERE / 'dynamic_map_fold_probe.bend'
LANES = {
    'materialized': HERE / 'dynamic_map_fold_bench_materialized.bend',
    'stream': HERE / 'dynamic_map_fold_bench_stream.bend',
}
SAMPLES = 16
INPUT_ITEMS = 200_000
INPUTS_PER_SAMPLE = 8


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd, env, timeout=120):
    return subprocess.run(cmd, env=env, capture_output=True, text=True,
                          timeout=timeout, check=True)


def build_probe(compiler, root, env):
    stem = root / 'correctness'
    started = time.perf_counter()
    run(['bun', str(compiler), str(PROBE), '-o', str(stem),
         '-o', str(stem.with_suffix('.js')),
         '-o', str(stem.with_suffix('.c'))], env)
    build_seconds = time.perf_counter() - started
    js = run(['node', str(stem.with_suffix('.js'))], env).stdout.strip()
    native = run([str(stem), '--threads', '1', '--gpu', 'off'], env).stdout.strip()
    assert js == native and re.fullmatch(r'\(True\{\}, True\{\}\)', js), (js, native)
    return {
        'build_seconds': build_seconds,
        'c_bytes': stem.with_suffix('.c').stat().st_size,
        'js_bytes': stem.with_suffix('.js').stat().st_size,
        'js_and_native_output': js,
    }


def build_lane(compiler, lane, root, env):
    stem = root / lane
    source = LANES[lane]
    started = time.perf_counter()
    run(['bun', str(compiler), str(source), '-o', str(stem.with_suffix('.c'))], env)
    build_seconds = time.perf_counter() - started
    source_c = stem.with_suffix('.c')
    binary = stem.with_suffix('.bin')
    run(['clang', '-O3', str(source_c), '-o', str(binary)], env)

    instrumented = source_c.read_text()
    alloc_mark = 'INLINE Loc heap_alloc(Env e, Cls cls) {'
    main_mark = '  io_sync();\n  return code;'
    assert alloc_mark in instrumented and main_mark in instrumented
    instrumented = instrumented.replace(
        alloc_mark,
        'static u64 ALLOC_CALLS = 0;\n' + alloc_mark + '\n  ALLOC_CALLS += 1;',
        1)
    instrumented = instrumented.replace(
        main_mark,
        '  io_sync();\n  fprintf(stderr, "ALLOC_CALLS=%llu\\n", '
        '(unsigned long long)ALLOC_CALLS);\n  return code;', 1)
    inst_c = stem.with_name(stem.name + '-alloc.c')
    inst_bin = stem.with_name(stem.name + '-alloc')
    inst_c.write_text(instrumented)
    run(['clang', '-O3', str(inst_c), '-o', str(inst_bin)], env)
    alloc_run = run([str(inst_bin), '--threads', '1', '--gpu', 'off'], env)
    allocation_calls = int(re.search(r'ALLOC_CALLS=(\d+)', alloc_run.stderr).group(1))

    return {
        'build_seconds': build_seconds,
        'c_bytes': source_c.stat().st_size,
        'c_sha256': sha256(source_c),
        'native_binary': str(binary),
        'allocation_calls': allocation_calls,
    }


def measure_pair(binaries, env, seed):
    rng = random.Random(seed)
    pairs = []
    for _ in range(SAMPLES):
        order = ['materialized', 'stream']
        rng.shuffle(order)
        sample = {}
        for lane in order:
            out = run([binaries[lane], '--threads', '1', '--gpu', 'off'],
                      env).stdout.strip().split()
            total, elapsed_us = map(int, out)
            sample[lane] = {'total': total, 'elapsed_us': elapsed_us}
        assert sample['materialized']['total'] == sample['stream']['total']
        sample['stream_over_materialized'] = (
            sample['stream']['elapsed_us'] / sample['materialized']['elapsed_us'])
        pairs.append(sample)
    ratios = [x['stream_over_materialized'] for x in pairs]
    med = {lane: statistics.median(x[lane]['elapsed_us'] for x in pairs)
           for lane in binaries}
    rng = random.Random(seed + 1)
    bootstrap = sorted(statistics.median(
        ratios[rng.randrange(len(ratios))] for _ in ratios) for _ in range(20000))
    return {
        'paired_samples': pairs,
        'median_us_per_eight_inputs': med,
        'median_us_per_input': {lane: value / INPUTS_PER_SAMPLE
                                for lane, value in med.items()},
        'median_stream_over_materialized': statistics.median(ratios),
        'paired_bootstrap_95_interval': [bootstrap[500], bootstrap[19499]],
    }


def compiler_report(compiler, label, root, env):
    root.mkdir(parents=True, exist_ok=True)
    comp = compiler.parent / 'comp.ts'
    report = {
        'main_sha256': sha256(compiler),
        'comp_sha256': sha256(comp),
        'correctness': build_probe(compiler, root, env),
    }
    lanes = {lane: build_lane(compiler, lane, root, env) for lane in LANES}
    report['lanes'] = {
        lane: {key: value for key, value in data.items() if key != 'native_binary'}
        for lane, data in lanes.items()
    }
    report['timings'] = measure_pair(
        {lane: data['native_binary'] for lane, data in lanes.items()},
        env, 20260924 + (label == 'candidate'))
    return report


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--upstream-main', type=Path, required=True,
                    help='bendlang/bend main.ts from the checked-out main branch')
parser.add_argument('--candidate-main', type=Path, required=True,
                    help='isolated static-callback candidate main.ts')
parser.add_argument('--output', type=Path, required=True,
                    help='write the raw report as JSON')
args = parser.parse_args()

upstream = args.upstream_main.resolve()
candidate = args.candidate_main.resolve()
env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
with tempfile.TemporaryDirectory(prefix='dynamic-map-fold-') as name:
    temp = Path(name)
    report = {
        'scope': 'dynamic List map/fold versus the public map transducer over a List source',
        'base_commit': '2f50df1ed36fcc3ebe6c75a2046e94001a44645d',
        'fixture_sha256': sha256(PROBE),
        'benchmark_fixtures_sha256': {k: sha256(v) for k, v in LANES.items()},
        'runner_sha256': sha256(Path(__file__).resolve()),
        'values_per_input': INPUT_ITEMS,
        'inputs_per_sample': INPUTS_PER_SAMPLE,
        'paired_sessions': SAMPLES,
        'timing_unit': 'microseconds from BenchClock.now_us; source construction is outside the timed region',
        'allocation_note': 'heap_alloc call counts are from separate instrumented binaries',
        'upstream': compiler_report(upstream, 'upstream', temp / 'upstream', env),
        'candidate': compiler_report(candidate, 'candidate', temp / 'candidate', env),
    }
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
