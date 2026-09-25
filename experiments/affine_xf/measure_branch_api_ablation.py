#!/usr/bin/env python3
"""Measure mirrored public/prototype Branch folds in one program each."""
import json
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BEND = ROOT.parent / 'bend' / 'bend2' / 'main.ts'
HERE = Path(__file__).resolve().parent
VARIANTS = {
    'public_first': ('branch_api_ablation.bend', 1, 2),
    'prototype_first': ('branch_api_ablation_swapped.bend', 2, 1),
}
SESSIONS = 64
DEPTH = 19


def run(command):
    return subprocess.check_output([str(part) for part in command],
                                   cwd=ROOT, text=True).strip()


def main():
    with tempfile.TemporaryDirectory(prefix='branch-api-ablation-') as tmp:
        binaries = {}
        for variant, (fixture, _, _) in VARIANTS.items():
            c_file = Path(tmp) / f'{variant}.c'
            binary = Path(tmp) / variant
            run(['bun', BEND, HERE / fixture, '-o', c_file])
            run(['clang', '-O3', c_file, '-o', binary])
            binaries[variant] = binary
        samples = {(variant, mode): [] for variant in VARIANTS
                   for mode in range(3)}
        for session in range(SESSIONS):
            cases = list(samples)
            random.Random(20260925 + session).shuffle(cases)
            for variant, mode in cases:
                elapsed, value = map(int, run([
                    binaries[variant], '--threads', '1', '--gpu', 'off',
                    '--', mode, DEPTH]).split())
                assert value == 1 << (DEPTH - 1), (variant, mode, value)
                samples[(variant, mode)].append(elapsed)
        results = {}
        for variant, (_, public, prototype) in VARIANTS.items():
            med = {mode: statistics.median(samples[(variant, mode)])
                   for mode in range(3)}
            results[variant] = {
                'median_us': {'direct': med[0], 'public': med[public],
                              'prototype': med[prototype]},
                'public_over_direct': med[public] / med[0],
                'prototype_over_direct': med[prototype] / med[0],
            }
    print(json.dumps({'depth': DEPTH, 'sessions': SESSIONS,
                      'variants': results}, indent=2))


if __name__ == '__main__':
    main()
