import Base
import ./permit_protocol.bend as P
import ./branch_control_ablation.bend as Tree
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
    case _: P.total_array(xs)

def choose_tree(mode: Nat, xs: Tree.Branch) -> U32:
  match mode:
    case 0n: Tree.direct(xs, 0)
    case _: P.total_tree(xs)

def measure_array(mode: Nat, depth: Nat) -> IO(Nat & U32):
  xs = Array.new(U32, depth, 1)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, choose_array(mode, xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def measure_tree(mode: Nat, depth: Nat) -> IO(Nat & U32):
  xs = Tree.build(depth, 1)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, choose_tree(mode, xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def measure(source: Nat, mode: Nat, depth: Nat) -> IO(Nat & U32):
  match source:
    case 0n: measure_array(mode, depth)
    case _: measure_tree(mode, depth)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case source <> mode <> depth <> rest:
      do IO<Unit>:
        result : Nat & U32 <- measure(B.arg_nat(source), B.arg_nat(mode),
          B.arg_nat(depth))
        IO.print(B.show_result(result))
    case _:
      do IO<Unit>:
        result : Nat & U32 <- measure(0n, 1n, 4n)
        IO.print(B.show_result(result))

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
