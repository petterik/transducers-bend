#!/usr/bin/env python3
"""Find the list-size crossover for transducer map(inc) versus Bend baselines."""
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


def source_for(out: Path, variant: str, sample_count: int, mode: str) -> str:
    library = os.path.relpath(ROOT / "transduce.bend", out)
    common = f"""import Base
import ./{library} as T

def inc(x: U32) -> U32:
  (x + 1 : U32)

def build(n: Nat, +start: U32) -> List<U32>:
  match n:
    case 0n:
      []
    case 1n+p:
      start <> build(p, (start + 1 : U32))

def run(xs: List<U32>) -> U32:
"""
    if mode == "list":
        common = common.replace("def run(xs: List<U32>) -> U32:\n", """def check_list(xs: List<U32>, +pos: U32, +acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case h <> t:
      check_list(t, (pos + 1 : U32), (acc + U32.mul(h, pos) : U32))

def check_data(xs: List<&2, U32>, +pos: U32, +acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case h <> t:
      check_data(t, (pos + 1 : U32), (acc + U32.mul(h, pos) : U32))

def direct_map(xs: List<U32>) -> List<U32>:
  match xs:
    case Nil{}:
      []
    case h <> t:
      inc(h) <> direct_map(t)

def direct_map_accum(xs: List<U32>, +acc: List<&2, U32>) -> List<&2, U32>:
  match xs:
    case Nil{}:
      List.reverse(&2, U32, acc)
    case h <> t:
      direct_map_accum(t, inc(h) <> acc)

def run(xs: List<U32>) -> U32:
""")
        if variant == "transducer":
            common += """  check_list(T.transduce(~T.over_list(~U32, ~List<U32>,
    ~T.map(~U32, ~U32, ~List<U32>, ~inc, ~T.into_list(~U32))), Unit{}, xs), 1, 0)
"""
        elif variant == "handwritten":
            common += """  check_list(direct_map(xs), 1, 0)
"""
        elif variant == "handwritten_accumulator":
            common += """  check_data(direct_map_accum(xs, []), 1, 0)
"""
        elif variant == "base_list":
            common += """  check_list(List.map(~U32, ~U32, ~inc, xs), 1, 0)
"""
        else:
            raise ValueError(variant)
    elif mode == "sum":
        common = common.replace("def run(xs: List<U32>) -> U32:\n", """def direct_sum(xs: List<U32>, +acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case h <> t:
      direct_sum(t, (acc + inc(h) : U32))

def run(xs: List<U32>) -> U32:
""")
        if variant == "transducer":
            common += """  T.transduce(~T.over_list(~U32, ~U32,
    ~T.map(~U32, ~U32, ~U32, ~inc, ~T.sum())), 0, xs)
"""
        elif variant == "handwritten":
            common += """  direct_sum(xs, 0)
"""
        elif variant == "base_list":
            common += """  List.foldl(~&1, ~U32, ~U32, ~U32.add,
    List.map(~U32, ~U32, ~inc, xs), 0)
"""
        else:
            raise ValueError(variant)
    else:
        raise ValueError(mode)
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


def expected(size: int, repeats: int, mode: str) -> int:
    # Each call maps [seed, seed + size) to [seed + 1, seed + size + 1].
    # The list mode weights positions so a reversed output cannot pass the
    # checksum while the sum mode retains the scalar reduction being measured.
    total = 0
    for seed in range(repeats):
        if mode == "sum":
            one = size * (seed + 1) + size * (size - 1) // 2
        else:
            one = sum((seed + j + 1) * (j + 1) for j in range(size))
        total = (total + one) & 0xFFFFFFFF
    return total


