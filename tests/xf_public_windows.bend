import Base
import ../xf.bend as X
import ./support/vec_pair_source.bend as Pair

def numbers() -> List<U32>:
  [1, 2, 3]

def empty() -> List<U32>:
  []

def empty_groups() -> List<List<U32>>:
  []

def window(width: Nat) -> List<List<U32>>:
  X.into(empty_groups(), X.windows(~U32, width), numbers())

def take_window() -> List<List<U32>>:
  X.into(empty_groups(),
    X.comp2(X.windows(~U32, 2n), X.take(~List<U32>, 1n)), numbers())

def take_input() -> List<List<U32>>:
  X.into(empty_groups(),
    X.comp2(X.take(~U32, 2n), X.windows(~U32, 2n)), numbers())

def main() -> List<List<U32>> & List<List<U32>> & List<List<U32>> &
  List<List<U32>> & List<List<U32>> & List<List<U32>> &
  List<List<U32>> & List<List<U32>> & List<List<U32>> &
  List<List<U32>>:
  (window(0n), window(1n), window(2n), window(3n), window(4n),
   X.into(empty_groups(), X.windows(~U32, 2n), empty()),
   take_window(), take_input(),
   X.into(empty_groups(), X.windows(~U32, 2n), Pair.example()),
   X.into(empty_groups(), X.windows(~U32, 2n),
     Array.new(U32, 2n, 7)))
#|([], [[3], [2], [1]], [[2, 3], [1, 2]], [[1, 2, 3]], [], [], [[1, 2]], [[1, 2]], [[3, 4]], [[7, 7], [7, 7], [7, 7]])
