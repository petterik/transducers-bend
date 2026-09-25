import Base
import ./rank2_rf_values.bend as V
import ./rank2_static_typed.bend as S

def main() -> List<U32> & U32 & List<Nat> & List<U32>:
  xf = V.compose(V.shifted(1), V.taking_u32(2n))
  inserted = V.into([9], xf, [1, 2, 3])
  sum = V.transduce(V.compose(V.shifted(1), V.taking_u32(2n)),
    V.sum_rf(), 0, [1, 2, 3])
  changed = V.into([], V.compose(S.mapped(), S.taking(2n)), [1, 2, 3])
  zero = V.into([9], V.taking_u32(0n), [1, 2, 3])
  (inserted, sum, changed, zero)
#|([3, 2, 9], 5, [2n, 1n], [9])
