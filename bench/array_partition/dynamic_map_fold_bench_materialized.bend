import Base
import ./dynamic_map_fold_probe.bend as P
import ./bench_clock.bend as BenchClock

# Native microsecond measurement. All eight inputs are built before the clock
# starts; each timed operation includes mapping, folding, and source cleanup.
def batch_inputs(+n: Nat, count: Nat,
  acc: List<List<U32>>) -> List<List<U32>>:
  match count:
    case 0n:
      acc
    case 1n+p:
      batch_inputs(n, p, P.numbers(n, []) <> acc)

def fold_batch(xs: List<List<U32>>, +total: U32) -> U32:
  match xs:
    case Nil{}:
      total
    case items <> rest:
      fold_batch(rest, (total + P.materialized_sum(items) : U32))

def measure(xs: List<List<U32>>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- BenchClock.now_us()
    total : U32 <- IO.pure(U32, fold_batch(xs, 0))
    after : Nat <- BenchClock.now_us()
    return (Nat.sub(after, before), total)

def result_text(result: Nat & U32) -> String:
  (elapsed, total) = result
  String.append(U32.show(total), String.append(" ", Nat.show(elapsed)))

def main() -> IO(Unit):
  inputs = batch_inputs(200000n, 8n, [])
  do IO<Unit>:
    result : Nat & U32 <- measure(inputs)
    IO.print(result_text(result))
