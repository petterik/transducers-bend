import Base
import ../xf.bend as X
import ../vec.bend as Vec

def numbers() -> List<U32>:
  [1, 2, 3]

def fragment(x: U32) -> Vec.Vec<U32>:
  +x = x
  Vec.push(~U32, Vec.push(~U32, Vec.empty(~U32, 0), x),
    U32.add(x, 10))

def fragments() -> List<Vec.Vec<U32>>:
  [fragment(1), fragment(2)]

def flattened_sum() -> U32:
  X.transduce(X.cat(Vec.Vec.adapter(~U32)), X.sum_rf(), 0,
    fragments())

def mapped_sum() -> U32:
  X.transduce(X.comp2(X.map(~U32, ~Vec.Vec<U32>, ~fragment),
    X.cat(Vec.Vec.adapter(~U32))), X.sum_rf(), 0, numbers())

def stopped_sum() -> U32:
  X.transduce(X.comp2(X.cat(Vec.Vec.adapter(~U32)),
    X.take(~U32, 3n)), X.sum_rf(), 0, fragments())

def collected() -> Vec.Vec<U32>:
  X.into(Vec.empty(~U32, 0),
    X.comp2(X.map(~U32, ~Vec.Vec<U32>, ~fragment),
      X.cat(Vec.Vec.adapter(~U32))), numbers())

def main() -> U32 & U32 & U32 & U32:
  (flattened_sum(), mapped_sum(), stopped_sum(),
    X.transduce(X.map(~U32, ~U32, ~U32.inc),
      X.sum_rf(), 0, collected()))
#|(26, 42, 14, 48)
