#!/usr/bin/env python3
"""Measure small-list crossovers for stateful transducer pipelines."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPILER = ROOT.parent / "bend/bend2/main.ts"
CASES = ("filter", "take", "filter_take")
VARIANTS = ("transducer", "direct_bend", "base_list")


def parse_sizes(value: str):
    sizes = []
    for part in value.split(","):
        if "-" in part:
            begin, end = map(int, part.split("-", 1))
            sizes.extend(range(begin, end + 1))
        else:
            sizes.append(int(part))
    if not sizes or any(n < 0 for n in sizes):
        raise argparse.ArgumentTypeError("sizes must be non-negative")
    return list(dict.fromkeys(sizes))


def expected(size: int, repeats: int, case: str, threshold: int, take: int,
             work_rounds: int) -> int:
    total = 0
    for seed in range(repeats):
        accepted = 0
        one = 0
        for offset in range(size):
            value = (seed + offset + 1) & 0xFFFFFFFF
            key = value
            for _ in range(work_rounds):
                key = ((((key * 1664525) & 0xFFFFFFFF) ^ (key >> 13)) + 1013904223) & 0xFFFFFFFF
            keep = case == "take" or key > threshold
            if keep:
                one = (one + value) & 0xFFFFFFFF
                accepted += 1
                if case != "filter" and accepted == take:
                    break
        total = (total + one) & 0xFFFFFFFF
    return total


def source_for(out: Path, variant: str, case: str, sample_count: int,
               threshold: int, take: int, work_rounds: int) -> str:
    library = os.path.relpath(ROOT / "transduce.bend", out)
    common = f"""import Base
import ./{library} as T

def inc(x: U32) -> U32:
  (x + 1 : U32)

def work(n: Nat, +x: U32) -> U32:
  match n:
    case 0n:
      x
    case 1n+p:
      work(p, (U32.xor(U32.mul(x, 1664525), U32.shrn(x, 13n)) + 1013904223 : U32))

def above(threshold: U32, x: U32) -> Bool:
  U32.is_gt(work({work_rounds}n, x), threshold)

def build(n: Nat, +start: U32) -> List<U32>:
  match n:
    case 0n:
      []
    case 1n+p:
      start <> build(p, (start + 1 : U32))

def mapped_data(xs: List<U32>) -> List<&2, U32>:
  match xs:
    case Nil{{}}:
      Nil{{}}
    case h <> t:
      inc(h) <> mapped_data(t)

type Running is Type:
  Running{{left: Nat, acc: U32}}

type FilterState is Type:
  FilterState{{acc: U32}}

def filter_choose(keep: Bool, +acc: U32, +x: U32) -> U32:
  match keep:
    case False{{}}:
      acc
    case True{{}}:
      (acc + x : U32)

def filter_feed(+threshold: U32, state: FilterState, +x: U32) -> FilterState:
  match state:
    case FilterState{{acc}}:
      FilterState{{filter_choose(above(threshold, x), acc, x)}}

def direct_filter(xs: List<U32>, +threshold: U32, state: FilterState) -> U32:
  match xs state:
    case Nil{{}} FilterState{{acc}}:
      acc
    case h <> t FilterState{{acc}}:
      direct_filter(t, threshold, filter_feed(threshold, state, inc(h)))

def direct_take(xs: List<U32>, state: Running) -> U32:
  match xs state:
    case xs Running{{0n, acc}}:
      acc
    case Nil{{}} Running{{left, acc}}:
      acc
    case h <> t Running{{1n+p, acc}}:
      direct_take(t, Running{{p, (acc + inc(h) : U32)}})

def filter_take_next(keep: Bool, n: Nat, acc: U32, +x: U32) -> Running:
  match keep n:
    case False{{}} n:
      Running{{n, acc}}
    case True{{}} 0n:
      Running{{0n, acc}}
    case True{{}} 1n+p:
      Running{{p, (acc + x : U32)}}

def filter_take_feed(+threshold: U32, n: Nat, acc: U32, +x: U32) -> Running:
  filter_take_next(above(threshold, x), n, acc, x)

def direct_filter_take(xs: List<U32>, state: Running, +threshold: U32) -> U32:
  match xs state:
    case xs Running{{0n, acc}}:
      acc
    case Nil{{}} Running{{left, acc}}:
      acc
    case h <> t Running{{1n+p, acc}}:
      direct_filter_take(t, filter_take_feed(threshold, 1n+p, acc, inc(h)), threshold)

