#!/usr/bin/env python3
"""Play a long, continuously simulated Bullet Cathedral run from Bend frames."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_cathedral_live.bend"
WIDTH = HEIGHT = 512
PIXELS = WIDTH * HEIGHT


def compile_bend(binary, generated):
    subprocess.run(
        ["bun", str(ROOT.parent / "bend/bend2/main.ts"), str(SOURCE),
         "-o", str(generated)], cwd=ROOT, check=True)
    subprocess.run(["clang", "-O3", str(generated), "-o", str(binary)],
                   cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=5,
                        help="playback duration (default: 5)")
    parser.add_argument("--fps", type=int, default=10,
                        help="playback frame rate (default: 10)")
    parser.add_argument("--frames", type=int,
                        help="exact frame count; overrides --minutes")
    parser.add_argument("--headless", action="store_true",
                        help="decode and check frames without opening a window")
    args = parser.parse_args()
    if args.fps < 1 or args.minutes <= 0:
        parser.error("--fps and --minutes must be positive")
    frames = (args.frames if args.frames is not None
              else round(args.minutes * 60 * args.fps))
    if not 1 <= frames <= 0xFFFFFFFF:
        parser.error("frame count must be between 1 and 4,294,967,295")
    if not args.headless and shutil.which("ffplay") is None:
        parser.error("ffplay is required for the window; install ffmpeg")

    with tempfile.TemporaryDirectory(prefix="bullet-cathedral-live-") as tmp:
        generated = Path(tmp) / "live.c"
        binary = Path(tmp) / "live"
        fifo = Path(tmp) / "pixels.rgb"
        os.mkfifo(fifo)
        compile_bend(binary, generated)
        bend = subprocess.Popen(
            [str(binary), "--threads", "1", "--gpu", "off", "--",
             str(fifo), str(frames)], cwd=ROOT, stdout=subprocess.DEVNULL)
        player = None
        try:
            if not args.headless:
                player = subprocess.Popen(
                    ["ffplay", "-hide_banner", "-loglevel", "warning", "-nostats",
                     "-autoexit", "-window_title", "Bullet Cathedral — Bend transducers",
                     "-x", "1024", "-y", "1024", "-f", "rawvideo",
                     "-pixel_format", "rgb24", "-video_size", "512x512",
                     "-framerate", str(args.fps), "-i", "pipe:0"],
                    cwd=ROOT, stdin=subprocess.PIPE)
            started = time.monotonic()
            stopped_by_viewer = False
            with fifo.open("rb") as source:
                for frame in range(frames):
                    if player is not None and player.poll() is not None:
                        stopped_by_viewer = True
                        break
                    rgb = source.read(PIXELS * 3)
                    if len(rgb) != PIXELS * 3:
                        raise RuntimeError(f"Bend stopped before frame {frame}")
                    if player is not None:
                        assert player.stdin is not None
                        try:
                            player.stdin.write(rgb)
                        except BrokenPipeError:
                            stopped_by_viewer = True
                            break
                    if args.headless or frame % 30 == 0:
                        elapsed = time.monotonic() - started
                        checksum = (sum(rgb[0::3]) * 65536
                                    + sum(rgb[1::3]) * 256
                                    + sum(rgb[2::3])) & 0xFFFFFFFF
                        print(f"frame {frame + 1}/{frames}, checksum {checksum}, "
                              f"{(frame + 1) / elapsed:.1f} generated fps",
                              flush=True)
            if player is not None:
                assert player.stdin is not None
                if not player.stdin.closed:
                    player.stdin.close()
                if player.wait() != 0:
                    raise RuntimeError("ffplay could not display the video stream")
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
