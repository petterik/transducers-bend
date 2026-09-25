import Base
import ../xf.bend as X

def small(x: U32) -> Bool:
  U32.is_lt(x, 4)

def numbers() -> List<U32>:
  [1, 2, 3, 4, 5]

def groups() -> List<List<U32>>:
  []

def flush_partial() -> List<List<U32>>:
  X.into(groups(), X.comp2(X.take_while(~U32, ~small),
    X.partition_all(~U32, 2n)), numbers())

def stop_downstream() -> List<List<U32>>:
  X.into(groups(), X.comp3(X.take_while(~U32, ~small),
    X.partition_all(~U32, 2n), X.take(~List<U32>, 1n)), numbers())

def stop_before_start() -> List<List<U32>>:
  X.into(groups(), X.comp3(X.drop(~U32, 2n),
    X.partition_all(~U32, 2n), X.take(~List<U32>, 0n)), numbers())

def drop_then_flush() -> List<List<U32>>:
  X.into(groups(), X.comp2(X.drop_while(~U32, ~small),
    X.partition_all(~U32, 3n)), numbers())

def main() -> List<List<U32>> & List<List<U32>> &
  List<List<U32>> & List<List<U32>>:
  (flush_partial(), stop_downstream(), stop_before_start(),
    drop_then_flush())
#|([[3], [1, 2]], [[1, 2]], [], [[4, 5]])