def run_binary(binary: Path, size: int, repeats: int, samples: int):
    output = subprocess.check_output(
        [str(binary), str(size), str(repeats)],
        text=True,
        timeout=120,
    )
    pairs = [tuple(map(int, line.split(":"))) for line in output.splitlines()]
    if len(pairs) != samples + 1:
        raise AssertionError((binary, output))
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bend-main", type=Path, default=DEFAULT_COMPILER)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--mode", choices=["list", "sum"], default="list",
                        help="Map to a list, or map then reduce to a scalar")
    parser.add_argument("--list-accumulator", action="store_true",
                        help="Include an accumulator-and-reverse direct Bend list map")
    parser.add_argument("--target-calls", type=int, default=1 << 20,
                        help="Approximate input elements per timed sample")
    parser.add_argument("--sizes", type=parse_sizes,
                        default=parse_sizes("0-32,48,64,96,128,192,256,512,1024"))
    args = parser.parse_args()
    if args.samples < 1 or args.target_calls < 1:
        parser.error("samples and target-calls must be positive")

    compiler = args.bend_main.resolve()
    env = {**os.environ, "BEND_NO_TELEMETRY": "1",
           "CLANG_MODULE_CACHE_PATH": "/tmp/bend-clang-modules"}
    report = {
        "scope": "Sequential dynamic U32 lists; map inc benchmark; input construction and checksum included",
        "mode": args.mode,
        "timing": "IO.now milliseconds inside persistent native process; one warmup; alternating variant order",
        "variant_language": "All variants are Bend source compiled to native C by the same sibling compiler",
        "manual_c_baseline": False,
        "ratio_to_handwritten_meaning": "Legacy field name; ratio to the direct Bend recursive comparator, not List.map or manual C",
        "variant_descriptions": {
            "transducer": "Public transducer composition in transduce.bend",
            "handwritten": "User-authored direct Bend recursive comparator (legacy report key)",
            "handwritten_accumulator": "User-authored direct Bend accumulator-and-reverse comparator (legacy report key)",
            "base_list": "Core Base.List.map/List.foldl comparator",
        },
        "platform": platform.platform(),
        "compiler": str(compiler),
        "compiler_sha256": hashlib.sha256((compiler.parent / "comp.ts").read_bytes()).hexdigest(),
        "library_sha256": hashlib.sha256((ROOT / "transduce.bend").read_bytes()).hexdigest(),
        "samples": args.samples,
        "target_calls": args.target_calls,
        "variants": (["transducer", "handwritten", "handwritten_accumulator", "base_list"]
                     if args.mode == "list" and args.list_accumulator
                     else ["transducer", "handwritten", "base_list"]),
        "results": [],
    }

    out = Path(tempfile.mkdtemp(prefix="transduce-map-inc-")).resolve()
    report["artifacts"] = str(out)
    binaries = {}
    for variant in report["variants"]:
        stem = out / variant
        bend = stem.with_suffix(".bend")
        bend.write_text(source_for(out, variant, args.samples + 1, args.mode))
        build = subprocess.run(
            ["bun", str(compiler), str(bend), "-o", str(stem),
             "-o", str(stem.with_suffix(".js")),
             "-o", str(stem.with_suffix(".c"))],
            env=env, capture_output=True, text=True, timeout=120,
        )
        if build.returncode:
            raise RuntimeError(build.stdout + build.stderr)
        binaries[variant] = stem
        report.setdefault("program_sha256", {})[variant] = hashlib.sha256(bend.read_bytes()).hexdigest()

    for size in args.sizes:
        repeats = max(1, args.target_calls // max(1, size))
        row = {"size": size, "repeats": repeats,
               "expected": expected(size, repeats, args.mode),
               "samples_ms": {variant: [] for variant in report["variants"]}}
        orders = [report["variants"], list(reversed(report["variants"]))]
        for order in orders:
            for variant in order:
                pairs = run_binary(binaries[variant], size, repeats, args.samples)
                if any(value != row["expected"] for value, _ in pairs):
                    raise AssertionError((size, variant, row["expected"], pairs))
                row["samples_ms"][variant].extend(ms for _, ms in pairs[1:])
        row["median_ms"] = {
            variant: statistics.median(values)
            for variant, values in row["samples_ms"].items()
        }
        row["ratio_to_handwritten"] = {
            variant: row["median_ms"][variant] / row["median_ms"]["handwritten"]
            if row["median_ms"]["handwritten"] else None
            for variant in report["variants"]
        }
        report["results"].append(row)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(size, row["median_ms"], flush=True)


if __name__ == "__main__":
    main()
