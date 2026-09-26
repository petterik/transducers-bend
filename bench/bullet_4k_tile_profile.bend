import Base
import ./bullet_cathedral_4k_tiled16.bend as B
import ./array_partition/bench_clock.bend as Clock

# Time one tile after the frame's world and bullet pool have been prepared.
def timed_tile(+frame: U32, tile: U32) -> IO(Unit):
  do IO<Unit>:
    world : B.Damage <- IO.pure(B.Damage,
      B.simulate(U32.to_nat(U32.inc(frame)), 0, B.initial()))
    pool : B.BulletPool <- IO.pure(B.BulletPool, B.build_pool(frame))
    before : Nat <- Clock.now_us()
    checksum : U32 <- IO.pure(U32,
      B.render_tile(world, pool, frame, tile))
    after : Nat <- Clock.now_us()
    IO.print(Nat.show(Nat.sub(after, before)) ++ " " ++
      U32.show(checksum))

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case frame <> tile <> rest:
      timed_tile(B.parsed_u32(U32.read(frame)),
        B.parsed_u32(U32.read(tile)))
    case _: IO.print("expected frame and tile")

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
