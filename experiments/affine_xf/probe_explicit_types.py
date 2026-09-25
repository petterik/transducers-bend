#!/usr/bin/env python3
"""Check an Xf with explicit reducer configuration and state types."""

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
    parser.add_argument('--expect-static-erasure', action='store_true')
    args = parser.parse_args()
    compiler = args.bend_main.resolve()
    with tempfile.TemporaryDirectory(prefix='affine-explicit-types-') as temp_name:
        temp = Path(temp_name)
        for fixture, expected in [('explicit_reducer_types.bend', '5'),
                                  ('explicit_reducer_list.bend', '[3, 2, 9]'),
                                  ('explicit_reducer_type_change.bend', '3n'),
                                  ('explicit_reducer_zero.bend', '0'),
                                  ('explicit_reducer_empty.bend', '0'),
                                  ('explicit_reducer_stop.bend', '104')]:
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
                print('PASS', fixture, lane)
            emitted = js.read_text()
            r2_records = emitted.count('{$: "R2"')
            xf_records = emitted.count('{$: "Xf"')
            if args.expect_static_erasure:
                assert r2_records == 0, (fixture, r2_records)
                assert xf_records == 1, (fixture, xf_records)
            print('EMITTED', fixture, 'R2 records', r2_records,
                  'Xf records', xf_records)

        rejected = run('bun', compiler,
                       HERE / 'explicit_reducer_reuse_rejected.bend',
                       '-o', temp / 'reuse.js')
        assert rejected.returncode != 0 and \
            'xf (consumed more than once)' in rejected.stderr, \
            (rejected.returncode, rejected.stdout, rejected.stderr)
        print('PASS owned Xf reuse rejected')


if __name__ == '__main__':
    main()
