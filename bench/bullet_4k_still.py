#!/usr/bin/env python3
"""Export one 3840x2160 Bullet Cathedral frame computed by Bend."""
import argparse
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_cathedral_4k_frames.bend"
WIDTH, HEIGHT = 3840, 2160
VISIBLE = WIDTH * HEIGHT
CAPACITY = 1 << 23


def run(*args):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True).stdout


def chunk(kind, payload):
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def write_png(path, rgb):
    rows = bytearray()
    stride = WIDTH * 3
    for y in range(HEIGHT):
        rows.append(0)
        rows.extend(rgb[y * stride:(y + 1) * stride])
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b""))


def decode(raw):
    rgb = bytearray(VISIBLE * 3)
    checksum = 0
    count = 0
    for match in re.finditer(rb"\d+", raw):
        color = int(match.group())
        if count < VISIBLE:
            assert 0 <= color <= 0xFFFFFF
            at = count * 3
            rgb[at] = (color >> 16) & 255
            rgb[at + 1] = (color >> 8) & 255
            rgb[at + 2] = color & 255
            checksum = (checksum + color) & 0xFFFFFFFF
        else:
            assert color == 0
        count += 1
    assert count == CAPACITY, count
    return rgb, checksum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame", type=int, default=96)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    assert 0 <= args.frame < 120
    with tempfile.TemporaryDirectory(prefix="bullet-4k-still-") as tmp:
        generated = Path(tmp) / "frame.c"
        binary = Path(tmp) / "frame"
        run("bun", ROOT.parent / "bend/bend2/main.ts", SOURCE,
            "-o", generated)
        run("clang", "-O3", generated, "-o", binary)
        raw = run(binary, "--threads", 1, "--gpu", "off", "--",
                  args.frame, 0)
        rgb, checksum = decode(raw)
        measured = run(binary, "--threads", 1, "--gpu", "off", "--",
                       args.frame).split()
        assert int(measured[1]) == checksum
    output = args.output or ROOT / f"bench/bullet-cathedral-4k-frame-{args.frame:03}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    write_png(output, rgb)
    print(f"{output} {WIDTH}x{HEIGHT} checksum={checksum}")


if __name__ == "__main__":
    main()
