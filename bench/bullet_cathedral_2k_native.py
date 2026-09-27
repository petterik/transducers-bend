#!/usr/bin/env python3
"""Compile and launch the native 2K Bullet Cathedral window (macOS)."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_cathedral_2k_native.bend"
FRAMES = ROOT / "bench/bullet_cathedral_2k_frames.bend"


def flattened_source():
    """Keep the native entry and frame code in one Bend module for checking."""
    frames = FRAMES.read_text()
    native = SOURCE.read_text()
    header = ("import Base\n"
              "import ./bullet_cathedral_2k_frames.bend as B\n"
              "import ./bullet_cathedral_present.bend as P\n")
    if not native.startswith(header):
        raise ValueError("native Bend imports changed; update the flat build")
    if frames.count("\ndef dump(") != 1 or frames.count("\ndef parsed_u32(") != 1 \
            or frames.count("\ndef dispatch(") != 1:
        raise ValueError("frame CLI boundary changed; update the flat build")
    body, rest = frames.split("\ndef dump(", 1)
    parsers = "\ndef parsed_u32(" + rest.split("\ndef parsed_u32(", 1)[1]
    parsers = parsers.split("\ndef dispatch(", 1)[0]
    body = body.replace("import Base\n",
                        "import Base\nimport ./bullet_cathedral_present.bend as P\n",
                        1)
    return body + parsers + "\n" + native[len(header):].replace("B.", "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=30,
                        help="wall-clock run duration (default: 30)")
    parser.add_argument("--window-width", type=int, default=1280,
                        help="window width in points (default: 1280)")
    parser.add_argument("--compile-only", action="store_true",
                        help="check and build the player without opening a window")
    args = parser.parse_args()
    duration_ms = round(args.minutes * 60_000)
    if not 1 <= duration_ms <= 0xFFFFFFFF:
        parser.error("duration must be between 1 ms and 4,294,967,295 ms")
    if not 320 <= args.window_width <= 3840:
        parser.error("window width must be between 320 and 3840")
    if sys.platform != "darwin":
        parser.error("the native presenter currently requires macOS")

    with tempfile.TemporaryDirectory(prefix="bullet-cathedral-native-") as tmp:
        binary = Path(tmp) / "bullet_cathedral"
        module_cache = Path(tmp) / "clang-modules"
        module_cache.mkdir()
        with tempfile.NamedTemporaryFile(mode="w", dir=ROOT / "bench",
                                         prefix="bullet_cathedral_flat_",
                                         suffix=".bend", delete=False) as file:
            file.write(flattened_source())
            flattened = Path(file.name)
        environment = os.environ.copy()
        environment["CLANG_MODULE_CACHE_PATH"] = str(module_cache)
        try:
            subprocess.run(
                ["bun", str(ROOT.parent / "bend/bend2/main.ts"),
                 str(flattened), "-o", str(binary)], cwd=ROOT,
                env=environment, check=True)
        finally:
            flattened.unlink(missing_ok=True)
        if args.compile_only:
            return 0
        return subprocess.call(
            [str(binary), "--threads", "1", "--gpu", "off", "--",
             str(duration_ms), str(args.window_width)], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
