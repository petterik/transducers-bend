import Base
import ./rank2_rf_values.bend as V
import ./rank2_static_typed.bend as S
import ../../transduce.bend as T

def main() -> U32:
  xf = S.compose(U32, Nat, Nat,
    (R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat, ~down)),
    (R => down => T.take(~Nat, ~R, ~down)),
    S.mapped(), S.taking(2n))
  V.transduce(xf, V.sum_rf(), 0, [1, 2, 3])
