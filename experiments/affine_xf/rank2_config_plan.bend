import Base
import ./rank2_probe.bend as P
import ../../transduce.bend as T

# The plan stores the downstream configuration at its dependent type. The
# constructor is formed where the code is closed; run carries it opaquely.
type Plan<-code: @-R: Type -> T.Reducer<U32, R> -> T.Reducer<U32, R>> is Type:
  Plan{limit: Nat, downstream: T.Config(U32, U32, code(U32, T.sum()))}

def run(~code: @-R: Type -> T.Reducer<U32, R> -> T.Reducer<U32, R>,
  plan: Plan<code>, xs: List<U32>) -> U32:
  match plan:
    case Plan{limit, downstream}:
      T.transduce(~T.over_list(~U32, ~U32,
        ~T.take(~U32, ~U32, ~code(U32, T.sum()))),
        (limit, downstream), xs)

def main() -> U32:
  plan : Plan<(R => down => P.map_apply(~U32, ~U32, ~P.plus_one, R, down))> =
    Plan{2n, 0}
  run(~(R => down => P.map_apply(~U32, ~U32, ~P.plus_one, R, down)),
    plan, [1, 2, 3])
#|5
