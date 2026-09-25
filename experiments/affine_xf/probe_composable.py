#!/usr/bin/env python3
"""Check type-indexed configuration and composed affine Xf semantics."""

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
    with tempfile.TemporaryDirectory(prefix='affine-composable-') as temp_name:
        temp = Path(temp_name)
        for fixture, expected in [('config_functor_probe.bend', '10'),
                                  ('composable_xf_probe.bend', '5'),
                                  ('staged_value_elaboration.bend', '5'),
                                  ('staged_range_elaboration.bend', '25'),
                                  ('staged_generic_elaboration.bend', '5'),
                                  ('callback_handoff.bend', '6')]:
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
            if fixture == 'composable_xf_probe.bend' and args.expect_static_erasure:
                emitted = js.read_text()
                assert '{$: "R2"' not in emitted
                print('PASS composed reducer records erased')
            if fixture == 'callback_handoff.bend':
                emitted = js.read_text()
                print('SHAPE ordinary callback handoff in loop',
                      'run_loop($apply_step$(run_clo' in emitted)
            if fixture == 'staged_generic_elaboration.bend':
                emitted = js.read_text()
                handoff = 'run_loop($composable_xf_probe$take_step$(run_clo'
                if args.expect_static_erasure:
                    assert handoff in emitted
                print('SHAPE generic stage callback handoff in loop',
                      handoff in emitted)
            if fixture == 'staged_value_elaboration.bend' and args.expect_static_erasure:
                emitted = js.read_text()
                assert 'run_loop($composable_xf_probe$take_step$(run_clo' not in emitted
                print('PASS staged template recipe has no callback handoff')


if __name__ == '__main__':
    main()
