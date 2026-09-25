import Base
import ./branch_control_ablation.bend as Tree
import ../../bench/array_partition/bench_clock.bend as Clock
import ./static_recipe_bench.bend as B

# An empty permit makes Halted impossible in live, checked Bend code.
type Flow<-K: Type, -S: Type> is Type:
  Ready{state: S}
  Halted{permit: K, state: S}

def inspect_total(-S: Type, state: S) -> Flow<Empty, S>:
  Ready{state}

def inspect_budget_case(done: Bool, left: U32, sum: U32) -> Flow<Unit, U32 & U32>:
  match done:
    case True{}: Halted{Unit{}, (left, sum)}
    case False{}: Ready{(left, sum)}

def inspect_budget(state: U32 & U32) -> Flow<Unit, U32 & U32>:
  (+left, sum) = state
  inspect_budget_case(U32.is_eq(left, 0), left, sum)

def fold_array(~K: Type, ~S: Type, ~step: S -> U32 -> S,
  ~inspect: S -> Flow<K, S>, xs: Array<U32>, flow: Flow<K, S>) -> Flow<K, S>:
  match xs flow:
    case ALeaf{x} Ready{state}:
      inspect(step(state, x))
    case ALeaf{x} Halted{permit, state}:
      Halted{permit, state}
    case ANode{left, right} Ready{state}:
      fold_array(~K, ~S, ~step, ~inspect, right,
        fold_array(~K, ~S, ~step, ~inspect, left, Ready{state}))
    case ANode{left, right} Halted{permit, state}:
      Halted{permit, state}

def fold_tree(~K: Type, ~S: Type, ~step: S -> U32 -> S,
  ~inspect: S -> Flow<K, S>, xs: Tree.Branch, flow: Flow<K, S>) -> Flow<K, S>:
  match xs flow:
    case Tree.Tip{x} Ready{state}:
      inspect(step(state, x))
    case Tree.Tip{x} Halted{permit, state}:
      Halted{permit, state}
    case Tree.Fork{left, right} Ready{state}:
      fold_tree(~K, ~S, ~step, ~inspect, right,
        fold_tree(~K, ~S, ~step, ~inspect, left, Ready{state}))
    case Tree.Fork{left, right} Halted{permit, state}:
      Halted{permit, state}

def finish_total(-S: Type, flow: Flow<Empty, S>) -> S:
  match flow:
    case Ready{state}: state
    case Halted{permit, state}:
      match permit:

def flow_state(-K: Type, -S: Type, flow: Flow<K, S>) -> S:
  match flow:
    case Ready{state}: state
    case Halted{permit, state}: state

# The source-facing driver returns only the accumulator. Flow stays private.
def drive_array(~K: Type, ~S: Type, ~step: S -> U32 -> S,
  ~inspect: S -> Flow<K, S>, xs: Array<U32>, state: S) -> S:
  flow_state(K, S, fold_array(~K, ~S, ~step, ~inspect,
    xs, inspect(state)))

def drive_tree(~K: Type, ~S: Type, ~step: S -> U32 -> S,
  ~inspect: S -> Flow<K, S>, xs: Tree.Branch, state: S) -> S:
  flow_state(K, S, fold_tree(~K, ~S, ~step, ~inspect,
    xs, inspect(state)))

def add_inc(state: U32, x: U32) -> U32:
  (state + U32.inc(x) : U32)

def budget_step(state: U32 & U32, x: U32) -> U32 & U32:
  (left, sum) = state
  ((left - 1 : U32), (sum + U32.inc(x) : U32))

def finish_budget(state: U32 & U32) -> U32:
  (left, sum) = state
  sum

def total_array(xs: Array<U32>) -> U32:
  drive_array(~Empty, ~U32, ~add_inc, ~inspect_total(U32), xs, 0)

def total_tree(xs: Tree.Branch) -> U32:
  drive_tree(~Empty, ~U32, ~add_inc, ~inspect_total(U32), xs, 0)

def affine_step(acc: Array<U32>, x: U32) -> Array<U32>:
  acc[0] <- x

