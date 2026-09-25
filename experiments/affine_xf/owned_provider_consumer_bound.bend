import Base
import ./custom_shift.bend as Shift
import ../../transduce.bend as T

# A narrow bridge: put the exact closed provider in an erased type index and
# its owned configuration in the value. This version is deliberately tied to
# the sum consumer, so it is a checker feasibility probe, not the target Xf.
type OwnedXf<-P: T.Reducer<U32, U32> -> T.Reducer<U32, U32>> is Type:
  OwnedXf{config: T.Config(U32, U32, P(T.sum()))}

def run(~P: T.Reducer<U32, U32> -> T.Reducer<U32, U32>,
  xf: OwnedXf<P>, xs: List<U32>) -> U32:
  match xf:
    case OwnedXf{config}:
      T.transduce(~T.over_list(~U32, ~U32, ~P(T.sum())), config, xs)

def make(n: Nat, offset: U32) -> OwnedXf<
  (down => T.map_with(~U32, ~U32, ~U32, ~U32, ~Shift.add,
    ~T.take(~U32, ~U32, ~down)))>:
  OwnedXf{(offset, (n, 0))}

def main() -> U32:
  run(~(down => T.map_with(~U32, ~U32, ~U32, ~U32, ~Shift.add,
    ~T.take(~U32, ~U32, ~down))), make(2n, 1), [1, 2, 3])
#|5
