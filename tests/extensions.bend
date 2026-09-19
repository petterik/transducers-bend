import Base
import ../transduce.bend as T
import ../examples/tree.bend as Tree

def first_two() -> T.Reducer<U32, List<U32>>:
  T.take(~U32, ~List<U32>, ~T.into_list(~U32))

def affine() -> T.Reducer<(Unit -> U32), List<(Unit -> U32)>>:
  T.take(~(Unit -> U32), ~List<(Unit -> U32)>, ~T.into_list(~(Unit -> U32)))

def add(acc: U32, f: Unit -> U32) -> U32:
  (acc + f(Unit{}) : U32)

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~Tree.over_tree(~U32, ~List<U32>, ~first_two()), (2n, Unit{}),
        Tree.Branch{Tree.Leaf{1}, Tree.Branch{Tree.Leaf{2}, Tree.Leaf{3}}})))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~Tree.over_tree(~U32, ~List<U32>, ~first_two()), (0n, Unit{}),
        Tree.Branch{Tree.Leaf{1}, Tree.Leaf{2}})))
    IO.print(Nat.show(T.transduce(~Tree.over_tree(~U32, ~Nat, ~T.count(~U32)), Unit{}, Tree.EmptyTree{})))
    IO.print(U32.show(List.foldl(~&1, ~(Unit -> U32), ~U32, ~add,
      T.transduce(~Tree.over_tree(~(Unit -> U32), ~List<(Unit -> U32)>, ~affine()), (1n, Unit{}),
        Tree.Branch{Tree.Leaf{u => 7}, Tree.Leaf{u => 8}}), 0)))
#|[1, 2]
#|[]
#|0
#|7
