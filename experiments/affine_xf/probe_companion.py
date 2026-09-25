#!/usr/bin/env python3
"""Check the isolated owner-qualified companion conversion experiment."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ENV = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
NEGATIVE = {
    'companion_missing_rejected.bend':
        '~?AUTO solved by a unique structural type match',
    'companion_wrong_return_rejected.bend':
        'a companion returning the expected type',
    'companion_reuse_rejected.bend':
        'pair (consumed more than once)',
    'companion_orphan_rejected.bend':
        '~?AUTO solved by a unique structural type match',
    'companion_unmarked_rejected.bend':
        'expected : Wrapped',
    'companion_bad_marker_rejected.bend':
        'expected : Wrapped',
}


def run(*args):
    return subprocess.run([str(arg) for arg in args], env=ENV,
                          capture_output=True, text=True, timeout=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path, required=True)
    args = parser.parse_args()
    compiler = args.bend_main.resolve()
    with tempfile.TemporaryDirectory(prefix='companion-probe-') as name:
        temp = Path(name)
        fixture = HERE / 'rank2_companion_raw.bend'
        js = temp / 'raw.js'
        native = temp / 'raw'
        result = run('bun', compiler, fixture, '-o', js, '-o', native)
        assert result.returncode == 0, (result.stdout, result.stderr)
        for lane, command in [('JS', ('bun', js)),
                              ('native', (native, '--threads', '1', '--gpu', 'off'))]:
            result = run(*command)
            assert result.returncode == 0 and result.stdout.strip() == '(5, (1, 1), 3, [2, 1, 9], 2n, 3, [2, 1, 9])', \
                (lane, result.returncode, result.stdout, result.stderr)
            print('PASS raw companion', lane)
        assert '{$: "Reducer"' not in js.read_text()
        print('PASS closed reducer code shape')
        core = HERE / 'companion_core_sources.bend'
        result = run('bun', compiler, core,
                     '-o', temp / 'core.js', '-o', temp / 'core')
        assert result.returncode == 0, (result.stdout, result.stderr)
        for lane, command in [('JS', ('bun', temp / 'core.js')),
                              ('native', (temp / 'core', '--threads', '1', '--gpu', 'off'))]:
            result = run(*command)
            assert result.returncode == 0 and result.stdout.strip() == '(3, 3, 8)', \
                (lane, result.returncode, result.stdout, result.stderr)
            print('PASS core Range/Array sources', lane)
        matrix = HERE / 'companion_semantics_matrix.bend'
        result = run('bun', compiler, matrix,
                     '-o', temp / 'matrix.js', '-o', temp / 'matrix')
        assert result.returncode == 0, (result.stdout, result.stderr)
        for lane, command in [('JS', ('bun', temp / 'matrix.js')),
                              ('native', (temp / 'matrix', '--threads', '1', '--gpu', 'off'))]:
            result = run(*command)
            assert result.returncode == 0 and result.stdout.strip() == \
                '(6, 14, 26, [4, 2], [3, 2, 1], 7, 3)', \
                (lane, result.returncode, result.stdout, result.stderr)
            print('PASS source/stage semantics matrix', lane)
        reducible = HERE / 'reducible_cat_probe.bend'
        result = run('bun', compiler, reducible,
                     '-o', temp / 'reducible.js', '-o', temp / 'reducible')
        assert result.returncode == 0, (result.stdout, result.stderr)
        reducible_js = (temp / 'reducible.js').read_text()
        assert '{$: "Reducer"' not in reducible_js
        assert '{$: "Source"' not in reducible_js
        expected_reducible = ('(42, 42, 14, 14, [12, 2, 11, 1], '
                              '[12, 2, 11, 1], '
                              'rank2_auto_sources.Bag{[2, 11, 1, 9], 1})')
        for lane, command in [('JS', ('bun', temp / 'reducible.js')),
                              ('native', (temp / 'reducible', '--threads', '1', '--gpu', 'off'))]:
            result = run(*command)
            assert result.returncode == 0 and result.stdout.strip() == expected_reducible, \
                (lane, result.returncode, result.stdout, result.stderr)
            print('PASS reducible cat semantics', lane)
        unrelated = HERE / 'companion_unrelated.bend'
        result = run('bun', compiler, unrelated,
                     '-o', temp / 'unrelated.js', '-o', temp / 'unrelated')
        assert result.returncode == 0, (result.stdout, result.stderr)
        for lane, command in [('JS', ('bun', temp / 'unrelated.js')),
                              ('native', (temp / 'unrelated', '--threads', '1', '--gpu', 'off'))]:
            result = run(*command)
            assert result.returncode == 0 and result.stdout.strip() == '7', \
                (lane, result.returncode, result.stdout, result.stderr)
            print('PASS unrelated marked companion', lane)
        boundary = HERE / 'companion_boundary_main.bend'
        result = run('bun', compiler, boundary)
        assert result.returncode == 0 and result.stdout.strip() == '(7, 9, 11)', \
            ('value', result.returncode, result.stdout, result.stderr)
        print('PASS imported template companion value mode')
        result = run('bun', compiler, boundary, '--checkup')
        assert result.returncode == 0, (result.stdout, result.stderr)
        result = run('bun', compiler, boundary,
                     '-o', temp / 'boundary.js', '-o', temp / 'boundary')
        assert result.returncode == 0, (result.stdout, result.stderr)
        for lane, command in [('JS', ('bun', temp / 'boundary.js')),
                              ('native', (temp / 'boundary', '--threads', '1', '--gpu', 'off'))]:
            result = run(*command)
            assert result.returncode == 0 and result.stdout.strip() == '(7, 9, 11)', \
                (lane, result.returncode, result.stdout, result.stderr)
            print('PASS imported template companion', lane)
        for fixture, diagnostic in NEGATIVE.items():
            result = run('bun', compiler, HERE / fixture,
                         '-o', temp / (fixture + '.js'))
            assert result.returncode != 0 and diagnostic in result.stderr, \
                (fixture, result.returncode, result.stdout, result.stderr)
            print('PASS expected refusal', fixture)


if __name__ == '__main__':
    main()
