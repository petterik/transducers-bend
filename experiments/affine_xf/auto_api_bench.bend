import Base
import ./static_recipe_bench.bend as B
import ./rank2_rf_values.bend as V
import ./rank2_sources.bend as Sources
import ../../bench/array_partition/bench_clock.bend as Clock

def api_list(xs: List<U32>, n: Nat) -> U32:
  V.transduce(V.compose(V.shifted(1), V.taking_u32(n)),
    V.sum_rf(), 0, xs)

def api_source(xs: List<U32>, n: Nat) -> U32:
  V.transduce_from(V.compose(V.shifted(1), V.taking_u32(n)),
    V.sum_rf(), 0, Sources.list_source(~U32, xs))

def once(mode: Nat, xs: List<U32>, n: Nat) -> U32:
  match mode:
    case 0n:
      B.direct(xs, n, 0)
    case 1n:
      B.current(xs, n)
    case 2n:
      B.rank2(xs, n)
    case 3n:
      api_list(xs, n)
    case _:
      api_source(xs, n)

def measure(mode: Nat, +size: Nat) -> IO(Nat & U32):
  xs = B.numbers(size, [])
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, once(mode, xs, size))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def run_measure(mode: Nat, size: Nat) -> IO(Unit):
  do IO<Unit>:
    result : Nat & U32 <- measure(mode, size)
    IO.print(B.show_result(result))

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> size <> rest:
      run_measure(B.arg_nat(mode), B.arg_nat(size))
    case _:
      run_measure(0n, 200000n)

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
