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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=30,
                        help="wall-clock run duration (default: 30)")
    parser.add_argument("--window-width", type=int, default=1280,
                        help="window width in points (default: 1280)")
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
        environment = os.environ.copy()
        environment["CLANG_MODULE_CACHE_PATH"] = str(module_cache)
        subprocess.run(
            ["bun", str(ROOT.parent / "bend/bend2/main.ts"), str(SOURCE),
             "-o", str(binary)], cwd=ROOT, env=environment, check=True)
        return subprocess.call(
            [str(binary), "--threads", "1", "--gpu", "off", "--",
             str(duration_ms), str(args.window_width)], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