def run(xs: List<U32>) -> U32:
"""
    if case == "filter":
        config = f"({threshold}, 0)"
        if variant == "transducer":
            common += f"""  T.transduce(~T.over_list(~U32, ~U32,
    ~T.map(~U32, ~U32, ~U32, ~inc,
      ~T.filter(~U32, ~U32, ~U32, ~above, ~T.sum()))), {config}, xs)
"""
        elif variant == "direct_bend":
            common += f"""  direct_filter(xs, {threshold}, FilterState{{0}})
"""
        elif variant == "base_list":
            common += f"""  List.foldl(~&2, ~U32, ~U32, ~U32.add,
    List.filter(~U32, ~(x => U32.is_gt(work({work_rounds}n, x), {threshold})), mapped_data(xs)), 0)
"""
    elif case == "take":
        config = f"({take}n, 0)"
        if variant == "transducer":
            common += f"""  T.transduce(~T.over_list(~U32, ~U32,
    ~T.map(~U32, ~U32, ~U32, ~inc, ~T.take(~U32, ~U32, ~T.sum()))), {config}, xs)
"""
        elif variant == "direct_bend":
            common += f"""  direct_take(xs, Running{{{take}n, 0}})
"""
        elif variant == "base_list":
            common += f"""  List.foldl(~&1, ~U32, ~U32, ~U32.add,
    List.take(&1, U32, List.map(~U32, ~U32, ~inc, xs), {take}n), 0)
"""
    elif case == "filter_take":
        config = f"({threshold}, ({take}n, 0))"
        if variant == "transducer":
            common += f"""  T.transduce(~T.over_list(~U32, ~U32,
    ~T.map(~U32, ~U32, ~U32, ~inc,
      ~T.filter(~U32, ~U32, ~U32, ~above,
        ~T.take(~U32, ~U32, ~T.sum())))), {config}, xs)
"""
        elif variant == "direct_bend":
            common += f"""  direct_filter_take(xs, Running{{{take}n, 0}}, {threshold})
"""
        elif variant == "base_list":
            common += f"""  List.foldl(~&2, ~U32, ~U32, ~U32.add,
    List.take(&2, U32,
      List.filter(~U32, ~(x => U32.is_gt(work({work_rounds}n, x), {threshold})), mapped_data(xs)),
      {take}n), 0)
"""
    else:
        raise ValueError(case)
    common += """
def parsed(value: Maybe<&2, Nat>) -> Nat:
  match value:
    case None{}:
      0n
    case Some{n}:
      n

def repeat(n: Nat, +size: Nat, +seed: U32, +acc: U32) -> U32:
  match n:
    case 0n:
      acc
    case 1n+p:
      answer = run(build(size, seed))
      repeat(p, size, (seed + 1 : U32), (acc + answer : U32))

