import Base
import ../transduce.bend as T

def inc1(x: U32) -> U32:
  (x + 1 : U32)
def inc2(x: U32) -> U32:
  (x + 2 : U32)
def inc3(x: U32) -> U32:
  (x + 3 : U32)
def pipeline() -> T.Reducer<U32, U32>:
  T.map(~U32, ~U32, ~U32, ~inc1,
    ~T.map(~U32, ~U32, ~U32, ~inc2,
      ~T.map(~U32, ~U32, ~U32, ~inc3, ~T.sum())))
def run(xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32, ~pipeline()), 0, xs)
def main() -> List<U32>:
  [run([]), run([0]), run([4294967290]), run([4294967295]),
    run([0, 1, 2]), T.transduce(~T.over_range(~U32, ~pipeline()), 0, T.range(10))]
#|[0, 6, 0, 5, 21, 105]
