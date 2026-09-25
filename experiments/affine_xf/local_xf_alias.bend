import Base
import ./rank2_probe.bend as P
import ../../transduce.bend as T

# The local name carries a statically known transformer. This is still an
# explicit ~ recipe at the List driver, not the proposed ordinary-value API.
def main() -> U32:
  xf : P.Xf<U32, U32> = P.Xf{R => down => P.map_apply(~U32, ~U32, ~P.plus_one, R, down)}
  T.transduce(~T.over_list(~U32, ~U32,
    ~P.apply_xf(U32, U32, U32, xf, T.sum())),
    0, [1, 2, 3])
#|9
