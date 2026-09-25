import Base
import ../../transduce.bend as T
import ../../bench/array_partition/bench_clock.bend as Clock
import ./static_recipe_bench.bend as B
import ./branch_control_ablation.bend as Tree

# A deliberately general total fold: the step cannot stop, and its state
# type is arbitrary. This measures the performance available to a proven
# no-stop specialization without changing the existing Source contract.
def fold_array_total(~S: Type, ~step: S -> U32 -> S,
  xs: Array<U32>, state: S) -> S:
  match xs:
    case ALeaf{x}:
      step(state, x)
    case ANode{left, right}:
      fold_array_total(~S, ~step, right,
        fold_array_total(~S, ~step, left, state))

def fold_tree_total(~S: Type, ~step: S -> U32 -> S,
  xs: Tree.Branch, state: S) -> S:
  match xs:
    case Tree.Tip{x}:
      step(state, x)
    case Tree.Fork{left, right}:
      fold_tree_total(~S, ~step, right,
        fold_tree_total(~S, ~step, left, state))

def map_step(~S: Type, ~f: U32 -> U32,
  ~down: S -> U32 -> S) -> S -> U32 -> S:
  s => x => down(s, f(x))

def direct_array(xs: Array<U32>, state: U32) -> U32:
  match xs:
    case ALeaf{x}:
      (state + U32.inc(x) : U32)
    case ANode{left, right}:
      direct_array(right, direct_array(left, state))

def control_array(xs: Array<U32>) -> U32:
  Tree.finish(T.reduce_array(~U32, ~U32,
    ~(s => x => T.Continue{(s + U32.inc(x) : U32)}),
    xs, T.Continue{0}))

def total_array(xs: Array<U32>) -> U32:
  fold_array_total(~U32, ~(s => x => (s + U32.inc(x) : U32)), xs, 0)

def total_tree(xs: Tree.Branch) -> U32:
  fold_tree_total(~U32, ~(s => x => (s + U32.inc(x) : U32)), xs, 0)

def composed_array(xs: Array<U32>) -> U32:
  fold_array_total(~U32,
    ~map_step(~U32, ~U32.inc, ~(s => x => (s + x : U32))), xs, 0)

def composed_tree(xs: Tree.Branch) -> U32:
  fold_tree_total(~U32,
    ~map_step(~U32, ~U32.inc, ~(s => x => (s + x : U32))), xs, 0)

def total_array_reduction() -> T.Reduction:
  T.Reduction{u => Array<U32>, u => U32, u => U32,
    config => xs => fold_array_total(~U32,
      ~map_step(~U32, ~U32.inc, ~(s => x => (s + x : U32))), xs, config)}

def total_tree_reduction() -> T.Reduction:
  T.Reduction{u => Tree.Branch, u => U32, u => U32,
    config => xs => fold_tree_total(~U32,
      ~map_step(~U32, ~U32.inc, ~(s => x => (s + x : U32))), xs, config)}

def public_total_array(xs: Array<U32>) -> U32:
  T.transduce(~total_array_reduction(), 0, xs)

def public_total_tree(xs: Tree.Branch) -> U32:
  T.transduce(~total_tree_reduction(), 0, xs)

def choose_array(mode: Nat, xs: Array<U32>) -> U32:
  match mode:
    case 0n: direct_array(xs, 0)
    case 1n: control_array(xs)
    case 2n: total_array(xs)
    case 3n: composed_array(xs)
    case _: public_total_array(xs)

def choose_tree(mode: Nat, xs: Tree.Branch) -> U32:
  match mode:
    case 0n: Tree.direct(xs, 0)
    case 1n: Tree.finish(Tree.control(xs, T.Continue{0}))
    case 2n: total_tree(xs)
    case 3n: composed_tree(xs)
    case _: public_total_tree(xs)

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
        result : Nat & U32 <- measure(B.arg_nat(source), B.arg_nat(mode), B.arg_nat(depth))
        IO.print(B.show_result(result))
    case _:
      do IO<Unit>:
        result : Nat & U32 <- measure(1n, 2n, 4n)
        IO.print(B.show_result(result))

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
