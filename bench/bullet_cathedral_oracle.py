#!/usr/bin/env python3
"""Independently check swept hits and the nine-cell broad phase."""
import argparse
import math
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/bullet_cathedral.bend"


def bullet(frame, ident):
    spoke = ident & 127
    birth = ident >> 7
    age = frame - birth
    angle = spoke * 0.049087385 + birth * 0.105
    base_x = 256 + (spoke - 64) * 1.25 + math.sin(birth * 0.17) * 34
    drift = math.sin(angle) * 0.65
    x = base_x + age * drift
    y = 500 - age * 6
    return x, y, x - drift, y + 6


def hostile_bullet(frame, ident):
    spoke = ident & 127
    birth = ident >> 7
    age = frame - birth
    phase = birth & 3
    angle = spoke * 0.049087385 + birth * 0.105
    speed = 2.7 + phase * 0.45
    turn = angle + age * phase * 0.006
    vx = speed * math.cos(turn)
    vy = speed * math.sin(turn)
    x = 256 + age * vx
    y = 150 + age * vy
    return x, y, x - vx, y - vy


def target(frame, cell_x, cell_y):
    ident = cell_x + 16 * cell_y
    x = cell_x * 32 + 16 + math.sin(frame * 0.055 + ident * 0.27) * 5
    y = cell_y * 32 + 16 + math.cos(frame * 0.04 + ident * 0.31) * 5
    return x, y


def swept_hit(b, enemy, radius):
    x, y, old_x, old_y = b
    ex, ey = enemy
    vx = x - old_x
    vy = y - old_y
    ratio = ((ex - old_x) * vx + (ey - old_y) * vy) / max(vx * vx + vy * vy, 0.0001)
    t = max(0.0, min(1.0, ratio))
    dx = ex - (old_x + t * vx)
    dy = ey - (old_y + t * vy)
    return dx * dx + dy * dy <= radius * radius


def player_x(frame):
    return 256 + math.sin(frame * 0.08) * 90


def player_entered(frame, b):
    if not swept_hit(b, (player_x(frame), 480), math.sqrt(118.81)):
        return False
    old_x, old_y = b[2:]
    dx = old_x - player_x(max(frame - 1, 0))
    dy = old_y - 480
    return dx * dx + dy * dy > 118.81


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--frames", type=int, default=96)
    args = p.parse_args()
    assert 1 <= args.frames <= 240
    with tempfile.TemporaryDirectory(prefix="bullet-oracle-") as directory:
        binary = Path(directory) / "bend"
        subprocess.run(["bun", str(ROOT.parent / "bend/bend2/main.ts"),
                        str(SOURCE), "-o", str(binary)], cwd=ROOT,
                       check=True, capture_output=True)
        health = [3] * 256
        player_hp = 240
        score = 0
        examined = 0
        geometric_hits = 0
        for frame in range(args.frames):
            enemies = [target(frame, x, y) for y in range(16) for x in range(16)]
            begin = max(0, frame - 95) * 128
            for ident in range(begin, (frame + 1) * 128):
                if ident & 3:
                    if player_entered(frame, hostile_bullet(frame, ident)):
                        player_hp = max(0, player_hp - 1)
                    continue
                b = bullet(frame, ident)
                x, y = b[:2]
                if not (0 <= x < 512 and 0 <= y < 512):
                    continue
                cx = int(x) >> 5
                cy = int(y) >> 5
                for target_id, enemy in enumerate(enemies):
                    examined += 1
                    if swept_hit(b, enemy, 9.0):
                        geometric_hits += 1
                        tx = target_id & 15
                        ty = target_id >> 4
                        assert abs(tx - cx) <= 1 and abs(ty - cy) <= 1, (
                            "broad phase missed a hit", frame, ident, target_id)
                        if health[target_id]:
                            health[target_id] -= 1
                            score += 1
            output = subprocess.run(
                [str(binary), "--threads", "1", "--gpu", "off", "--",
                 str(frame), "1"], cwd=ROOT, check=True, capture_output=True,
                text=True).stdout.strip()
            assert int(output) == score, (frame, int(output), score)
            shield = subprocess.run(
                [str(binary), "--threads", "1", "--gpu", "off", "--",
                 str(frame), "2"], cwd=ROOT, check=True, capture_output=True,
                text=True).stdout.strip()
            assert int(shield) == player_hp, (
                frame, int(shield), player_hp)
            if frame % 8 == 0 or frame == args.frames - 1:
                print(f"frame {frame}: {score} accepted hits, "
                      f"player shield {player_hp}", flush=True)
        print(f"verified {examined} exhaustive pairs, {geometric_hits} geometric hits")


if __name__ == "__main__":
    main()
