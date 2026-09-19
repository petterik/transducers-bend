import Base
import ../transduce.bend as T

def inc(x: U32) -> U32:
  (x + 1 : U32)

# Equivalent to (transduce (map inc) + 0 (range 10)).
def example() -> U32:
  T.transduce(~T.over_range(~U32, ~T.map(~U32, ~U32, ~U32, ~inc, ~T.sum())), 0, T.range(10))

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(U32.show(example()))
    IO.print(Nat.show(T.transduce(~T.over_range(~Nat, ~T.count(~U32)), Unit{}, T.range(10))))
    IO.print(Nat.show(T.transduce(~T.over_string(~Nat, ~T.count(~Char)), Unit{}, "abc")))
    IO.print(Nat.show(T.transduce(~T.over_string(~Nat, ~T.count(~Char)), Unit{}, "")))
    IO.print(Nat.show(T.transduce(~T.over_string(~Nat, ~T.take(~Char, ~Nat, ~T.count(~Char))), (0n, Unit{}), "abc")))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~T.over_string(~List<U32>, ~T.map(~Char, ~U32, ~List<U32>, ~Char.to_u32, ~T.into_list(~U32))), Unit{}, "aé")))
#|55
#|10
#|3
#|0
#|0
#|[97, 233]
