import Base
import ./rank2_static_typed.bend as S
import ../../transduce.bend as T

# The isolated checker candidate should infer A, B, and closed provider P
# from the checked type of the first runtime argument, xf. The reducer stays
# an explicit closed template argument in this first step.
def main() -> Nat:
  xf = S.compose(U32, Nat, Nat,
    (R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat, ~down)),
    (R => down => T.take(~Nat, ~R, ~down)),
    S.mapped(), S.taking(2n))
  S.run(~?AUTO, ~?AUTO, ~?AUTO,
    ~Nat, ~T.count(~Nat), xf, Unit{}, [1, 2, 3])
#|2n
