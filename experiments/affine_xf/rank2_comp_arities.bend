import Base
import ./rank2_rf_values.bend as V
import ./rank2_static_typed.bend as S

def main() -> U32 & List<Nat> & U32 & U32 & U32:
  two = V.transduce(V.comp2(V.shifted(1), V.taking_u32(2n)),
    V.sum_rf(), 0, [1, 2, 3])
  three = V.into([], V.comp3(V.shifted(1),
    V.taking_u32(2n), S.mapped()), [1, 2, 3])
  four = V.transduce(V.comp4(V.shifted(1), V.taking_u32(2n),
    V.shifted(3), V.shifted(4)), V.sum_rf(), 0, [1, 2, 3])
  five = V.transduce(V.comp5(V.shifted(1), V.taking_u32(2n),
    V.shifted(3), V.shifted(4), V.shifted(5)),
    V.sum_rf(), 0, [1, 2, 3])
  ten = V.transduce(V.comp2(
    V.comp5(V.shifted(1), V.shifted(1), V.shifted(1),
      V.shifted(1), V.shifted(1)),
    V.comp5(V.shifted(1), V.shifted(1), V.shifted(1),
      V.shifted(1), V.shifted(1))),
    V.sum_rf(), 0, [1, 2])
  (two, three, four, five, ten)
#|(5, [3n, 2n], 19, 29, 23)
