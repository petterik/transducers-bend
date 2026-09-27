import Base
import ../xf.bend as X
import ../vec.bend as Vec

def numbers() -> List<U32>:
  [1, 2, 3]

def ordered() -> Vec.Vec<U32>:
  X.into(Vec.empty(~U32, 0),
    X.map(~U32, ~U32, ~U32.inc), numbers())

def weighted(index: Nat, value: U32) -> U32:
  U32.mul(U32.inc(U32.from_nat(index)), value)

def main() -> U32:
  X.transduce(X.map_indexed(~U32, ~U32, ~weighted),
    X.sum_rf(), 0, ordered())
#|20
