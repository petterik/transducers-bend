#!/usr/bin/env python3
"""Check the isolated local-alias specialization experiment."""

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
                          capture_output=True, text=True, timeout=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path, required=True)
    args = parser.parse_args()
    compiler = args.bend_main.resolve()
    with tempfile.TemporaryDirectory(prefix='affine-alias-probe-') as temp_name:
        temp = Path(temp_name)
        for fixture, expected in [
            ('local_rf_alias.bend', '6'),
            ('local_xf_alias.bend', '9'),
            ('runtime_take_recipe.bend', '5'),
            ('custom_source_alias.bend', '5'),
        ]:
            js = temp / (fixture + '.js')
            native = temp / fixture.removesuffix('.bend')
            build = run('bun', compiler, HERE / fixture,
                        '-o', js, '-o', native)
            assert build.returncode == 0, (fixture, build.stdout, build.stderr)
            for lane, command in [('JS', ('bun', js)),
                                  ('native', (native, '--threads', '1', '--gpu', 'off'))]:
                result = run(*command)
                assert result.returncode == 0 and result.stdout.strip() == expected, \
                    (fixture, lane, result.stdout, result.stderr)
                print('PASS', fixture, lane, expected)
            if fixture == 'local_xf_alias.bend':
                emitted = js.read_text()
                assert '{$: "Xf"' not in emitted
                assert '{$: "Reducer"' not in emitted
                print('PASS local Xf and Reducer erased from JS')

        for fixture, expected in [
            ('runtime_rf_capture_rejected.bend', 'k is a variable here, not comptime'),
            ('runtime_rf_unknown_rejected.bend', 'rf is a variable here, not comptime'),
            ('computed_xf_alias_rejected.bend', 'xf is a variable here, not comptime'),
            ('runtime_rf_rejected.bend', 'rf (consumed more than once)'),
            ('runtime_xf_rejected.bend', 'xf is a variable here, not comptime'),
        ]:
            result = run('bun', compiler, HERE / fixture,
                         '-o', temp / (fixture + '.js'))
            assert result.returncode != 0 and expected in result.stderr, \
                (fixture, result.returncode, result.stdout, result.stderr)
            print('PASS', fixture, 'rejected at expected boundary')


if __name__ == '__main__':
    main()