def measure(n: Nat, +size: Nat, +repeats: Nat) -> IO(Unit):
  match n:
    case 0n:
      IO.pure(Unit, Unit{})
    case 1n+p:
      do IO<Unit>:
        before : Nat <- IO.now()
        answer : U32 = repeat!(repeats, size, 0, 0)
        after : Nat <- IO.now()
        IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
        measure(p, size, repeats)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case a <> b <> t:
      measure(SAMPLE_COUNTn, parsed(Nat.read(a)), parsed(Nat.read(b)))
    case a <> t:
      measure(SAMPLE_COUNTn, parsed(Nat.read(a)), 1n)
    case Nil{}:
      measure(SAMPLE_COUNTn, 0n, 1n)

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
"""
    return common.replace("SAMPLE_COUNT", str(sample_count))


def run_binary(binary: Path, size: int, repeats: int, samples: int):
    output = subprocess.check_output([str(binary), str(size), str(repeats)],
                                     text=True, timeout=120)
    pairs = [tuple(map(int, line.split(":"))) for line in output.splitlines()]
    if len(pairs) != samples + 1:
        raise AssertionError((binary, output))
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bend-main", type=Path, default=DEFAULT_COMPILER)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--threshold", type=int, default=1)
    parser.add_argument("--take", type=int, default=32)
    parser.add_argument("--work-rounds", type=int, default=0,
                        help="U32 mixing rounds used by the filter predicate")
    parser.add_argument("--target-calls", type=int, default=1 << 20,
                        help="Approximate input elements per timed sample")
    parser.add_argument("--sizes", type=parse_sizes,
                        default=parse_sizes("0-32,48,64,96,128,192,256,512,1024"))
    args = parser.parse_args()
    if args.samples < 1 or args.target_calls < 1:
        parser.error("samples and target-calls must be positive")
    if not 0 <= args.threshold <= 0xFFFFFFFF:
        parser.error("threshold must fit U32")
    if args.take < 1:
        parser.error("take must be positive")
    if args.work_rounds < 0:
        parser.error("work-rounds must be non-negative")

    compiler = args.bend_main.resolve()
    env = {**os.environ, "BEND_NO_TELEMETRY": "1",
           "CLANG_MODULE_CACHE_PATH": "/tmp/bend-clang-modules"}
    report = {
        "scope": "Sequential dynamic U32 lists; map inc plus stateful reduction; construction and checksum included",
        "timing": "IO.now milliseconds inside persistent native process; one warmup; alternating variant order",
        "variants": list(VARIANTS),
        "variant_descriptions": {
            "transducer": "Public transducer composition in transduce.bend",
            "direct_bend": "User-authored fused Bend traversal compiled to native C",
            "base_list": "Core Base.List map/filter/take/foldl pipeline where the prelude type kinds permit it",
        },
        "manual_c_baseline": False,
        "threshold": args.threshold,
        "take": args.take,
        "work_rounds": args.work_rounds,
        "platform": platform.platform(),
        "compiler": str(compiler),
        "compiler_sha256": hashlib.sha256((compiler.parent / "comp.ts").read_bytes()).hexdigest(),
        "library_sha256": hashlib.sha256((ROOT / "transduce.bend").read_bytes()).hexdigest(),
        "samples": args.samples,
        "target_calls": args.target_calls,
        "cases": args.cases,
        "results": [],
    }

    out = Path(tempfile.mkdtemp(prefix="transduce-stateful-")).resolve()
    report["artifacts"] = str(out)
    for case in args.cases:
        binaries = {}
        for variant in VARIANTS:
            stem = out / f"{case}-{variant}"
            bend = stem.with_suffix(".bend")
            bend.write_text(source_for(out, variant, case, args.samples + 1,
                                       args.threshold, args.take, args.work_rounds))
            build = subprocess.run(
                ["bun", str(compiler), str(bend), "-o", str(stem),
                 "-o", str(stem.with_suffix(".js")),
                 "-o", str(stem.with_suffix(".c"))],
                env=env, capture_output=True, text=True, timeout=120,
            )
            if build.returncode:
                raise RuntimeError(build.stdout + build.stderr)
            binaries[variant] = stem
            report.setdefault("program_sha256", {})[f"{case}:{variant}"] = hashlib.sha256(bend.read_bytes()).hexdigest()

        for size in args.sizes:
            repeats = max(1, args.target_calls // max(1, size))
            row = {
                "case": case,
                "size": size,
                "repeats": repeats,
                "expected": expected(size, repeats, case, args.threshold, args.take,
                                      args.work_rounds),
                "samples_ms": {variant: [] for variant in VARIANTS},
            }
            for order in (list(VARIANTS), list(reversed(VARIANTS))):
                for variant in order:
                    pairs = run_binary(binaries[variant], size, repeats, args.samples)
                    if any(value != row["expected"] for value, _ in pairs):
                        raise AssertionError((case, size, variant, row["expected"], pairs))
                    row["samples_ms"][variant].extend(ms for _, ms in pairs[1:])
            row["median_ms"] = {
                variant: statistics.median(values)
                for variant, values in row["samples_ms"].items()
            }
            row["ratio_to_direct_bend"] = {
                variant: row["median_ms"][variant] / row["median_ms"]["direct_bend"]
                if row["median_ms"]["direct_bend"] else None
                for variant in VARIANTS
            }
            row["ratio_to_base_list"] = {
                variant: row["median_ms"][variant] / row["median_ms"]["base_list"]
                if row["median_ms"]["base_list"] else None
                for variant in VARIANTS
            }
            report["results"].append(row)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(case, size, row["median_ms"], flush=True)


if __name__ == "__main__":
    main()
