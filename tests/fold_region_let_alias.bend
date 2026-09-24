import Base

def plus_one(x: U32) -> U32:
  (x + 1 : U32)

def sum_values(acc: U32, value: U32) -> U32:
  (acc + value : U32)

def mapped_sum_let(xs: List<U32>) -> U32:
  values = List.map(~U32, ~U32, ~plus_one, xs)
  List.foldl(~&1, ~U32, ~U32, ~sum_values, values, 0)

def main() -> Bool:
  U32.is_eq(mapped_sum_let([1, 2, 3, 4]), 14)

#|True{}
