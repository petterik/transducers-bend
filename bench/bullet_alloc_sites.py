#!/usr/bin/env python3
"""Attribute timed Bend heap allocations to generated-C call sites."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from public_array_map_filter_sum import instrument_allocations

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_cathedral.bend"


def command(*args):
    return subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True,
                          capture_output=True, text=True)


def instrument_sites(source):
    source = instrument_allocations(source)
    labels = []
    call = re.compile(r"\bheap_alloc\(e,")
    def replace(match):
        before = source[:match.start()]
        line = before.count("\n") + 1
        signature = re.findall(r"^(?:INLINE|OUTLINE|DEV|static)[^\n]*\) \{",
                               before, re.MULTILINE)
        context = before.splitlines()[-1].strip()
        labels.append({"site": len(labels), "generated_c_line": line,
                       "enclosing_function": signature[-1] if signature else None,
                       "statement": context + "heap_alloc(e,"
                           + source[match.end():].splitlines()[0]})
        return f"profile_alloc({len(labels) - 1}, e,"
    source = call.sub(replace, source)
    wrapper = (f"static u64 site_counts[{len(labels)}];\n"
               "INLINE Loc profile_alloc(u32 site, Env e, Cls cls) {\n"
               "  if (timing) site_counts[site]++;\n"
               "  return heap_alloc(e, cls);\n"
               "}\n")
    marker = "INLINE void heap_free(Env e, Cls cls, Loc loc) {"
    assert source.count(marker) == 1
    source = source.replace(marker, wrapper + marker, 1)
    exit_marker = '  fprintf(stderr, "TIMED_ALLOC %llu %u\\n", '
    assert source.count(exit_marker) == 1
    report = (f"  for (u32 i = 0; i < {len(labels)}; i++)\n"
              "    if (site_counts[i]) fprintf(stderr, \"SITE %u %llu\\n\",\n"
              "      i, (unsigned long long)site_counts[i]);\n")
    source = source.replace(exit_marker, report + exit_marker, 1)
    return source, labels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--output", type=Path, default=ROOT /
                        "bench/bullet-alloc-sites-20260927.json")
    args = parser.parse_args()
    assert args.frames > 0
    with tempfile.TemporaryDirectory(prefix="bullet-alloc-sites-") as temp_name:
        temp = Path(temp_name)
        generated = temp / "original.c"
        instrumented = temp / "sites.c"
        binary = temp / "sites"
        command("bun", ROOT.parent / "bend/bend2/main.ts", SOURCE,
                "-o", generated)
        generated_sha256 = hashlib.sha256(generated.read_bytes()).hexdigest()
        code, labels = instrument_sites(generated.read_text())
        instrumented.write_text(code)
        command("clang", "-O3", instrumented, "-o", binary)
        result = command(binary, "--threads", 1, "--gpu", "off", "--",
                         args.frames, "bench", "x")
        elapsed, checksum = map(int, result.stdout.split())
        total = re.search(r"TIMED_ALLOC (\d+) (\d+)", result.stderr)
        assert total and int(total.group(2)) == 2
        counts = {int(site): int(count) for site, count in
                  re.findall(r"SITE (\d+) (\d+)", result.stderr)}
    for label in labels:
        label["timed_calls"] = counts.get(label["site"], 0)
    assert sum(counts.values()) == int(total.group(1)), (sum(counts.values()),
                                                          int(total.group(1)))
    report = {
        "scope": "Static generated-C heap_alloc call sites, instrumented in one native CPU run. Sites in shared runtime helpers aggregate all callers. Counts are not allocation bytes or time.",
        "frames": args.frames, "checksum": checksum,
        "instrumented_elapsed_us": elapsed,
        "timed_heap_allocations": int(total.group(1)),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "generated_c_sha256": generated_sha256,
        "sites": labels,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    for site in sorted(labels, key=lambda item: item["timed_calls"], reverse=True)[:20]:
        print(site["site"], site["timed_calls"], site["generated_c_line"],
              site["enclosing_function"])
    print("TOTAL", report["timed_heap_allocations"], "CHECKSUM", checksum)


if __name__ == "__main__":
    main()
