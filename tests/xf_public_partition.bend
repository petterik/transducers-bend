import Base
import ../xf.bend as X

def five() -> List<U32>:
  [1, 2, 3, 4, 5]

def empty_groups() -> List<List<U32>>:
  []

def groups() -> List<List<U32>>:
  X.into(empty_groups(), X.partition_all(~U32, 2n), five())

def zero() -> List<List<U32>>:
  X.into(empty_groups(), X.partition_all(~U32, 0n), five())

def take_after() -> List<List<U32>>:
  X.into(empty_groups(), X.comp2(
    X.partition_all(~U32, 2n), X.take(~List<U32>, 1n)), five())

def take_before() -> List<List<U32>>:
  X.into(empty_groups(), X.comp2(
    X.take(~U32, 3n), X.partition_all(~U32, 2n)), five())

def main() -> List<List<U32>> & List<List<U32>> &
  List<List<U32>> & List<List<U32>>:
  (groups(), zero(), take_after(), take_before())
#|([[5], [3, 4], [1, 2]], [], [[1, 2]], [[3], [1, 2]])
