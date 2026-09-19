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
import re
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


def require_success(run: subprocess.CompletedProcess[str], context: str) -> None:
    if run.returncode != 0:
        message = (run.stdout + run.stderr).strip()
        raise RuntimeError(f"{context}: {message[-1000:]}")


def run_bend(binary: Path, flags: list[str], expected_value: int,
             samples: int) -> dict[str, object]:
    run = subprocess.run([str(binary), *flags], capture_output=True,
                         text=True, timeout=240)
    if run.returncode != 0:
        message = (run.stdout + run.stderr).strip()
        gpu_requested = "--gpu" in flags and flags[flags.index("--gpu") + 1] != "off"
        if gpu_requested and "no gpu device" in message.lower():
            return {"status": "unavailable", "reason": message[-300:]}
        require_success(run, f"Bend benchmark failed ({binary.name} {' '.join(flags)})")
    times = parse_bend_output(run.stdout, expected_value, samples)
    return {"status": "ok", "samples_ms": times,
            "median_ms": statistics.median(times), "checksum": expected_value}


def external_source(root: Path, language: str, values: dict[str, int],
                    out: Path) -> Path:
    source = (root / "bench/wordscan" / LANGUAGE_FILES[language]).read_text()
    parameter_names = ("ARRAY_DEPTH", "BATCH_DEPTH", "NORMALIZE_ROUNDS", "REPEATS")
    patterns = {
        "c": {name: rf"(#define {name} )\d+"
              for name in parameter_names},
        "typescript": {name: rf"(const {name} = )\d+;"
                       for name in parameter_names},
        "lean": {name: rf"(def {name} : Nat := )\d+"
                 for name in parameter_names},
    }[language]

    for name, pattern in patterns.items():
        source, count = re.subn(pattern, rf"\g<1>{values[name]}", source)
        if count != 1:
            raise AssertionError(
                f"{language} benchmark parameter {name} matched {count} declarations"
            )
    path = out / f"direct.{language}"
    path.write_text(source)
    return path


def run_external(language: str, source: Path, out: Path,
                 expected_value: int, samples: int) -> dict[str, object]:
    if language == "c":
        if shutil.which("clang") is None:
            return {"status": "unavailable", "reason": "clang not found"}
        binary = out / "direct-c"
        build = subprocess.run(["clang", "-std=c11", "-O3", str(source),
                                "-o", str(binary)], capture_output=True,
                               text=True, timeout=120)
        require_success(build, "C benchmark compilation failed")
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
        require_success(run, f"{language} benchmark failed")
        values = [int(line) for line in run.stdout.splitlines() if line]
        if values != [expected_value]:
            raise AssertionError((language, expected_value, run.stdout,
                                  run.stderr))
        times.append(elapsed)
    return {"status": "ok", "samples_ms": times[1:],
            "median_ms": statistics.median(times[1:]),
            "checksum": expected_value,
            "timing_note": "process wall time, including startup"}


def result_text(result: dict[str, object]) -> str:
    status = result["status"]
    if status == "ok":
        return f"{result['median_ms']:.2f} ms"
    reason = str(result.get("reason", ""))
    return f"{status}: {reason.replace(chr(10), ' ')}"


