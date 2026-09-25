import Base
import ./rank2_probe.bend as P
import ../../transduce.bend as T

# The static transformation is an erased index. The value owns only runtime
# configuration. The explicit ~f at the consumer is the unresolved API sugar.
type Plan<-f: U32 -> U32> is Type:
  Plan{limit: Nat}

def make(~f: U32 -> U32, limit: Nat) -> Plan<f>:
  Plan{limit}

def run(~f: U32 -> U32, plan: Plan<f>, xs: List<U32>) -> U32:
  match plan:
    case Plan{limit}:
      T.transduce(~T.over_list(~U32, ~U32,
        ~T.take(~U32, ~U32, ~T.map(~U32, ~U32, ~U32,
          ~f, ~T.sum()))),
        (limit, 0), xs)

def execute(limit: Nat, xs: List<U32>) -> U32:
  plan = make(~P.plus_one, limit)
  run(~P.plus_one, plan, xs)

def main() -> U32:
  execute(2n, [1, 2, 3])
#|5
