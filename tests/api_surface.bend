import Base
import ../transduce.bend as T
import ../examples/tree.bend as Tree

# One type-changing declaration is shared by two consumers and three sources.
def to_nat(x: U32) -> Maybe<Nat>:
  Some{U32.to_nat(x)}

def pipeline(~R: Type, ~down: T.Reducer<Nat, R>) -> T.Reducer<U32, R>:
  T.keep(~U32, ~Nat, ~R, ~to_nat, ~down)

def values() -> Tree.Tree<U32>:
  Tree.Branch{Tree.Leaf{1}, Tree.Branch{Tree.Leaf{2}, Tree.Leaf{3}}}

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(Nat.show(T.transduce(
      ~T.over_range(~Nat, ~pipeline(~Nat, ~T.count(~Nat))),
      Unit{}, T.range_between(1, 4))))
    IO.print(List.show(~&1, ~Nat, ~Nat.show,
      T.transduce(
        ~T.over_list(~U32, ~List<Nat>, ~pipeline(~List<Nat>, ~T.into_list(~Nat))),
        Unit{}, [4, 5])))
    IO.print(Nat.show(T.transduce(
      ~Tree.over_tree(~U32, ~Nat, ~pipeline(~Nat, ~T.count(~Nat))),
      Unit{}, values())))
#|3
#|[4, 5]
#|3
