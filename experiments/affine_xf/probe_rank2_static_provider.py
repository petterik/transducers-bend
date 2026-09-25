#!/usr/bin/env python3
"""Check closed rank-2 stage providers and their ownership boundary."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ENV = {**os.environ, 'BEND_NO_TELEMETRY': '1',
       'CLANG_MODULE_CACHE_PATH': '/tmp/bend-clang-modules'}
POSITIVE = {
    'template_provider_composition.bend': '[0, 2, 5, 9]',
    'owned_provider_consumer_bound.bend': '5',
    'rank2_static_provider.bend': '12',
    'rank2_static_compose.bend': '7',
    'rank2_static_typed.bend': '2n',
}
NEGATIVE = {
    'rank2_runner_value_probe.bend':
        'a template applied to closed ~ arguments (R is a variable here',
    'rank2_static_reuse_rejected.bend': 'xf (consumed more than once)',
}


def run(*args):
    return subprocess.run([str(arg) for arg in args], env=ENV,
                          capture_output=True, text=True, timeout=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path, required=True)
    parser.add_argument('--expect-static-erasure', action='store_true')
    args = parser.parse_args()
    compiler = args.bend_main.resolve()
    with tempfile.TemporaryDirectory(prefix='rank2-static-provider-') as name:
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
            if args.expect_static_erasure:
                emitted = js.read_text()
                assert '{$: "Reducer"' not in emitted, fixture
                assert 'take_step$(run_clo' not in emitted, fixture
                assert 'advance$(run_clo' not in emitted, fixture
                print('PASS closed reducer code shape', fixture,
                      'js_bytes', js.stat().st_size)
        for fixture, diagnostic in NEGATIVE.items():
            result = run('bun', compiler, HERE / fixture,
                         '-o', temp / (fixture + '.js'))
            assert result.returncode != 0 and diagnostic in result.stderr, \
                (fixture, result.returncode, result.stdout, result.stderr)
            print('PASS expected checker refusal', fixture)


if __name__ == '__main__':
    main()
