import Base
import ../xf.bend as X
import ../examples/branch_public.bend as B

def sum() -> U32:
  X.transduce(X.map(~U32, ~U32, ~U32.inc), X.sum_rf(), 0,
    B.build(3n, 1))

def first_three() -> U32:
  X.transduce(X.comp2(X.map(~U32, ~U32, ~U32.inc),
    X.take(~U32, 3n)), X.sum_rf(), 0, B.build(3n, 1))

def zero() -> U32:
  X.transduce(X.take(~U32, 0n), X.sum_rf(), 0, B.build(3n, 1))

def empty_u32() -> List<U32>:
  []

def retained() -> List<U32>:
  X.into(empty_u32(), X.map(~U32, ~U32, ~U32.inc), B.build(3n, 1))

def main() -> U32 & U32 & U32 & List<U32>:
  (sum(), first_three(), zero(), retained())
#|(100, 30, 0, [16, 15, 14, 13, 12, 11, 10, 9])
