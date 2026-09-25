import Base
import ../xf.bend as X

def parity(x: U32) -> U32:
  U32.mod(x, 2)

def numbers() -> List<U32>:
  [1, 3, 2, 4, 5]

def empty() -> List<U32>:
  []

def singleton() -> List<U32>:
  [9]

def empty_groups() -> List<List<U32>>:
  []

def groups() -> List<List<U32>>:
  X.into(empty_groups(),
    X.partition_by(~U32, ~U32, ~parity, ~U32.is_eq), numbers())

def take_group() -> List<List<U32>>:
  X.into(empty_groups(),
    X.comp2(X.partition_by(~U32, ~U32, ~parity, ~U32.is_eq),
      X.take(~List<U32>, 1n)), numbers())

def take_input() -> List<List<U32>>:
  X.into(empty_groups(),
    X.comp2(X.take(~U32, 3n),
      X.partition_by(~U32, ~U32, ~parity, ~U32.is_eq)), numbers())

def main() -> List<List<U32>> & List<List<U32>> & List<List<U32>> &
  List<List<U32>> & List<List<U32>> & List<List<U32>>:
  (groups(), take_group(), take_input(),
   X.into(empty_groups(),
     X.partition_by(~U32, ~U32, ~parity, ~U32.is_eq), empty()),
   X.into(empty_groups(),
     X.partition_by(~U32, ~U32, ~parity, ~U32.is_eq), singleton()),
   X.into(empty_groups(),
     X.comp2(X.partition_by(~U32, ~U32, ~parity, ~U32.is_eq),
       X.take(~List<U32>, 0n)), numbers()))
#|([[5], [2, 4], [1, 3]], [[1, 3]], [[2], [1, 3]], [], [[9]], [])
