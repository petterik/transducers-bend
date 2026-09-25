import Base
import ../../transduce.bend as T
import ./rank2_probe.bend as P

# The stage code stays closed; the actual limit is a runtime configuration.
def run(n: Nat, xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.take(~U32, ~U32, ~T.map(~U32, ~U32, ~U32,
      ~P.plus_one, ~T.sum()))),
    (n, 0), xs)

def main() -> U32:
  run(2n, [1, 2, 3])
#|5
