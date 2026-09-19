import Base
import ../transduce.bend as T
import ../examples/tree.bend as Tree

type State is Type:
  State{left: Nat, sum: U32}

def control(n: Nat, sum: U32) -> T.Control<State>:
  match n:
    case 0n:
      T.Stop{State{0n, sum}}
    case 1n+p:
      T.Continue{State{1n+p, sum}}

# The runner instruments these three functions to check exact lifecycle counts.
def begin(n: Nat) -> T.Control<State>:
  control(n, 0)

def advance(state: State, x: U32) -> T.Control<State>:
  match state:
    case State{0n, sum}:
      T.Stop{State{0n, 999}}
    case State{1n+p, sum}:
      control(p, (sum + x : U32))

def done(state: State) -> U32:
  match state:
    case State{left, sum}:
      (sum + 1000 : U32)

def consumer() -> T.Reducer<U32, U32>:
  T.Reducer{Nat, State, n => begin(n), s => x => advance(s, x), s => done(s)}

def digits() -> T.Reducer<Char, U32>:
  T.map(~Char, ~U32, ~U32, ~(c => (Char.to_u32(c) - 48 : U32)), ~consumer())

def main() -> List<U32>:
  [T.transduce(~T.over_list(~U32, ~U32, ~consumer()), 2n, [1, 2, 3]),
   T.transduce(~T.over_list(~U32, ~U32, ~consumer()), 0n, [1, 2, 3]),
   T.transduce(~T.over_list(~U32, ~U32, ~consumer()), 9n, []),
   T.transduce(~T.over_range(~U32, ~consumer()), 2n, T.range_between(1, 4)),
   T.transduce(~T.over_range(~U32, ~consumer()), 0n, T.range_between(1, 4)),
   T.transduce(~T.over_range(~U32, ~consumer()), 9n, T.range(0)),
   T.transduce(~T.over_string(~U32, ~digits()), 2n, "123"),
   T.transduce(~T.over_string(~U32, ~digits()), 0n, "123"),
   T.transduce(~T.over_string(~U32, ~digits()), 9n, ""),
   T.transduce(~Tree.over_tree(~U32, ~U32, ~consumer()), 2n,
     Tree.Branch{Tree.Leaf{1}, Tree.Branch{Tree.Leaf{2}, Tree.Leaf{3}}}),
   T.transduce(~Tree.over_tree(~U32, ~U32, ~consumer()), 0n,
     Tree.Branch{Tree.Leaf{1}, Tree.Leaf{2}}),
   T.transduce(~Tree.over_tree(~U32, ~U32, ~consumer()), 9n, Tree.EmptyTree{})]
#|[1003, 1000, 1000, 1003, 1000, 1000, 1003, 1000, 1000, 1003, 1000, 1000]
