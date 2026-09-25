import Base
import ./rank2_rf_values.bend as V
import ./rank2_static_typed.bend as S
import ./custom_shift.bend as Shift
import ../../transduce.bend as T

# The desired call shape for a List source. Xf and Rf are independently
# constructed affine values; their checked types determine all six omitted
# closed template arguments. Source protocol lookup is a separate problem.
def main() -> U32:
  xf_sum = S.compose(U32, U32, U32,
    (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~down)),
    (R => down => T.take(~U32, ~R, ~down)),
    V.shifted(1), V.taking_u32(2n))
  sum = V.transduce(xf_sum, V.sum_rf(), 0, [1, 2, 3])
  xf_count = S.compose(U32, Nat, Nat,
    (R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat, ~down)),
    (R => down => T.take(~Nat, ~R, ~down)),
    S.mapped(), S.taking(2n))
  count = V.transduce(xf_count, V.count_nat_rf(), Unit{}, [1, 2, 3])
  (sum + U32.from_nat(count) : U32)
#|7
