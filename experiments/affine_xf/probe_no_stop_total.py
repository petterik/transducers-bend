#!/usr/bin/env python3
"""Check the typed total-fold experiment across Bend execution lanes."""

import argparse
from pathlib import Path
import subprocess
import tempfile

from measure_explicit_types import ENV


HERE = Path(__file__).resolve().parent
SEMANTICS = HERE / 'no_stop_total_semantics.bend'
REJECT = HERE / 'no_stop_total_reject.bend'
EXPECTED = ('(2048, 2048, 2048, 2048, 2048, '
            '1573376, 1573376, 1573376, 1573376, 1573376)')


def run(*args):
    return subprocess.run([str(arg) for arg in args], env=ENV,
                          capture_output=True, text=True, timeout=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend-main', type=Path, required=True)
    compiler = parser.parse_args().bend_main.resolve()
    with tempfile.TemporaryDirectory(prefix='no-stop-probe-') as name:
        temp = Path(name)
        result = run('bun', compiler, SEMANTICS)
        assert result.returncode == 0 and result.stdout.strip() == EXPECTED, \
            ('value', result.returncode, result.stdout, result.stderr)
        result = run('bun', compiler, SEMANTICS,
                     '-o', temp / 'semantics.js', '-o', temp / 'semantics')
        assert result.returncode == 0, (result.stdout, result.stderr)
        for lane, command in [('JS', ('bun', temp / 'semantics.js')),
                              ('native', (temp / 'semantics', '--threads', '1', '--gpu', 'off'))]:
            result = run(*command)
            assert result.returncode == 0 and result.stdout.strip() == EXPECTED, \
                (lane, result.returncode, result.stdout, result.stderr)
            print('PASS total fold', lane)
        result = run('bun', compiler, REJECT, '--check-only')
        assert result.returncode != 0 and 'expected : U32' in result.stderr \
            and 'observed : ../../transduce.Control' in result.stderr, \
            (result.returncode, result.stdout, result.stderr)
        print('PASS stopping step rejected by total fold type')


if __name__ == '__main__':
    main()
