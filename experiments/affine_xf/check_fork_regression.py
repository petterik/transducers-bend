#!/usr/bin/env python3
"""Compare the fork checker with bendlang/main on upstream Bend tests locally."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
BEND = ROOT.parent / 'bend'
ENV = {**os.environ, 'BEND_NO_TELEMETRY': '1'}


def git(*args):
    return subprocess.check_output(['git', '-C', str(BEND), *args])


def run(compiler, fixture, flag):
    result = subprocess.run(['bun', str(compiler), str(fixture), flag],
                            capture_output=True, text=True, env=ENV,
                            timeout=60)
    return result.returncode, result.stdout, result.stderr


def upstream_compiler(temp, ref):
    target = temp / 'upstream'
    shutil.copytree(BEND / 'bend2', target,
                    ignore=shutil.ignore_patterns('docs', 'pack'))
    for name in ('bend.ts', 'comp.ts'):
        (target / name).write_bytes(git('show', f'{ref}:bend2/{name}'))
    return target / 'main.ts'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fork-main', type=Path,
                        default=BEND / 'bend2' / 'main.ts')
    parser.add_argument('--upstream-ref', default='bendlang/main')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    listed = set(git('ls-tree', '-r', '--name-only', args.upstream_ref,
                     'tests').decode().splitlines())
    fixtures = [BEND / name for name in sorted(listed)
                if name.endswith('.bend') and (BEND / name).is_file()]
    positive, other = [], []
    for fixture in fixtures:
        want = '\n'.join(line[2:] for line in fixture.read_text().splitlines()
                         if line.startswith('#|'))
        (other if not want or want.startswith('Error:') else positive).append(
            fixture)
    mismatches = []
    with tempfile.TemporaryDirectory(prefix='bend-regression-') as name:
        upstream = upstream_compiler(Path(name), args.upstream_ref)
        for start in range(0, len(positive), 60):
            batch = positive[start:start + 60]
            # Imports must be relative to a file inside the same parent as
            # the sibling bend checkout; no source in that checkout is edited.
            with tempfile.TemporaryDirectory(prefix='.bend-check-',
                                             dir=ROOT) as scratch:
                fixture = Path(scratch) / 'main.bend'
                fixture.write_text(''.join(
                    f'import {os.path.relpath(path, fixture.parent)} as '
                    f'regression_{index}\n'
                    for index, path in enumerate(batch)))
                before = run(upstream, fixture, '--checkup')
                after = run(args.fork_main, fixture, '--checkup')
                if before != after:
                    mismatches.append({'batch': start,
                                       'files': [str(p) for p in batch],
                                       'upstream': before,
                                       'fork': after})

        def compare(fixture):
            before = run(upstream, fixture, '--check-only')
            after = run(args.fork_main, fixture, '--check-only')
            return None if before == after else {
                'file': str(fixture), 'upstream': before, 'fork': after}

        with ThreadPoolExecutor(max_workers=4) as pool:
            mismatches.extend(m for m in pool.map(compare, other)
                              if m is not None)
    report = {'upstream_ref': args.upstream_ref,
              'positive_checkup': len(positive),
              'other_check_only': len(other),
              'mismatches': mismatches}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"PASS: {len(positive)} positive checkup + {len(other)} "
          f"other check-only fixtures; {len(mismatches)} mismatches"
          if not mismatches else json.dumps(report, indent=2))
    if mismatches:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
