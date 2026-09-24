import Base
import ./bench_clock.bend as BenchClock

def main() -> IO(Unit):
  do IO<Unit>:
    before : Nat <- BenchClock.now_us()
    after : Nat <- BenchClock.now_us()
    IO.print(Nat.show(Nat.sub(after, before)))
