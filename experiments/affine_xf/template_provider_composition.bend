import Base
import ./custom_shift.bend as Shift
import ../../transduce.bend as T

# Closed lambdas can forward their own binder into a template call. Their
# ordinary function composition is checked, then the isolated static pass
# may erase the resulting reducer plumbing before the source loop.
def compose_provider(
  ~outer: T.Reducer<U32, U32> -> T.Reducer<U32, U32>,
  ~inner: T.Reducer<U32, U32> -> T.Reducer<U32, U32>,
  ~down: T.Reducer<U32, U32>) -> T.Reducer<U32, U32>:
  outer(inner(down))

def run(n: Nat, offset: U32, xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~compose_provider(
      ~(down => T.map_with(~U32, ~U32, ~U32, ~U32,
        ~Shift.add, ~down)),
      ~(down => T.take(~U32, ~U32, ~down)),
      ~T.sum())),
    (offset, (n, 0)), xs)

def main() -> List<U32>:
  [run(0n, 1, [1, 2, 3]),
   run(1n, 1, [1, 2, 3]),
   run(2n, 1, [1, 2, 3]),
   run(4n, 1, [1, 2, 3])]
#|[0, 2, 5, 9]
