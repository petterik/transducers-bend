#!/usr/bin/env python3
"""Compare sibling Bend runtime/checker benches with an archived base locally."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT.parent / "bend"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timed(argv, timeout):
    begin = time.perf_counter()
    try:
        env = dict(os.environ, CLANG_MODULE_CACHE_PATH="/tmp/bend-clang-modules")
        done = subprocess.run([str(x) for x in argv], capture_output=True,
                              text=True, timeout=timeout, env=env)
        return {"seconds": time.perf_counter() - begin,
                "exit": done.returncode, "stdout": done.stdout.strip()[-600:],
                "stderr": done.stderr.strip()[-600:]}
    except subprocess.TimeoutExpired:
        return {"seconds": time.perf_counter() - begin,
                "exit": "timeout", "stdout": "", "stderr": ""}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--runtime-mode", choices=("seq", "parallel", "gpu"),
                        default="seq")
    parser.add_argument("--skip-checker", action="store_true")
    args = parser.parse_args()
    baseline = args.baseline.resolve()
    assert args.runs > 0
    benches = sorted(p.name for p in (CURRENT / "bench/runtime").iterdir()
                     if p.is_dir() and not p.name.startswith("_"))
    checkers = sorted(p.name for p in (CURRENT / "bench/checker").iterdir()
                      if p.is_dir() and not p.name.startswith("_"))
    flags = {"seq": ["--threads", "1", "--gpu", "off"],
             "parallel": ["--threads", "8", "--gpu", "off"],
             "gpu": ["--gpu", "on"]}[args.runtime_mode]
    report = {"scope": "Local M3 Max, " + args.runtime_mode + " mode, "
              + " ".join(flags) + "; separate executable builds; process wall time includes startup; paired outputs; no M4 cluster pin comparison",
              "baseline": str(baseline), "current": str(CURRENT),
              "platform": platform.platform(), "runs": args.runs,
              "runtime_mode": args.runtime_mode,
              "timeout_seconds": args.timeout,
              "compiler_sha256": {label: digest(path / "bend2/comp.ts")
                                  for label, path in (("baseline", baseline), ("current", CURRENT))},
              "runtime": {}, "checker": {}}
    with tempfile.TemporaryDirectory(prefix="bend-upstream-local-") as temp_name:
        temp = Path(temp_name)
        for bench in benches:
            row = {"builds": {}, "runs": {"baseline": [], "current": []}}
            for label, tree in (("baseline", baseline), ("current", CURRENT)):
                binary = temp / f"{bench}-{label}"
                row["builds"][label] = timed(["bun", tree / "bend2/main.ts",
                    tree / "bench/runtime" / bench / "main.bend", "-o", binary],
                    args.timeout)
            if all(row["builds"][label]["exit"] == 0
                   for label in ("baseline", "current")):
                for n in range(args.runs):
                    for label in (("baseline", "current") if n % 2 == 0
                                  else ("current", "baseline")):
                        row["runs"][label].append(timed([
                            temp / f"{bench}-{label}", *flags], args.timeout))
            report["runtime"][bench] = row
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print("runtime", bench, [row["builds"][x]["exit"] for x in
                  ("baseline", "current")], flush=True)
        for bench in ([] if args.skip_checker else checkers):
            row = {"baseline": [], "current": []}
            for n in range(args.runs):
                for label, tree in ((("baseline", baseline), ("current", CURRENT))
                                    if n % 2 == 0 else
                                    (("current", CURRENT), ("baseline", baseline))):
                    row[label].append(timed(["bun", tree / "bend2/main.ts",
                        tree / "bench/checker" / bench / "main.bend"],
                        args.timeout))
            report["checker"][bench] = row
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print("checker", bench, flush=True)


if __name__ == "__main__":
    main()
