# A zero Nat field in a continuing scalar record does not imply Stop.
# Generic compiler optimizations must not infer take-like invariants by shape.
import Base
import ../transduce.bend as T

type State is Type:
  State{left: Nat, sum: U32}

def advance(state: State, x: U32) -> T.Control<State>:
  match state:
    case State{left, sum}:
      T.Stop{State{left, (sum + x : U32)}}

def finish(state: State) -> U32:
  match state:
    case State{left, sum}:
      sum

def consumer() -> T.Reducer<U32, U32>:
  T.Reducer{U32, State, sum => T.Continue{State{0n, sum}},
    s => x => advance(s, x), s => finish(s)}

def main() -> List<U32>:
  [T.transduce(~T.over_list(~U32, ~U32, ~consumer()), 10, [7, 8]),
   T.transduce(~T.over_range(~U32, ~consumer()), 10, T.range_between(7, 9)),
   T.transduce(~T.over_range(~U32, ~T.take(~U32, ~U32, ~consumer())), (1n, 10), T.range_between(7, 9)),
   T.transduce(~T.over_range(~U32, ~T.take(~U32, ~U32, ~consumer())), (0n, 10), T.range_between(7, 9))]
#|[17, 17, 17, 10]
