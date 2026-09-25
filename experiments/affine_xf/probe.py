#!/usr/bin/env python3
"""Reproduce the first-class xf boundary on bendlang/main."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ENV = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}


def run(*args):
    return subprocess.run([str(arg) for arg in args], env=ENV,
                          capture_output=True, text=True, timeout=60)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path, required=True)
    parser.add_argument('--expect-static-erasure', action='store_true')
    args = parser.parse_args()
    compiler = args.bend_main.resolve()

    with tempfile.TemporaryDirectory(prefix='affine-xf-probe-') as temp_name:
        temp = Path(temp_name)
        js = temp / 'rank2.js'
        native = temp / 'rank2'
        build = run('bun', compiler, HERE / 'rank2_probe.bend',
                    '-o', js, '-o', native)
        assert build.returncode == 0, build.stdout + build.stderr
        for name, command in [('JS', ('bun', js)),
                              ('native', (native, '--threads', '1', '--gpu', 'off'))]:
            result = run(*command)
            assert result.returncode == 0 and result.stdout.strip() == '9', \
                (name, result.stdout, result.stderr)
            print('PASS', name, 'closed rank-2 xf')
        if args.expect_static_erasure:
            emitted = js.read_text()
            assert '{$: "Reducer"' not in emitted
            assert '{$: "Xf"' not in emitted
            print('PASS closed xf and reducer erased from JS')

        for fixture, expected in [
            ('runtime_xf_rejected.bend', 'xf is a variable here, not comptime'),
            ('runtime_rf_rejected.bend', 'rf (consumed more than once)'),
        ]:
            result = run('bun', compiler, HERE / fixture,
                         '-o', temp / (fixture + '.js'))
            assert result.returncode != 0 and expected in result.stderr, \
                (fixture, result.returncode, result.stdout, result.stderr)
            print('PASS', fixture, 'rejected at expected boundary')


if __name__ == '__main__':
    main()
