import Base
import ./rank2_static_typed.bend as S
import ../../transduce.bend as T

# All leading static arguments are inferred from xf's checked type. The
# consumer is fixed here so this does not yet prove transduce(xf, rf,...).
def run_count(~A: Type, ~B: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> ->
    T.Reducer<A, R>,
  xf: S.Xf<A, B, P>, xs: List<A>) -> Nat:
  match xf:
    case S.Xf{configure}:
      config = configure(Nat, T.count(~B), Unit{})
      T.transduce(~T.over_list(~A, ~Nat,
        ~P(Nat, T.count(~B))), config, xs)

def main() -> Nat:
  xf = S.compose(U32, Nat, Nat,
    (R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat, ~down)),
    (R => down => T.take(~Nat, ~R, ~down)),
    S.mapped(), S.taking(2n))
  run_count(xf, [1, 2, 3])
#|2n
