import Base
import ./rank2_static_provider.bend as P
import ./rank2_static_compose.bend as S
import ./custom_shift.bend as Shift
import ../../transduce.bend as T

def run_auto(~R: Type, ~down: T.Reducer<U32, R>,
  ~Code: @-Result: Type -> @-consumer: T.Reducer<U32, Result> ->
    T.Reducer<U32, Result>,
  xf: P.Xf<Code>, initial: T.Config(U32, R, down),
  xs: List<U32>) -> R:
  match xf:
    case P.Xf{configure}:
      config = configure(R, down, initial)
      T.transduce(~T.over_list(~U32, ~R, ~Code(R, down)), config, xs)

def pipeline(n: Nat) -> P.Xf<
  (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
    ~Shift.add, ~T.take(~U32, ~R, ~down)))>:
  S.compose(
    (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~down)),
    (R => down => T.take(~U32, ~R, ~down)),
    S.shifted(1), S.taking(n))

def main() -> List<U32>:
  [run_auto(~U32, ~T.sum(), pipeline(2n), 0, [1, 2, 3]),
   run_auto(~U32, ~T.sum(), pipeline(0n), 0, [1, 2, 3])]
#|[5, 0]
