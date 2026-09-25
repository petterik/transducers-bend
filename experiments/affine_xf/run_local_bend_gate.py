#!/usr/bin/env python3
"""Run Bend's upstream test gate locally without editing the Bend checkout.

The upstream gate assumes an SSH mini cluster. This copies its current source
to a temporary directory, replaces the transport and host-specific paths, and
limits build concurrency. Test discovery, checkup, JS/native builds, runs, and
verdict remain upstream.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


BEND = Path(__file__).resolve().parents[3] / 'bend'


def replace_once(source, old, new):
    assert source.count(old) == 1, f'gate source changed: {old[:80]}'
    return source.replace(old, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bend', type=Path, default=BEND)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert args.workers > 0
    bend = args.bend.resolve()
    bun = shutil.which('bun')
    assert bun, 'bun must be on PATH'

    with tempfile.TemporaryDirectory(prefix='bend-local-gate-') as temp:
        temp = Path(temp)
        gate_dir = temp / 'gates'
        gate_dir.mkdir()
        library = (bend / 'gates/_lib.ts').read_text()
        test = (bend / 'gates/test.ts').read_text()
        library = replace_once(library,
            'export const ROOT = path.join(import.meta.dirname, "..");',
            f'export const ROOT = {json.dumps(str(bend))};')
        library = replace_once(library,
            'export const BUN = "/usr/local/bun/bin/bun";',
            f'export const BUN = {json.dumps(bun)};')
        library, count = re.subn(
            r'export async function ssh\([\s\S]*?\n}\n\nfunction sleep',
            'export async function ssh(node: number, script: string, '
            'input?: Buffer | string, timeout?: number): Promise<Exec> {\n'
            '  return exec("sh", ["-c", script], input, timeout);\n'
            '}\n\nfunction sleep', library, count=1)
        assert count == 1, 'SSH transport changed'
        library, count = re.subn(
            r'export async function node_lock\(\): Promise<number\[]> '
            r'{[\s\S]*?\n}\n\n// Packs',
            'export async function node_lock(): Promise<number[]> {\n'
            f'  return Array.from({{ length: {args.workers} }}, (_, i) => i);\n'
            '}\n\n// Packs', library, count=1)
        assert count == 1, 'node selection changed'
        test = replace_once(test, 'd=$HOME/bend-test/${tag}',
                            f'd={temp}/test/${{tag}}')
        test = replace_once(test, 'xargs -P 10 -L 1',
                            'xargs -P 2 -L 1')
        (gate_dir / '_lib.ts').write_text(library)
        (gate_dir / 'test.ts').write_text(test)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('w') as output:
            result = subprocess.run([bun, str(gate_dir / 'test.ts')],
                                    stdout=output, stderr=subprocess.STDOUT,
                                    cwd=bend, timeout=45 * 60,
                                    env={**os.environ,
                                         'BEND_NO_TELEMETRY': '1',
                                         'CLANG_MODULE_CACHE_PATH':
                                             str(temp / 'clang-cache')})
    print(f'Local Bend gate exit {result.returncode}; output: {args.output}')
    print('\n'.join(args.output.read_text().splitlines()[-30:]))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
