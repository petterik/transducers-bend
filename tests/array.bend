import Base
import ../transduce.bend as T

type Quad is Data:
  Quad{left: U32, right: U32}

def values() -> Array<Quad>:
  a = Array.set(Quad, [Quad{0, 0} : Quad*4n], 0, Quad{1, 11})
  b = Array.set(Quad, a, 1, Quad{5, 15})
  c = Array.set(Quad, b, 2, Quad{3, 13})
  Array.set(Quad, c, 3, Quad{7, 17})

def sum_values(x: Quad) -> U32:
  match x:
    case Quad{left, right}:
      (left + right : U32)

def pair(x: Quad) -> List<U32>:
  match x:
    case Quad{left, right}:
      [left, right]

def maybe_pair(x: Quad) -> List<U32>:
  match x:
    case Quad{0, 0}:
      []
    case Quad{left, right}:
      [left, right]

def with_empty() -> Array<Quad>:
  Array.set(Quad, [Quad{0, 0} : Quad*2n], 1, Quad{2, 3})

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(U32.show(T.transduce(~T.over_array(~Quad, ~U32,
      ~T.map(~Quad, ~U32, ~U32, ~sum_values, ~T.sum())), 0, values())))
    IO.print(U32.show(T.transduce(~T.over_array(~Quad, ~U32,
      ~T.map(~Quad, ~List<U32>, ~U32, ~pair,
        ~T.cat(~U32, ~U32, ~T.sum()))), 0, values())))
    IO.print(U32.show(T.transduce(~T.over_array(~Quad, ~U32,
      ~T.map(~Quad, ~List<U32>, ~U32, ~pair,
        ~T.cat(~U32, ~U32, ~T.sum()))), 0, values())))
    IO.print(U32.show(T.transduce(~T.over_array(~Quad, ~U32,
      ~T.map(~Quad, ~List<U32>, ~U32, ~pair,
        ~T.cat(~U32, ~U32,
          ~T.take(~U32, ~U32, ~T.sum())))), (3n, 0), values())))
    IO.print(U32.show(T.transduce(~T.over_array(~Quad, ~U32,
      ~T.map(~Quad, ~List<U32>, ~U32, ~maybe_pair,
        ~T.cat(~U32, ~U32, ~T.sum()))), 0, with_empty())))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~T.over_array(~Quad, ~List<U32>,
        ~T.map(~Quad, ~List<U32>, ~List<U32>, ~pair,
          ~T.cat(~U32, ~List<U32>, ~T.into_list(~U32)))),
        Unit{}, values())))
#|72
#|72
#|72
#|17
#|5
#|[1, 11, 5, 15, 3, 13, 7, 17]
