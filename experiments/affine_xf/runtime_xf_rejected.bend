import Base
import ./rank2_probe.bend as P
import ../../transduce.bend as T

# This is the desired ordinary-value API boundary. Current Bend requires the
# reducer supplied to over_list to be closed template syntax, so xf cannot be
# an affine runtime parameter here.
def run(xf: P.Xf<U32, U32>, xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~P.apply_xf(U32, U32, U32, xf, T.sum())),
    0, xs)

def main() -> U32:
  run(P.map_xf(~U32, ~U32, ~P.plus_one), [1, 2, 3])
