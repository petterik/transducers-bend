#!/usr/bin/env python3
"""Check bounded ~?AUTO inference in the isolated compiler candidate."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ENV = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
POSITIVE = {'auto_unrelated_type.bend': '7',
            'rank2_auto_holes.bend': '2n',
            'rank2_auto_partial.bend': '2n',
            'rank2_auto_partial_custom.bend': '[5, 0]',
            'rank2_auto_all.bend': '2n',
            'rank2_auto_rf.bend': '7',
            'rank2_auto_api.bend': '([3, 2, 9], 5, [2n, 1n], [9])'}
NEGATIVE = {
    'auto_ambiguous_rejected.bend':
        '~?AUTO solved by a unique structural type match',
    'auto_open_provider_rejected.bend':
        'Code is a variable here, not comptime',
    'rank2_static_reuse_rejected.bend':
        'xf (consumed more than once)',
    'auto_rf_mismatch_rejected.bend':
        '~?AUTO solved by a unique structural type match',
    'auto_rf_reuse_rejected.bend':
        'rf (consumed more than once)',
    'auto_into_mismatch_rejected.bend':
        'expected : U32',
}


def run(*args):
    return subprocess.run([str(arg) for arg in args], env=ENV,
                          capture_output=True, text=True, timeout=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path, required=True)
    args = parser.parse_args()
    compiler = args.bend_main.resolve()
    with tempfile.TemporaryDirectory(prefix='auto-inference-') as name:
        temp = Path(name)
        for fixture, expected in POSITIVE.items():
            js = temp / (fixture + '.js')
            native = temp / fixture.removesuffix('.bend')
            result = run('bun', compiler, HERE / fixture,
                         '-o', js, '-o', native)
            assert result.returncode == 0, \
                (fixture, result.stdout, result.stderr)
            for lane, command in [('JS', ('bun', js)),
                                  ('native', (native, '--threads', '1', '--gpu', 'off'))]:
                result = run(*command)
                assert result.returncode == 0 and result.stdout.strip() == expected, \
                    (fixture, lane, result.stdout, result.stderr)
                print('PASS', fixture, lane)
            emitted = js.read_text()
            assert '{$: "Reducer"' not in emitted
            print('PASS closed reducer code shape', fixture)
        for fixture, diagnostic in NEGATIVE.items():
            result = run('bun', compiler, HERE / fixture,
                         '-o', temp / (fixture + '.js'))
            assert result.returncode != 0 and diagnostic in result.stderr, \
                (fixture, result.returncode, result.stdout, result.stderr)
            print('PASS expected checker refusal', fixture)


if __name__ == '__main__':
    main()
