#!/usr/bin/env python3
"""Count showcase source lines, lexical tokens, and raw o200k BPE tokens.

Install tiktoken 0.14.0 to reproduce the BPE counts. This tokenizer is a
named proxy for prompt size, not an assertion about any specific model.
"""
import json
from pathlib import Path

from bullet_cathedral_cross_language import BEND, C, ROOT, RUST, sha, source_size


def main():
    import tiktoken

    encoder = tiktoken.get_encoding("o200k_base")
    paths = (BEND, ROOT / "bench/bullet_cathedral_direct.bend", C, RUST,
             ROOT / "bench/bullet_cathedral_loops.rs",
             ROOT / "xf.bend", ROOT / "transduce_core.bend",
             ROOT / "proofs/list_map_fold_law.bend",
             ROOT / "proofs/no_stop_control_law.bend",
             ROOT / "proofs/api_stage_laws.bend")
    files = {}
    for path in paths:
        contents = path.read_text()
        files[path.relative_to(ROOT).as_posix()] = {
            "sha256": sha(path),
            "bytes": len(contents.encode("utf-8")),
            **source_size(path),
            "raw_o200k_base_tokens": len(encoder.encode(contents)),
        }
    report = {
        "scope": "Five complete handwritten scene files: Bend transducers, Bend direct loops, C direct loops, Rust iterators, and Rust direct loops. Raw BPE counts include comments, whitespace and each scene's own CLI harness; code-line and lexical-token counts omit blank lines and comments according to bullet_cathedral_cross_language.py. Shared Bend libraries and proof artifacts are reported separately. Neither token measure is a measured GPT-6 prompt bill.",
        "tiktoken_version": tiktoken.__version__,
        "encoding": encoder.name,
        "files": files,
    }
    output = ROOT / "bench/bullet-source-metrics-20260927.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({name: value["raw_o200k_base_tokens"]
                      for name, value in files.items()}))


if __name__ == "__main__":
    main()
