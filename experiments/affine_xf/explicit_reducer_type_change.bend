import Base
import ./explicit_reducer_types.bend as E
import ../../transduce.bend as T

def sum_nat() -> E.R2<Nat, Nat, Nat, Nat>:
  E.R2{n => T.Continue{n}, s => x => T.Continue{Nat.add(s, x)}, s => s}

def main() -> Nat:
  xf : E.Xf<U32, Nat, U32.to_nat> = E.Xf{2n}
  E.run(~U32, ~Nat, ~Nat, ~Nat, ~Nat,
    ~U32.to_nat, ~sum_nat(), xf, 0n, [1, 2, 3])
#|3
