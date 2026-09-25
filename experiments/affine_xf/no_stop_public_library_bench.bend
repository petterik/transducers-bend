import Base
import ../../xf.bend as X
import ../../xf_legacy.bend as Old
import ../../bench/array_partition/bench_clock.bend as Clock
import ./static_recipe_bench.bend as B

def direct_array(xs: Array<U32>, state: U32) -> U32:
  match xs:
    case ALeaf{x}: (state + U32.inc(x) : U32)
    case ANode{left, right}:
      direct_array(right, direct_array(left, state))

def choose_array(mode: Nat, xs: Array<U32>) -> U32:
  match mode:
    case 0n: direct_array(xs, 0)
    case 1n: X.transduce(X.map(~U32, ~U32, ~U32.inc), X.sum_rf(), 0, xs)
    case 2n: X.transduce(X.comp2(
      X.map(~U32, ~U32, ~U32.inc), X.take(~U32, 524288n)),
      X.sum_rf(), 0, xs)
    case _: Old.transduce(Old.comp2(
      Old.map(~U32, ~U32, ~U32.inc), Old.take(~U32, 524288n)),
      Old.sum_rf(), 0, xs)

def measure_array(mode: Nat, depth: Nat) -> IO(Nat & U32):
  xs = Array.new(U32, depth, 1)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, choose_array(mode, xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> depth <> rest:
      do IO<Unit>:
        result : Nat & U32 <- measure_array(B.arg_nat(mode), B.arg_nat(depth))
        IO.print(B.show_result(result))
    case _:
      do IO<Unit>:
        result : Nat & U32 <- measure_array(1n, 4n)
        IO.print(B.show_result(result))

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
