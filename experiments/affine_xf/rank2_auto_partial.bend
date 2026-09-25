import Base
import ./rank2_static_typed.bend as S
import ../../transduce.bend as T

# With an explicit downstream reducer first, the parser can fill the omitted
# trailing static arguments. The checker infers A and P from xf's type.
def run_auto(~R: Type, ~B: Type, ~down: T.Reducer<B, R>,
  ~A: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  xf: S.Xf<A, B, P>, initial: T.Config(B, R, down),
  xs: List<A>) -> R:
  match xf:
    case S.Xf{configure}:
      config = configure(R, down, initial)
      T.transduce(~T.over_list(~A, ~R, ~P(R, down)), config, xs)

def main() -> Nat:
  xf = S.compose(U32, Nat, Nat,
    (R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat, ~down)),
    (R => down => T.take(~Nat, ~R, ~down)),
    S.mapped(), S.taking(2n))
  run_auto(~Nat, ~Nat, ~T.count(~Nat), xf, Unit{}, [1, 2, 3])
#|2n
