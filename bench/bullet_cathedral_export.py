#!/usr/bin/env python3
"""Build and export deterministic Bullet Cathedral frames computed in Bend."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import struct
import subprocess
import tempfile
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_cathedral.bend"
WIDTH = 512
PIXELS = WIDTH * WIDTH
MASK = 0xFFFFFFFF


def run(*args):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True,
                          capture_output=True).stdout


def png_chunk(kind, payload):
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def write_png(path, rgb):
    rows = bytearray()
    stride = WIDTH * 3
    for y in range(WIDTH):
        rows.append(0)
        rows.extend(rgb[y * stride:(y + 1) * stride])
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, WIDTH, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + png_chunk(b"IEND", b""))


def decode(raw):
    pixels = [int(x) for x in re.findall(rb"\d+", raw)]
    assert len(pixels) == PIXELS, len(pixels)
    rgb = bytearray(PIXELS * 3)
    for i, color in enumerate(pixels):
        assert 0 <= color <= 0xFFFFFF
        at = 3 * i
        rgb[at] = (color >> 16) & 255
        rgb[at + 1] = (color >> 8) & 255
        rgb[at + 2] = color & 255
    return rgb, sum(pixels) & MASK


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--frames", type=int, default=120)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--output-dir", type=Path, default=ROOT / "bench")
    p.add_argument("--stills", type=int, nargs="+", default=[0, 24, 48, 72, 96, 119])
    p.add_argument("--video", type=Path, default=ROOT / "bench/bullet-cathedral.mp4")
    p.add_argument("--report", type=Path, default=ROOT / "bench/bullet-cathedral-report.json")
    args = p.parse_args()
    assert 1 <= args.frames <= 240 and 1 <= args.fps <= 120
    assert all(0 <= n < args.frames for n in args.stills)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.video.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bullet-cathedral-") as directory:
        generated = Path(directory) / "bend.c"
        binary = Path(directory) / "bend"
        run("bun", ROOT.parent / "bend/bend2/main.ts", SOURCE, "-o", generated)
        run("clang", "-O3", generated, "-o", binary)
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg is required for the MP4 export")
        encoder = subprocess.Popen(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
             "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{WIDTH}", "-r", str(args.fps),
             "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "slow",
             "-crf", "16", "-pix_fmt", "yuv420p", str(args.video)],
            stdin=subprocess.PIPE, cwd=ROOT)
        checksums = []
        stills = {}
        export_seconds = []
        try:
            for frame in range(args.frames):
                started = time.perf_counter()
                raw = run(binary, "--threads", 1, "--gpu", "off", "--",
                          frame, 0)
                rgb, checksum = decode(raw)
                checksums.append(checksum)
                assert encoder.stdin is not None
                encoder.stdin.write(rgb)
                if frame in args.stills:
                    path = args.output_dir / f"bullet-cathedral-frame-{frame:03}.png"
                    write_png(path, rgb)
                    measured = run(binary, "--threads", 1, "--gpu", "off", "--",
                                   frame).split()
                    assert int(measured[1]) == checksum, (frame, checksum, measured)
                    score = int(run(binary, "--threads", 1, "--gpu", "off", "--",
                                    frame, 1))
                    player_hp = int(run(binary, "--threads", 1, "--gpu", "off", "--",
                                        frame, 2))
                    stills[str(frame)] = {
                        "path": str(path.relative_to(ROOT)),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "checksum": checksum, "accepted_hits": score,
                        "player_shield": player_hp,
                    }
                export_seconds.append(time.perf_counter() - started)
                if frame % 16 == 0 or frame == args.frames - 1:
                    print(f"frame {frame + 1}/{args.frames}", flush=True)
        finally:
            if encoder.stdin:
                encoder.stdin.close()
        assert encoder.wait() == 0
        sample = run(binary, "--threads", 1, "--gpu", "off", "--",
                     min(args.frames, 60), "bench", "x").split()
        report = {
            "description": "Bullet Cathedral, all simulation and RGB pixels computed in Bend",
            "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "compiler_commit": run("git", "-C", ROOT.parent / "bend", "rev-parse",
                                   "HEAD").decode().strip(),
            "frames": args.frames, "fps_encoding": args.fps,
            "resolution": [WIDTH, WIDTH],
            "video": str(args.video.relative_to(ROOT)),
            "video_sha256": hashlib.sha256(args.video.read_bytes()).hexdigest(),
            "frame_checksums": checksums, "stills": stills,
            "sequential_bend_frames": min(args.frames, 60),
            "sequential_bend_time_us": int(sample[0]),
            "sequential_bend_checksum": int(sample[1]),
            "median_export_seconds_per_frame": statistics.median(export_seconds),
            "timing_note": "Bend sequential time includes simulation, framebuffer construction, and pixel checksum; export timing includes process startup, text transfer, PNG/MP4 encoding, and repeated replay from frame zero",
        }
        args.report.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
