import Base
import ./rank2_probe.bend as P
import ../../transduce.bend as T

# An ordinary call is not an inert alias: removing its runtime evaluation
# could change the program, even if its result were usable at compile time.
def main() -> U32:
  xf = P.map_xf(~U32, ~U32, ~P.plus_one)
  T.transduce(~T.over_list(~U32, ~U32,
    ~P.apply_xf(U32, U32, U32, xf, T.sum())),
    0, [1, 2, 3])
