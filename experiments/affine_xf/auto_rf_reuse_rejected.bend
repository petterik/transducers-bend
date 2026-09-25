import Base
import ./rank2_rf_values.bend as V
import ./rank2_static_typed.bend as S
import ./custom_shift.bend as Shift
import ../../transduce.bend as T

def pipeline() -> S.Xf<U32, U32,
  (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
    ~Shift.add, ~T.take(~U32, ~R, ~down)))>:
  S.compose(U32, U32, U32,
    (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~down)),
    (R => down => T.take(~U32, ~R, ~down)),
    V.shifted(1), V.taking_u32(2n))

def main() -> U32:
  rf = V.sum_rf()
  first = V.transduce(pipeline(), rf, 0, [1, 2, 3])
  second = V.transduce(pipeline(), rf, 0, [1, 2, 3])
  (first + second : U32)
