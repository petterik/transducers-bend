import Base

# Higher-resolution clock for native benchmark fixtures. The implementation
# uses the same monotonic clock as IO.now, but keeps microseconds.
def now_us() -> IO(Nat):
  import "./bench_clock.c"
  import "./bench_clock.js"
