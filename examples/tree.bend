# An independently defined source. Nothing in transduce.bend mentions Tree.
import Base
import ../transduce.bend as T

type Tree<-A: Type> is Type:
  EmptyTree{}
  Leaf{value: A}
  Branch{left: Tree<A>, right: Tree<A>}

# Ordered depth-first traversal. Each recursive call consumes a structural child.
def reduce(~A: Type, ~S: Type, ~advance: S -> A -> T.Control<S>, tree: Tree<A>, c: T.Control<S>) -> T.Control<S>:
  match tree c:
    case EmptyTree{} c:
      c
    case Leaf{x} T.Stop{s}:
      T.Stop{s}
    case Branch{left, right} T.Stop{s}:
      T.Stop{s}
    case Leaf{x} T.Continue{s}:
      advance(s, x)
    case Branch{left, right} T.Continue{s}:
      reduce(~A, ~S, ~advance, right, reduce(~A, ~S, ~advance, left, T.Continue{s}))

# Callers supply their pipeline once, as with the built-in over_* adapters.
def over_tree(~A: Type, ~R: Type, ~r: T.Reducer<A, R>) -> T.Reduction:
  T.reducible(~Tree<A>, ~A, ~R, ~(u => r),
    ~(xs => c => reduce(~A, ~T.State(A, R, r), ~(s => x => T.step(A, R, r, s, x)), xs, c)))
