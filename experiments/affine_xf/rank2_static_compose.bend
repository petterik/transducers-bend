import Base
import ./rank2_static_provider.bend as P
import ./custom_shift.bend as Shift
import ../../transduce.bend as T

def shifted(offset: U32) -> P.Xf<
  (R => down => T.map_with(~U32, ~U32, ~R, ~U32, ~Shift.add, ~down))>:
  P.Xf{R => down => config => (offset, config)}

def taking(n: Nat) -> P.Xf<
  (R => down => T.take(~U32, ~R, ~down))>:
  P.Xf{R => down => config => (n, config)}

# This is open to any two stage providers of the same input/output type.
# Composition owns each stage value and moves each configure closure once.
def compose(
  -Outer: @-R: Type -> @-down: T.Reducer<U32, R> -> T.Reducer<U32, R>,
  -Inner: @-R: Type -> @-down: T.Reducer<U32, R> -> T.Reducer<U32, R>,
  xf: P.Xf<Outer>, xg: P.Xf<Inner>) ->
  P.Xf<(R => down => Outer(R, Inner(R, down)))>:
  match xf xg:
    case P.Xf{configureF} P.Xf{configureG}:
      P.Xf{R => down => config =>
        configureF(R, Inner(R, down), configureG(R, down, config))}

def main() -> U32:
  xf_sum = compose(
    (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~down)),
    (R => down => T.take(~U32, ~R, ~down)),
    shifted(1), taking(2n))
  sum = P.run(~(R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~T.take(~U32, ~R, ~down))),
    ~U32, ~T.sum(), xf_sum, 0, [1, 2, 3])
  xf_count = compose(
    (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~down)),
    (R => down => T.take(~U32, ~R, ~down)),
    shifted(1), taking(2n))
  count = P.run(~(R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~T.take(~U32, ~R, ~down))),
    ~Nat, ~T.count(~U32), xf_count, Unit{}, [1, 2, 3])
  (sum + U32.from_nat(count) : U32)
#|7
