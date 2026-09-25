import Base

def plus_one(x: U32) -> U32:
  (x + 1 : U32)

def mapped_values(xs: +List<U32>) -> +List<U32>:
  match xs:
    case Nil{}:
      Nil{}
    case h <> t:
      plus_one(h) <> mapped_values(t)

def is_even(x: U32) -> Bool:
  U32.is_eq(U32.mod(x, 2), 0)

def retain_step(acc: List<U32>, value: U32) -> List<U32>:
  value <> acc

def hash_step(acc: U32, value: U32) -> U32:
  ((acc * 33 : U32) + value : U32)

def retained_hash(xs: +List<U32>) -> U32:
  retained = List.foldl(~&2, ~U32, ~List<U32>, ~retain_step,
    List.filter(~U32, ~is_even, mapped_values(xs)), Nil{})
  List.foldl(~&1, ~U32, ~U32, ~hash_step, retained, 5381)

def main() -> Bool:
  U32.is_eq(retained_hash([0, 1, 2, 3, 4, 5]), 193383665)
#|True{}
