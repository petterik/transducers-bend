import Base
import ./rank2_static_typed.bend as S
import ./custom_shift.bend as Shift
import ../../transduce.bend as T

# A consumer value also carries checked static reducer code in its type.
# Its live field consumes the caller's initial value and produces the
# configuration the reducer requires. No runtime reducer record is needed.
type Rf<-B: Type, -R: Type, -Q: T.Reducer<B, R>, -Init: Type> is Type:
  Rf{prepare: Init -> T.Config(B, R, Q)}

def sum_rf() -> Rf<U32, U32, T.sum(), U32>:
  Rf{initial => initial}

def count_nat_rf() -> Rf<Nat, Nat, T.count(~Nat), Unit>:
  Rf{initial => initial}

def shifted(offset: U32) -> S.Xf<U32, U32,
  (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
    ~Shift.add, ~down))>:
  S.Xf{R => down => config => (offset, config)}

def taking_u32(n: Nat) -> S.Xf<U32, U32,
  (R => down => T.take(~U32, ~R, ~down))>:
  S.Xf{R => down => config => (n, config)}

def transduce(~A: Type, ~B: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  ~R: Type, ~Q: T.Reducer<B, R>, ~Init: Type,
  xf: S.Xf<A, B, P>, rf: Rf<B, R, Q, Init>,
  initial: Init, xs: List<A>) -> R:
  match xf rf:
    case S.Xf{configure} Rf{prepare}:
      config = configure(R, Q, prepare(initial))
      T.transduce(~T.over_list(~A, ~R, ~P(R, Q)), config, xs)

def main() -> U32:
  xf_sum = S.compose(U32, U32, U32,
    (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~down)),
    (R => down => T.take(~U32, ~R, ~down)),
    shifted(1), taking_u32(2n))
  sum = transduce(~U32, ~U32,
    ~(R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~T.take(~U32, ~R, ~down))),
    ~U32, ~T.sum(), ~U32,
    xf_sum, sum_rf(), 0, [1, 2, 3])
  xf_count = S.compose(U32, Nat, Nat,
    (R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat, ~down)),
    (R => down => T.take(~Nat, ~R, ~down)),
    S.mapped(), S.taking(2n))
  count = transduce(~U32, ~Nat,
    ~(R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat,
      ~T.take(~Nat, ~R, ~down))),
    ~Nat, ~T.count(~Nat), ~Unit,
    xf_count, count_nat_rf(), Unit{}, [1, 2, 3])
  (sum + U32.from_nat(count) : U32)
#|7
