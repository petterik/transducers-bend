import Base
import ../transduce.bend as T
import ../examples/tree.bend as Tree
import ./support/source_contract.bend as C

def show(xs: List<List<U32>>) -> String:
  List.show(~&1, ~List<U32>, ~(ys => List.show(~&1, ~U32, ~U32.show, ys)), xs)

def array_values() -> Array<U32>:
  a = Array.set(U32, [0 : U32*4n], 0, 1)
  b = Array.set(U32, a, 1, 2)
  c = Array.set(U32, b, 2, 3)
  Array.set(U32, c, 3, 4)

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(show(C.cases(~List<U32>,
      ~(xs => c => T.reduce_list(~U32, ~C.Trace, ~C.advance, xs, c)),
      ~(u => [1, 2, 3]), ~(u => []))))
    IO.print(show(C.cases(~T.Range,
      ~(xs => c => T.reduce_range(~C.Trace, ~C.advance, xs, c)),
      ~(u => T.range_between(1, 4)), ~(u => T.range(0)))))
    IO.print(show(C.cases(~String,
      ~(xs => c => T.reduce_string(~C.Trace, ~C.char_advance, xs, c)),
      ~(u => "123"), ~(u => ""))))
    IO.print(show(C.cases(~Tree.Tree<U32>,
      ~(xs => c => Tree.reduce(~U32, ~C.Trace, ~C.advance, xs, c)),
      ~(u => Tree.Branch{Tree.Leaf{1}, Tree.Branch{Tree.Leaf{2}, Tree.Leaf{3}}}),
      ~(u => Tree.EmptyTree{}))))
    IO.print(show(C.populated_cases(~Array<U32>,
      ~(xs => c => T.reduce_array(~U32, ~C.Trace, ~C.advance, xs, c)),
      ~(u => array_values()))))
#|[[1, 0, 0], [1, 1, 1], [1, 2, 12], [0, 3, 123], [0, 0, 0], [1, 0, 0]]
#|[[1, 0, 0], [1, 1, 1], [1, 2, 12], [0, 3, 123], [0, 0, 0], [1, 0, 0]]
#|[[1, 0, 0], [1, 1, 1], [1, 2, 12], [0, 3, 123], [0, 0, 0], [1, 0, 0]]
#|[[1, 0, 0], [1, 1, 1], [1, 2, 12], [0, 3, 123], [0, 0, 0], [1, 0, 0]]
#|[[1, 0, 0], [1, 1, 1], [1, 2, 12], [0, 4, 1234]]
