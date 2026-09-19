#!/usr/bin/env python3
"""Compare an array mapcat pipeline with fused Bend and language twins.

The Bend variants run inside one persistent process so IO.now measures the
computation rather than compiler or process startup. The C, TypeScript, and
Lean twins are direct scalar references; their CPU-1 wall times are reported
separately because those programs do not share Bend's persistent-process
timer or its CPU/GPU runtime.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPILER = ROOT.parent / "bend/bend2/main.ts"
VARIANTS = ("transduced", "staged", "direct")
VARIANT_CALLS = {
    "transduced": "W.transduced",
    "staged": "W.staged",
    "direct": "W.direct",
}
LANGUAGE_FILES = {
    "c": "direct.c",
    "typescript": "direct.ts",
    "lean": "direct.lean",
}


def u32(x: int) -> int:
    return x & 0xFFFFFFFF


def work(x: int, rounds: int) -> int:
    for _ in range(rounds):
        x = u32((u32(x * 1664525) + 1013904223) ^ (x >> 13))
    return x


def feed(acc: int, x: int, rounds: int) -> int:
    normalized = work(u32(x ^ 2654435761), rounds)
    if normalized & 3:
        acc = u32(acc + normalized)
    return acc


def expected(array_depth: int, batch_depth: int, repeats: int,
             rounds: int) -> int:
    width = 1 << array_depth

    def leaf(seed: int) -> int:
        acc = 0
        for i in range(width):
            s = u32(seed + i)
            for x in (s, 1664525, 1013904223, 2654435761):
                acc = feed(acc, x, rounds)
        return acc

    def batch(p: int, seed: int) -> int:
        if p == 0:
            return leaf(seed)
        left = batch(p - 1, seed)
        right = batch(p - 1, u32(seed + (1 << (array_depth + p - 1))))
        return u32(left + right)

    one = batch(batch_depth, 0)
    answer = 0
    for _ in range(repeats):
        answer = u32(answer + one)
    return answer


def replace_tokens(source: str, values: dict[str, int]) -> str:
    for name, value in values.items():
        source = source.replace(name, str(value))
    return source


def compiler_env() -> dict[str, str]:
    return {
        **os.environ,
        "BEND_NO_TELEMETRY": "1",
        "CLANG_MODULE_CACHE_PATH": "/tmp/bend-clang-modules",
    }


def build_bend(root: Path, compiler: Path, out: Path, variant: str,
               values: dict[str, int]) -> tuple[Path, dict[str, int]]:
    common = (root / "bench/wordscan/common.bend").read_text()
    # The generated source lives in a temporary directory, so keep its source
    # import explicit rather than relying on the checkout-relative path.
    library = "./" + os.path.relpath(root / "transduce.bend", out)
    common = common.replace("import ../../transduce.bend as T",
                           f"import {library} as T")
    (out / "common.bend").write_text(replace_tokens(common, values))
    source = (root / "bench/wordscan/driver.bend").read_text()
    source = source.replace("W.transduced", VARIANT_CALLS[variant])
    source = replace_tokens(source, values)
    stem = out / variant
    bend = stem.with_suffix(".bend")
    bend.write_text(source)
    command = ["bun", str(compiler), str(bend), "-o", str(stem),
               "-o", str(stem.with_suffix(".js")),
               "-o", str(stem.with_suffix(".c"))]
    built = subprocess.run(command, env=compiler_env(), capture_output=True,
                           text=True, timeout=240)
    if built.returncode != 0:
        raise RuntimeError(built.stdout + built.stderr)
    if variant == "transduced":
        emitted = stem.with_suffix(".js").read_text()
    # This is diagnostic rather than a correctness requirement: the current
    # compiler may retain static records for the richer mapcat composition.
    emitted = stem.with_suffix(".js").read_text()
    record_count = emitted.count('{$: "Reducer"') + emitted.count(
        '{$: "Reduction"')
    return stem, {"js_records": record_count,
                  "c_bytes": stem.with_suffix(".c").stat().st_size}


def parse_bend_output(output: str, expected_value: int,
                      samples: int) -> list[int]:
    pairs = []
    for line in output.splitlines():
        fields = line.split(":")
        if len(fields) != 2:
            raise AssertionError(output)
        value, millis = map(int, fields)
        if value != expected_value:
            raise AssertionError((expected_value, output))
        pairs.append(millis)
    if len(pairs) != samples + 1:
        raise AssertionError((samples, output))
    return pairs[1:]


def run_bend(binary: Path, flags: list[str], expected_value: int,
             samples: int) -> dict[str, object]:
    run = subprocess.run([str(binary), *flags], capture_output=True,
                         text=True, timeout=240)
    if run.returncode != 0:
        message = (run.stdout + run.stderr).strip()
        return {"status": "unavailable", "reason": message[-300:]}
    times = parse_bend_output(run.stdout, expected_value, samples)
    return {"status": "ok", "samples_ms": times,
            "median_ms": statistics.median(times), "checksum": expected_value}


def external_source(root: Path, language: str, values: dict[str, int],
                    out: Path) -> Path:
    source = (root / "bench/wordscan" / LANGUAGE_FILES[language]).read_text()
    defaults = {"ARRAY_DEPTH": 8, "BATCH_DEPTH": 6,
                "NORMALIZE_ROUNDS": 32, "REPEATS": 1}
    if language == "c":
        for name, default in defaults.items():
            source = source.replace(f"#define {name} {default}",
                                   f"#define {name} {values[name]}")
    elif language == "typescript":
        for name, default in defaults.items():
            source = source.replace(f"const {name} = {default};",
                                   f"const {name} = {values[name]};")
    else:
        for name, default in defaults.items():
            source = source.replace(f"def {name} : Nat := {default}",
                                   f"def {name} : Nat := {values[name]}")
    path = out / f"direct.{language}"
    path.write_text(source)
    return path


def run_external(language: str, source: Path, out: Path,
                 expected_value: int, samples: int) -> dict[str, object]:
    if language == "c":
        binary = out / "direct-c"
        build = subprocess.run(["clang", "-std=c11", "-O3", str(source),
                                "-o", str(binary)], capture_output=True,
                               text=True, timeout=120)
        if build.returncode != 0:
            return {"status": "unavailable",
                    "reason": (build.stdout + build.stderr)[-300:]}
        command = [str(binary)]
    elif language == "typescript":
        if shutil.which("bun") is None:
            return {"status": "unavailable", "reason": "bun not found"}
        command = ["bun", str(source)]
    else:
        lean = shutil.which("lean")
        if lean is None:
            return {"status": "unavailable", "reason": "lean not found"}
        command = [lean, "--run", str(source)]

    times = []
    for _ in range(samples + 1):
        started = time.perf_counter()
        run = subprocess.run(command, capture_output=True, text=True,
                             timeout=240)
        elapsed = (time.perf_counter() - started) * 1000
        if run.returncode != 0:
            return {"status": "unavailable",
                    "reason": (run.stdout + run.stderr)[-300:]}
        values = [int(line) for line in run.stdout.splitlines() if line]
        if values != [expected_value]:
            raise AssertionError((language, expected_value, run.stdout,
                                  run.stderr))
        times.append(elapsed)
    return {"status": "ok", "samples_ms": times[1:],
            "median_ms": statistics.median(times[1:]),
            "checksum": expected_value,
            "timing_note": "process wall time, including startup"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bend-main", type=Path, default=DEFAULT_COMPILER)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/wordscan/results.json")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--array-depth", type=int, default=8)
    parser.add_argument("--batch-depth", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--normalize-rounds", type=int, default=32)
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--no-gpu", action="store_true")
    args = parser.parse_args()
    if args.samples < 1 or args.repeats < 1 or args.threads < 1:
        parser.error("samples, repeats, and threads must be positive")
    if not 0 <= args.array_depth < 31 or not 0 <= args.batch_depth < 31:
        parser.error("depths must be in [0, 30]")
    if args.array_depth + args.batch_depth >= 31:
        parser.error("array-depth + batch-depth must be below 31")
    if args.normalize_rounds < 0:
        parser.error("normalize-rounds must be non-negative")

    compiler = args.bend_main.resolve()
    values = {"ARRAY_DEPTH": args.array_depth,
              "BATCH_DEPTH": args.batch_depth,
              "REPEATS": args.repeats,
              # SAMPLES is replaced by samples + 1 so the first timed sample
              # is a warm-up and is discarded by parse_bend_output.
              "SAMPLES": args.samples + 1,
              "NORMALIZE_ROUNDS": args.normalize_rounds}
    expected_value = expected(args.array_depth, args.batch_depth,
                              args.repeats, args.normalize_rounds)
    report: dict[str, object] = {
        "benchmark": "wordscan",
        "scope": "Array<Quad> mapcat/filter/map/reduce; balanced independent batches",
        "timing": "Bend IO.now milliseconds exclude process/compiler startup; external wall times include startup",
        "semantics": "Each Quad expands to four lanes; normalize with wrapping U32 work; retain normalized lanes with x&3 != 0; sum",
        "baseline_terminology": {
            "transduced": "Public over_array + mapcat + filter + map + sum",
            "staged": "Core Bend Array.to_list plus list flatten/Base.List.map/filter/fold",
            "direct": "User-authored fused Bend traversal",
            "c": "Handwritten C fused loop",
            "typescript": "Handwritten TypeScript fused loop",
            "lean": "Handwritten Lean fused loop",
        },
        "parameters": {**values, "samples": args.samples,
                       "threads": args.threads, "expected_checksum": expected_value},
        "platform": platform.platform(),
        "compiler": str(compiler),
        "compiler_sha256": hashlib.sha256((compiler.parent / "comp.ts").read_bytes()).hexdigest(),
        "library_sha256": hashlib.sha256((ROOT / "transduce.bend").read_bytes()).hexdigest(),
        "results": [],
    }

    out = Path(tempfile.mkdtemp(prefix="transduce-wordscan-")).resolve()
    report["artifacts"] = str(out)
    for variant in VARIANTS:
        binary, build_info = build_bend(ROOT, compiler, out, variant, values)
        row: dict[str, object] = {"variant": variant, "build": build_info,
                                  "modes": {}}
        row["modes"]["cpu_1"] = run_bend(
            binary, ["--threads", "1", "--gpu", "off"],
            expected_value, args.samples)
        row["modes"]["cpu_16"] = run_bend(
            binary, ["--threads", str(args.threads), "--gpu", "off"],
            expected_value, args.samples)
        if args.no_gpu:
            row["modes"]["gpu"] = {"status": "skipped",
                                     "reason": "--no-gpu"}
        else:
            row["modes"]["gpu"] = run_bend(
                binary, ["--threads", "1", "--gpu", "1GB"],
                expected_value, args.samples)
        report["results"].append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")

    external: dict[str, object] = {}
    for language in LANGUAGE_FILES:
        source = external_source(ROOT, language, values, out)
        external[language] = run_external(language, source, out,
                                           expected_value, args.samples)
    report["external"] = external
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
