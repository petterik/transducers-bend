import Base
import ../../xf.bend as X
import ../../transduce_core.bend as T
import ./permit_protocol.bend as P
import ./branch_control_ablation.bend as Tree
import ../../bench/array_partition/bench_clock.bend as Clock
import ./static_recipe_bench.bend as Args

# Mirror branch_api_ablation.bend with public and prototype cases exchanged.
# The two programs deliberately differ only in choose's case order.
# Both protocols traverse the same owned Tree.Branch values. This copies the
# source protocol shape so the comparison isolates their downstream APIs.
def drive_loop(~K: Data, ~S: Type,
  ~advance: S -> U32 -> S, ~inspect: S -> T.Checked<K, S>,
  xs: Tree.Branch, checked: T.Checked<K, S>) -> S:
  match xs checked:
    case Tree.Tip{x} T.Halted{permit, state}: state
    case Tree.Tip{x} T.Ready{state}: advance(state, x)
    case Tree.Fork{left, right} T.Halted{permit, state}: state
    case Tree.Fork{left, right} T.Ready{state}:
      drive_loop(~K, ~S, ~advance, ~inspect, right,
        inspect(drive_loop(~K, ~S, ~advance, ~inspect,
          left, T.Ready{state})))

def drive(~K: Data, ~S: Type,
  ~advance: S -> U32 -> S, ~inspect: S -> T.Checked<K, S>,
  xs: Tree.Branch, state: S) -> S:
  drive_loop(~K, ~S, ~advance, ~inspect, xs, inspect(state))

def source(xs: Tree.Branch) -> T.Source<U32, Tree.Branch,
  (K => S => advance => inspect => tree => state =>
    drive(~K, ~S, ~advance, ~inspect, tree, state))>:
  T.Source{xs}

def choose(mode: Nat, xs: Tree.Branch) -> U32:
  match mode:
    case 0n: Tree.direct(xs, 0)
    case 1n: P.total_tree(xs)
    case _: X.transduce(X.map(~U32, ~U32, ~P.inc),
      X.sum_rf(), 0, source(xs))

def measure(mode: Nat, depth: Nat) -> IO(Nat & U32):
  xs = Tree.build(depth, 1)
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
