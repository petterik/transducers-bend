#!/usr/bin/env python3
"""Check the erased-code, owned-config representation against Bend main."""

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
    with tempfile.TemporaryDirectory(prefix='affine-type-index-') as temp_name:
        temp = Path(temp_name)
        for fixture in ('type_indexed_plan.bend', 'rank2_config_plan.bend'):
            js = temp / (fixture + '.js')
            native = temp / fixture.removesuffix('.bend')
            build = run('bun', compiler, HERE / fixture,
                        '-o', js, '-o', native)
            assert build.returncode == 0, (fixture, build.stdout, build.stderr)
            for lane, command in [('JS', ('bun', js)),
                                  ('native', (native, '--threads', '1', '--gpu', 'off'))]:
                result = run(*command)
                assert result.returncode == 0 and result.stdout.strip() == '5', \
                    (fixture, lane, result.stdout, result.stderr)
                print('PASS', fixture, lane)
            if args.expect_static_erasure:
                emitted = js.read_text()
                assert '{$: "Reducer"' not in emitted
                print('PASS no runtime Reducer record in', fixture)

        blocked = run('bun', compiler, HERE / 'rank2_type_indexed_plan.bend',
                      '-o', temp / 'rank2.js')
        assert blocked.returncode != 0 and 'transduce.Config' in blocked.stderr, \
            (blocked.returncode, blocked.stdout, blocked.stderr)
        print('PASS general reducer transform rejected at dependent Config')


if __name__ == '__main__':
    main()
