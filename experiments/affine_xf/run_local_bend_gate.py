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
DESKTOP_CASES = {'gfx_clicks': 'clicks', 'gfx_window': 'window'}


def replace_once(source, old, new):
    assert source.count(old) == 1, f'gate source changed: {old[:80]}'
    return source.replace(old, new)


def gate_failures(log):
    matches = re.findall(
        r'^FAIL (\S+) \[(\w+)\]\n  expected: .*\n  observed: (.*)$',
        log, re.MULTILINE)
    return {(name, lane): observed.replace('\\n', '\n')
            for name, lane, observed in matches}


def upstream_compiler(bend, temp):
    target = temp / 'upstream'
    shutil.copytree(bend / 'bend2', target,
                    ignore=shutil.ignore_patterns('docs', 'pack'))
    for name in ('bend.ts', 'comp.ts', 'main.ts'):
        source = subprocess.check_output(
            ['git', '-C', str(bend), 'show',
             f'bendlang/main:bend2/{name}'])
        (target / name).write_bytes(source)
    return target / 'main.ts'


def native_observation(compiler, source, binary, env):
    build = subprocess.run(['bun', str(compiler), str(source),
                            '-o', str(binary)], env=env,
                           capture_output=True, text=True, timeout=180)
    if build.returncode != 0:
        raise RuntimeError(f'upstream build failed for {source}: '
                           + build.stdout + build.stderr)
    try:
        run = subprocess.run([str(binary)], env=env,
                             capture_output=True, timeout=5)
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b'') + (error.stderr or b'')
        return output.decode(errors='replace').strip() + (
            '\ntimeout' if output else 'timeout')
    observed = (run.stdout + run.stderr).decode(errors='replace').strip()
    if run.returncode != 0:
        observed += ('\n' if observed else '') + f'exit {run.returncode}'
    return observed


def desktop_only_matches_upstream(bend, temp, failures, env):
    if set(failures) != {(name, 'c') for name in DESKTOP_CASES}:
        return False
    compiler = upstream_compiler(bend, temp)
    for name, file in DESKTOP_CASES.items():
        observed = native_observation(
            compiler, bend / 'tests' / 'gfx' / f'{file}.bend',
            temp / f'upstream-{file}', env)
        if observed != failures[(name, 'c')]:
            print(f'{name}: fork observed {failures[(name, "c")]!r}; '
                  f'upstream observed {observed!r}')
            return False
    return True


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
        env = {**os.environ, 'BEND_NO_TELEMETRY': '1',
               'CLANG_MODULE_CACHE_PATH': str(temp / 'clang-cache')}
        with args.output.open('w') as output:
            result = subprocess.run([bun, str(gate_dir / 'test.ts')],
                                    stdout=output, stderr=subprocess.STDOUT,
                                    cwd=bend, timeout=45 * 60,
                                    env=env)
        log = args.output.read_text()
        failures = gate_failures(log)
        verdict = re.search(r'^PASS: (\d+) / (\d+)$', log, re.MULTILINE)
        exactly_two_failures = verdict is not None \
            and int(verdict.group(2)) - int(verdict.group(1)) == 2 \
            and len(re.findall(r'^FAIL ', log, re.MULTILINE)) == 2
        desktop_equivalent = result.returncode != 0 and exactly_two_failures \
            and desktop_only_matches_upstream(bend, temp, failures, env)
    print(f'Local Bend gate exit {result.returncode}; output: {args.output}')
    print('\n'.join(log.splitlines()[-30:]))
    if desktop_equivalent:
        print('Two native desktop graphics results match stock upstream on '
              'this host; all other gate checks passed.')
    raise SystemExit(0 if result.returncode == 0 or desktop_equivalent else 1)


if __name__ == '__main__':
    main()
