import Base
import ./rank2_probe.bend as P
import ../../transduce.bend as T

# Expected rejection: Config cannot reduce through the opaque code index.
# This deliberately tests a general reducer transformer, unlike the simple
# map function in type_indexed_plan.bend.
type Plan<-code: @-R: Type -> T.Reducer<U32, R> -> T.Reducer<U32, R>> is Type:
  Plan{limit: Nat}

def make(~code: @-R: Type -> T.Reducer<U32, R> -> T.Reducer<U32, R>,
  limit: Nat) -> Plan<code>:
  Plan{limit}

def run(~code: @-R: Type -> T.Reducer<U32, R> -> T.Reducer<U32, R>,
  plan: Plan<code>, xs: List<U32>) -> U32:
  match plan:
    case Plan{limit}:
      T.transduce(~T.over_list(~U32, ~U32,
        ~T.take(~U32, ~U32, ~code(U32, T.sum()))),
        (limit, 0), xs)

def main() -> U32:
  plan = make(~(R => down => P.map_apply(~U32, ~U32, ~P.plus_one, R, down)), 2n)
  run(~(R => down => P.map_apply(~U32, ~U32, ~P.plus_one, R, down)),
    plan, [1, 2, 3])
#|5
