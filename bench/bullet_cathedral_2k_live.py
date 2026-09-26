#!/usr/bin/env python3
"""Play a continuously simulated 1920x1080 Bullet Cathedral run on the CPU."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_cathedral_2k_live.bend"
WIDTH, HEIGHT = 1920, 1080
FRAME_BYTES = WIDTH * HEIGHT * 3


def compile_bend(binary, generated):
    subprocess.run(
        ["bun", str(ROOT.parent / "bend/bend2/main.ts"), str(SOURCE),
         "-o", str(generated)], cwd=ROOT, check=True)
    subprocess.run(["clang", "-O3", str(generated), "-o", str(binary)],
                   cwd=ROOT, check=True)


def packed_sum(rgb):
    """Match Bend's wrapping sum of packed 0xRRGGBB pixels."""
    return (sum(rgb[0::3]) * 65536 + sum(rgb[1::3]) * 256
            + sum(rgb[2::3])) & 0xFFFFFFFF


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=30,
                        help="playback duration (default: 30)")
    parser.add_argument("--fps", type=int, default=24,
                        help="playback frame rate (default: 24)")
    parser.add_argument("--frames", type=int,
                        help="exact frame count; overrides --minutes")
    parser.add_argument("--headless", action="store_true",
                        help="check the stream without opening a window")
    parser.add_argument("--window-width", type=int, default=1280,
                        help="window width (default: 1280)")
    args = parser.parse_args()
    if args.fps < 1 or args.minutes <= 0 or args.window_width < 1:
        parser.error("--fps, --minutes, and --window-width must be positive")
    frames = (args.frames if args.frames is not None
              else round(args.minutes * 60 * args.fps))
    if not 1 <= frames <= 0xFFFFFFFF:
        parser.error("frame count must be between 1 and 4,294,967,295")
    if not args.headless and shutil.which("ffplay") is None:
        parser.error("ffplay is required for the window; install ffmpeg")

    with tempfile.TemporaryDirectory(prefix="bullet-cathedral-2k-") as tmp:
        generated = Path(tmp) / "live.c"
        binary = Path(tmp) / "live"
        fifo = Path(tmp) / "pixels.rgb"
        os.mkfifo(fifo)
        compile_bend(binary, generated)
        bend = subprocess.Popen(
            [str(binary), "--threads", "1", "--gpu", "off", "--",
             str(fifo), str(frames)], cwd=ROOT, stdout=subprocess.DEVNULL)
        player = None
        stopped_by_viewer = False
        try:
            if not args.headless:
                player = subprocess.Popen(
                    ["ffplay", "-hide_banner", "-loglevel", "warning",
                     "-nostats", "-autoexit", "-window_title",
                     "Bullet Cathedral — 2K CPU transducers",
                     "-x", str(args.window_width),
                     "-y", str(round(args.window_width * HEIGHT / WIDTH)),
                     "-f", "rawvideo", "-pixel_format", "rgb24",
                     "-video_size", f"{WIDTH}x{HEIGHT}",
                     "-framerate", str(args.fps), "-i", "pipe:0"],
                    cwd=ROOT, stdin=subprocess.PIPE)
            started = time.monotonic()
            with fifo.open("rb") as source:
                for frame in range(frames):
                    if player is not None and player.poll() is not None:
                        stopped_by_viewer = True
                        break
                    rgb = source.read(FRAME_BYTES)
                    if len(rgb) != FRAME_BYTES:
                        raise RuntimeError(f"Bend stopped before frame {frame}")
                    if player is not None:
                        assert player.stdin is not None
                        try:
                            player.stdin.write(rgb)
                        except BrokenPipeError:
                            stopped_by_viewer = True
                            break
                    if frame == 0 or (frame + 1) % 120 == 0:
                        elapsed = time.monotonic() - started
                        print(f"frame {frame + 1}/{frames}, checksum "
                              f"{packed_sum(rgb)}, "
                              f"{(frame + 1) / elapsed:.1f} streamed fps",
                              flush=True)
            if player is not None:
                assert player.stdin is not None
                if not player.stdin.closed:
                    try:
                        player.stdin.close()
                    except BrokenPipeError:
                        stopped_by_viewer = True
                if player.wait() != 0 and not stopped_by_viewer:
                    raise RuntimeError("ffplay could not display the stream")
            if stopped_by_viewer and bend.poll() is None:
                bend.terminate()
            if bend.wait() != 0 and not stopped_by_viewer:
                raise RuntimeError("Bend stopped with an error")
        except KeyboardInterrupt:
            print("Stopped.", file=sys.stderr)
        finally:
            if player is not None and player.poll() is None:
                player.terminate()
                player.wait()
            if bend.poll() is None:
                bend.terminate()
            bend.wait()


if __name__ == "__main__":
    main()
