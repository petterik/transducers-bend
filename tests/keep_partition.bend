import Base
import ../transduce.bend as T
import ../examples/tree.bend as Tree

def bool_value(x: Bool) -> Maybe<U32>:
  match x:
    case False{}:
      None{}
    case True{}:
      Some{42}

def no_value(x: Bool) -> Maybe<U32>:
  None{}

def keep_value(x: U32) -> Maybe<U32>:
  Some{(x + 10 : U32)}

def bool_values() -> Tree.Tree<Bool>:
  Tree.Branch{Tree.Leaf{True{}}, Tree.Branch{Tree.Leaf{False{}}, Tree.Leaf{True{}}}}

def keep_closure(f: Unit -> U32) -> Maybe<U32>:
  Some{f(Unit{})}

def add_function(acc: U32, f: Unit -> U32) -> U32:
  (acc + f(Unit{}) : U32)

def group_sum(xs: List<(Unit -> U32)>) -> U32:
  List.foldl(~&1, ~(Unit -> U32), ~U32, ~add_function, xs, 0)

def append_group(acc: List<U32>, xs: List<(Unit -> U32)>) -> List<U32>:
  group_sum(xs) <> acc

def affine_groups() -> T.Reducer<List<(Unit -> U32)>, List<U32>>:
  T.reducing(~List<(Unit -> U32)>, ~List<U32>, ~List<U32>,
    ~append_group, ~(xs => List.reverse(&1, U32, xs)))

def values() -> Tree.Tree<U32>:
  Tree.Branch{Tree.Leaf{1},
    Tree.Branch{Tree.Leaf{2},
      Tree.Branch{Tree.Leaf{3}, Tree.Branch{Tree.Leaf{4}, Tree.Leaf{5}}}}}

def show_groups(xs: List<List<U32>>) -> String:
  List.show(~&1, ~List<U32>, ~(ys => List.show(~&1, ~U32, ~U32.show, ys)), xs)

def stopped_start(u: Unit) -> T.Control<U32>:
  T.Stop{7}

def stopped_step(s: U32, xs: List<U32>) -> T.Control<U32>:
  T.Stop{(s + U32.from_nat(List.length(&1, U32, xs)) + 100 : U32)}

def stopped_down() -> T.Reducer<List<U32>, U32>:
  T.Reducer{Unit, U32, stopped_start, stopped_step, s => s}

def stop_during_flush(s: U32, xs: List<U32>) -> T.Control<U32>:
  T.Stop{(s + U32.from_nat(List.length(&1, U32, xs)) : U32)}

def stop_flush_down() -> T.Reducer<List<U32>, U32>:
  T.Reducer{Unit, U32, u => T.Continue{0}, stop_during_flush, s => s}

def nested_groups() -> T.Reducer<U32, List<List<List<U32>>>>:
  T.partition_all(~U32, ~List<List<List<U32>>>,
    ~T.partition_all(~List<U32>, ~List<List<List<U32>>>,
      ~T.into_list(~List<List<U32>>)))

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~Tree.over_tree(~U32, ~List<U32>,
        ~T.keep(~U32, ~U32, ~List<U32>, ~keep_value, ~T.into_list(~U32))),
        Unit{}, values())))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~Tree.over_tree(~Bool, ~List<U32>,
        ~T.keep(~Bool, ~U32, ~List<U32>, ~bool_value, ~T.into_list(~U32))),
        Unit{}, bool_values())))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~T.over_list(~Bool, ~List<U32>,
        ~T.keep(~Bool, ~U32, ~List<U32>, ~no_value, ~T.into_list(~U32))),
        Unit{}, [True{}, False{}])))
    IO.print(show_groups(T.transduce(~Tree.over_tree(~U32, ~List<List<U32>>,
      ~T.partition_all(~U32, ~List<List<U32>>, ~T.into_list(~List<U32>))),
      (2n, Unit{}), values())))
    IO.print(show_groups(T.transduce(~Tree.over_tree(~U32, ~List<List<U32>>,
      ~T.take(~U32, ~List<List<U32>>,
        ~T.partition_all(~U32, ~List<List<U32>>, ~T.into_list(~List<U32>)))),
      (3n, (2n, Unit{})), values())))
    IO.print(show_groups(T.transduce(~Tree.over_tree(~U32, ~List<List<U32>>,
      ~T.partition_all(~U32, ~List<List<U32>>,
        ~T.take(~List<U32>, ~List<List<U32>>, ~T.into_list(~List<U32>)))),
      (2n, (1n, Unit{})), values())))
    IO.print(show_groups(T.transduce(~Tree.over_tree(~U32, ~List<List<U32>>,
      ~T.partition_all(~U32, ~List<List<U32>>, ~T.into_list(~List<U32>))),
      (0n, Unit{}), values())))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~Tree.over_tree(~U32, ~List<U32>,
        ~T.map(~U32, ~Maybe<U32>, ~List<U32>, ~keep_value,
          ~T.cat_maybe(~U32, ~List<U32>, ~T.into_list(~U32)))),
        Unit{}, values())))
    IO.print(U32.show(T.transduce(~T.over_list(~U32, ~U32,
      ~T.partition_all(~U32, ~U32, ~stopped_down())),
      (2n, Unit{}), [1, 2, 3])))
    IO.print(U32.show(T.transduce(~T.over_list(~U32, ~U32,
      ~T.partition_all(~U32, ~U32, ~stop_flush_down())),
      (3n, Unit{}), [1, 2])))
    IO.print(show_groups(T.transduce(~T.over_list(~U32, ~List<List<U32>>,
      ~T.partition_all(~U32, ~List<List<U32>>, ~T.into_list(~List<U32>))),
      (3n, Unit{}), [])))
    IO.print(List.show(~&1, ~List<List<U32>>, ~show_groups,
      T.transduce(~T.over_list(~U32, ~List<List<List<U32>>>,
        ~nested_groups()), (2n, (2n, Unit{})), [1, 2, 3, 4, 5])))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~Tree.over_tree(~(Unit -> U32), ~List<U32>,
        ~T.keep(~(Unit -> U32), ~U32, ~List<U32>, ~keep_closure, ~T.into_list(~U32))),
        Unit{}, Tree.Branch{Tree.Leaf{u => 7}, Tree.Leaf{u => 8}})))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~Tree.over_tree(~(Unit -> U32), ~List<U32>,
        ~T.partition_all(~(Unit -> U32), ~List<U32>, ~affine_groups())),
        (2n, []), Tree.Branch{Tree.Leaf{u => 7}, Tree.Leaf{u => 8}})))
#|[11, 12, 13, 14, 15]
#|[42, 42]
#|[]
#|[[1, 2], [3, 4], [5]]
#|[[1, 2], [3]]
#|[[1, 2]]
#|[]
#|[11, 12, 13, 14, 15]
#|7
#|2
#|[]
#|[[[1, 2], [3, 4]], [[5]]]
#|[7, 8]
#|[15]
