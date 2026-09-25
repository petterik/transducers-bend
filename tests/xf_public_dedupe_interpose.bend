import Base
import ../xf.bend as X

def same_parity(a: U32, b: U32) -> Bool:
  U32.is_eq(U32.mod(a, 2), U32.mod(b, 2))

def numbers() -> List<U32>:
  [1, 1, 2, 2, 1, 1, 3]

def parity_numbers() -> List<U32>:
  [1, 3, 2, 4, 1]

def short() -> List<U32>:
  [1, 2, 3]

def empty() -> List<U32>:
  []

def singleton() -> List<U32>:
  [4]

def deduped() -> List<U32>:
  X.into(empty(), X.dedupe(~U32, ~U32.is_eq), numbers())

def separated() -> List<U32>:
  X.into(empty(), X.interpose(~U32, 9), short())

def main() -> List<U32> & List<U32> & List<U32> &
  U32 & U32 & U32 & U32 & U32 & U32 & U32:
  (deduped(),
   X.into(empty(), X.dedupe(~U32, ~same_parity), parity_numbers()),
   separated(),
   X.transduce(X.dedupe(~U32, ~U32.is_eq), X.sum_rf(), 0, numbers()),
   X.transduce(X.interpose(~U32, 9), X.sum_rf(), 0, short()),
   X.transduce(X.interpose(~U32, 9), X.sum_rf(), 0, empty()),
   X.transduce(X.interpose(~U32, 9), X.sum_rf(), 0, singleton()),
   X.transduce(X.comp2(X.interpose(~U32, 9), X.take(~U32, 2n)),
     X.sum_rf(), 0, short()),
   X.transduce(X.comp2(X.take(~U32, 2n), X.interpose(~U32, 9)),
     X.sum_rf(), 0, short()),
   X.transduce(X.comp2(X.interpose(~U32, 9), X.take(~U32, 0n)),
     X.sum_rf(), 0, short()))
#|([3, 1, 2, 1], [1, 2, 1], [3, 9, 2, 9, 1], 7, 24, 0, 4, 10, 12, 0)
