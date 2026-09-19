import Base
import ../transduce.bend as T

def inc(x: U32) -> U32:
  (x + 1 : U32)

def above(threshold: U32, x: U32) -> Bool:
  U32.is_gt(x, threshold)

def pipeline() -> T.Reducer<U32, U32>:
  T.map(~U32, ~U32, ~U32, ~inc,
    ~T.filter(~U32, ~U32, ~U32, ~above,
      ~T.take(~U32, ~U32, ~T.sum())))

def run(xs: List<U32>, threshold: U32, n: Nat) -> U32:
  T.transduce(~T.over_list(~U32, ~U32, ~pipeline()), (threshold, (n, 0)), xs)

def main() -> List<U32>:
  [run([1, 2, 3, 4, 5], 2, 2n), run([1, 2, 3], 2, 0n), run([], 2, 2n), run([1, 2, 3], 99, 2n), run([1, 2, 3], 2, 9n)]
#|[7, 0, 0, 0, 7]