def render_report(report: dict[str, object], output_name: str,
                  output_command: str) -> str:
    parameters = report["parameters"]
    results = {row["variant"]: row for row in report["results"]}
    threaded_label = f"cpu_{parameters['threads']}"
    threaded_title = f"Bend CPU {parameters['threads']}"
    transduced = results["transduced"]
    staged = results["staged"]
    direct = results["direct"]
    trans_cpu1 = transduced["modes"]["cpu_1"]
    staged_cpu1 = staged["modes"]["cpu_1"]
    direct_cpu1 = direct["modes"]["cpu_1"]
    trans_median = trans_cpu1.get("median_ms")
    staged_median = staged_cpu1.get("median_ms")
    direct_median = direct_cpu1.get("median_ms")
    numeric_medians = all(isinstance(x, (int, float)) for x in
                          (trans_median, staged_median, direct_median))
    if numeric_medians and staged_median != 0 and direct_median != 0:
        staged_delta = (1 - trans_median / staged_median) * 100
        direct_gap = (trans_median / direct_median - 1) * 100
        comparison = (
            f"The public transduced path is {staged_delta:.0f}% faster than the "
            f"materialized Core Bend list path at one thread in this run. "
            f"It is {direct_gap:.0f}% above the direct fused Bend loop at one "
            "thread."
        )
    elif numeric_medians:
        comparison = "The timer resolution was too coarse for a meaningful CPU ratio on this small workload."
    else:
        comparison = "The CPU comparison is incomplete because one or more modes failed."
    trans_records = transduced["build"]["js_records"]
    gpu_result = transduced["modes"].get("gpu", {})
    lean_result = report["external"]["lean"]
    gpu_note = result_text(gpu_result)
    lean_note = result_text(lean_result)
    reproduce_command = (
        "python3 bench/wordscan/run.py "
        f"--array-depth {parameters['ARRAY_DEPTH']} "
        f"--batch-depth {parameters['BATCH_DEPTH']} "
        f"--repeats {parameters['REPEATS']} "
        f"--normalize-rounds {parameters['NORMALIZE_ROUNDS']} "
        f"--samples {parameters['samples']} "
        f"--threads {parameters['threads']} "
        f"--gpu-memory {parameters['gpu_memory']} "
        f"--output {output_command}"
    )
    if gpu_result.get("status") == "skipped":
        reproduce_command += " --no-gpu"
    if gpu_result.get("status") == "ok":
        gpu_summary = (
            f"The host exposed Metal and the transduced GPU median was {gpu_note}."
        )
    else:
        gpu_summary = (
            f"The host's GPU result was `{gpu_note}`. Re-run the benchmark on a "
            "host with Metal access to populate that mode."
        )
    if lean_result.get("status") == "ok":
        lean_summary = f"Lean was measured at {lean_note}."
    else:
        lean_summary = f"Lean was `{lean_note}`."
    return f"""# Array mapcat benchmark report

This run used `ARRAY_DEPTH={parameters['ARRAY_DEPTH']}`,
`BATCH_DEPTH={parameters['BATCH_DEPTH']}`, `REPEATS={parameters['REPEATS']}`,
and `NORMALIZE_ROUNDS={parameters['NORMALIZE_ROUNDS']}`. Every successful
variant returned checksum `{parameters['expected_checksum']}`. Bend timings are
persistent-process `IO.now` medians after one discarded warm-up; the C and
TypeScript figures include process startup and are therefore a separate
reference.

| Variant | Bend CPU 1 | {threaded_title} | Bend GPU | External CPU 1 |
| --- | ---: | ---: | --- | ---: |
| Transduced (`over_array` + `mapcat`) | {result_text(trans_cpu1)} | {result_text(transduced['modes'][threaded_label])} | {gpu_note} | — |
| Core Bend materialized list | {result_text(staged_cpu1)} | {result_text(staged['modes'][threaded_label])} | {result_text(staged['modes'].get('gpu', {}))} | — |
| Direct fused Bend | {result_text(direct_cpu1)} | {result_text(direct['modes'][threaded_label])} | {result_text(direct['modes'].get('gpu', {}))} | — |
| Handwritten C | — | — | — | {result_text(report['external']['c'])} |
| Handwritten TypeScript | — | — | — | {result_text(report['external']['typescript'])} |
| Handwritten Lean | — | — | — | {lean_note} |

{comparison} The direct Bend and C loops are lower-level reference points;
this benchmark does not claim that the public transducer API beats handwritten
C. The emitted transduced JavaScript contains {trans_records} static reducer/source
records; that is a compiler/code-shape observation, not a correctness failure.

The benchmark checksum validates lane membership, wrapping arithmetic, and
batch partitioning. It is a sum, so it cannot by itself prove traversal order;
the ordered `over_array` conformance test covers that separately.

{gpu_summary} {lean_summary} Raw
samples, compiler/library hashes, checksums, and the artifact directory are in
[{output_name}]({output_name}).

Reproduce with:

```sh
{reproduce_command}
```
"""


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
    parser.add_argument("--gpu-memory", default="1GB",
                        help="Metal/CUDA memory span passed to --gpu")
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
    if re.fullmatch(r"[1-9][0-9]*(?:MB|GB)", args.gpu_memory) is None:
        parser.error("gpu-memory must be a positive size such as 512MB or 2GB")

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
                       "threads": args.threads, "gpu_memory": args.gpu_memory,
                       "expected_checksum": expected_value},
        "platform": platform.platform(),
        "compiler": str(compiler),
        "compiler_sha256": hashlib.sha256((compiler.parent / "comp.ts").read_bytes()).hexdigest(),
        "library_sha256": hashlib.sha256((ROOT / "transduce.bend").read_bytes()).hexdigest(),
        "results": [],
    }

    out = Path(tempfile.mkdtemp(prefix="transduce-wordscan-")).resolve()
    report["artifacts"] = str(out)
    cpu_modes = [("cpu_1", ["--threads", "1", "--gpu", "off"])]
    threaded_label = f"cpu_{args.threads}"
    if threaded_label != "cpu_1":
        cpu_modes.append((threaded_label,
                          ["--threads", str(args.threads), "--gpu", "off"]))
    for variant in VARIANTS:
        binary, build_info = build_bend(ROOT, compiler, out, variant, values)
        row: dict[str, object] = {"variant": variant, "build": build_info,
                                  "modes": {}}
        for label, flags in cpu_modes:
            row["modes"][label] = run_bend(
                binary, flags, expected_value, args.samples)
        if args.no_gpu:
            row["modes"]["gpu"] = {"status": "skipped",
                                     "reason": "--no-gpu"}
        else:
            row["modes"]["gpu"] = run_bend(
                binary, ["--threads", "1", "--gpu", args.gpu_memory],
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
    args.output.with_name("REPORT.md").write_text(
        render_report(report, args.output.name, str(args.output))
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