def affine_array(xs: Array<U32>) -> Array<U32>:
  drive_array(~Empty, ~(Array<U32>), ~affine_step,
    ~inspect_total(Array<U32>), xs, Array.new(U32, 0n, 0))

def finish_budget_flow(flow: Flow<Unit, U32 & U32>) -> U32:
  match flow:
    case Ready{state}: finish_budget(state)
    case Halted{permit, state}: finish_budget(state)

# A nested source must preserve the stop signal from its downstream fold.
def cat_step(flow: Flow<Unit, U32 & U32>, x: U32) -> Flow<Unit, U32 & U32>:
  fold_array(~Unit, ~(U32 & U32), ~budget_step, ~inspect_budget,
    Array.new(U32, 1n, x), flow)

def inspect_cat(flow: Flow<Unit, U32 & U32>) -> Flow<Unit, Flow<Unit, U32 & U32>>:
  match flow:
    case Ready{state}: Ready{Ready{state}}
    case Halted{permit, state}: Halted{Unit{}, Halted{permit, state}}

def finish_cat(flow: Flow<Unit, Flow<Unit, U32 & U32>>) -> U32:
  match flow:
    case Ready{state}: finish_budget_flow(state)
    case Halted{permit, state}: finish_budget_flow(state)

def nested_cat_array(xs: Array<U32>, limit: U32) -> U32:
  finish_cat(fold_array(~Unit, ~(Flow<Unit, U32 & U32>),
    ~cat_step, ~inspect_cat, xs, Ready{inspect_budget((limit, 0))}))

def budget_array(xs: Array<U32>, limit: U32) -> U32:
  finish_budget(drive_array(~Unit, ~(U32 & U32), ~budget_step,
    ~inspect_budget, xs, (limit, 0)))

def budget_tree(xs: Tree.Branch, limit: U32) -> U32:
  finish_budget(drive_tree(~Unit, ~(U32 & U32), ~budget_step,
    ~inspect_budget, xs, (limit, 0)))

def initial_halt_array(xs: Array<U32>) -> U32:
  finish_budget_flow(fold_array(~Unit, ~(U32 & U32), ~budget_step,
    ~inspect_budget, xs, Halted{Unit{}, (0, 123)}))

def direct_array(xs: Array<U32>, state: U32) -> U32:
  match xs:
    case ALeaf{x}: (state + U32.inc(x) : U32)
    case ANode{left, right}:
      direct_array(right, direct_array(left, state))

def choose_array(mode: Nat, xs: Array<U32>, limit: U32) -> U32:
  match mode:
    case 0n: direct_array(xs, 0)
    case 1n: total_array(xs)
    case 2n: budget_array(xs, limit)
    case _: initial_halt_array(xs)

def choose_tree(mode: Nat, xs: Tree.Branch, limit: U32) -> U32:
  match mode:
    case 0n: Tree.direct(xs, 0)
    case 1n: total_tree(xs)
    case _: budget_tree(xs, limit)

def measure_array(mode: Nat, depth: Nat, limit: U32) -> IO(Nat & U32):
  xs = Array.new(U32, depth, 1)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, choose_array(mode, xs, limit))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def measure_tree(mode: Nat, depth: Nat, limit: U32) -> IO(Nat & U32):
  xs = Tree.build(depth, 1)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, choose_tree(mode, xs, limit))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def measure(source: Nat, mode: Nat, depth: Nat, limit: U32) -> IO(Nat & U32):
  match source:
    case 0n: measure_array(mode, depth, limit)
    case _: measure_tree(mode, depth, limit)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case source <> mode <> depth <> limit <> rest:
      do IO<Unit>:
        result : Nat & U32 <- measure(B.arg_nat(source), B.arg_nat(mode),
          B.arg_nat(depth), U32.from_nat(B.arg_nat(limit)))
        IO.print(B.show_result(result))
    case _:
      do IO<Unit>:
        result : Nat & U32 <- measure(0n, 1n, 4n, 3)
        IO.print(B.show_result(result))

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
