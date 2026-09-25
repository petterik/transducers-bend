import Base
import ./custom_shift.bend as Shift
import ../../transduce.bend as T

# Probe whether a reusable-looking rank-2 run field could hide the provider
# without a static type index or explicit template argument at the call site.
type Runner is Type:
  Runner{run: @-R: Type -> @-down: T.Reducer<U32, R> ->
    T.Config(U32, R, down) -> List<U32> -> R}

def shift_take(n: Nat, offset: U32) -> Runner:
  Runner{R => down => initial => xs =>
    T.transduce(~T.over_list(~U32, ~R,
      ~T.map_with(~U32, ~U32, ~R, ~U32, ~Shift.add,
        ~T.take(~U32, ~R, ~down))),
      (offset, (n, initial)), xs)}

def transduce(runner: Runner, xs: List<U32>) -> U32:
  match runner:
    case Runner{run}:
      run(U32, T.sum(), 0, xs)

def main() -> U32:
  transduce(shift_take(2n, 1), [1, 2, 3])
