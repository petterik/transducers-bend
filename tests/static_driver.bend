import Base
import ../transduce.bend as T

def keep(+x: U32) -> Bool:
  U32.is_gt(x, 1)

def keep_unit(local: Unit, x: U32) -> Bool:
  keep(x)

def pipeline() -> T.Reducer<U32, U32>:
  T.filter(~U32, ~U32, ~Unit, ~keep_unit,
    ~T.take(~U32, ~U32, ~T.sum()))

def run(xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32, ~pipeline()), (Unit{}, (2n, 0)), xs)

def main() -> List<U32>:
  [run([]), run([0, 1, 2, 3]), run([4, 5, 6])]
#|[0, 5, 9]
