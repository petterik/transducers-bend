import Base
import ../../xf.bend as X
import ../../examples/branch_public.bend as Branch
import ../../bench/array_partition/bench_clock.bend as Clock
import ./static_recipe_bench.bend as Args

def choose(mode: Nat, xs: Branch.Branch) -> U32:
  match mode:
    case 0n: Branch.direct(xs, 0)
    case 1n: X.transduce(X.map(~U32, ~U32, ~U32.inc),
      X.sum_rf(), 0, xs)
    case _: X.transduce(X.map(~U32, ~U32, ~U32.inc),
      X.sum_rf(), 0, Branch.Branch.source(xs))

def measure(mode: Nat, depth: Nat) -> IO(Nat & U32):
  xs = Branch.build(depth, 1)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, choose(mode, xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> depth <> rest:
      do IO<Unit>:
        result : Nat & U32 <- measure(Args.arg_nat(mode), Args.arg_nat(depth))
        IO.print(Args.show_result(result))
    case _:
      do IO<Unit>:
        result : Nat & U32 <- measure(1n, 4n)
        IO.print(Args.show_result(result))

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
