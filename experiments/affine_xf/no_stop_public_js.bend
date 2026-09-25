import Base
import ../../xf.bend as X
import ../../xf_legacy.bend as Old

def source(depth: Nat) -> Array<U32>:
  Array.new(U32, depth, 1)

def direct(xs: Array<U32>, state: U32) -> U32:
  match xs:
    case ALeaf{x}: (state + U32.inc(x) : U32)
    case ANode{left, right}:
      direct(right, direct(left, state))

def total(xs: Array<U32>) -> U32:
  X.transduce(X.map(~U32, ~U32, ~U32.inc), X.sum_rf(), 0, xs)

def legacy(xs: Array<U32>) -> U32:
  Old.transduce(Old.map(~U32, ~U32, ~U32.inc), Old.sum_rf(), 0, xs)

def stopping(xs: Array<U32>) -> U32:
  X.transduce(X.comp2(
    X.map(~U32, ~U32, ~U32.inc), X.take(~U32, 131072n)),
    X.sum_rf(), 0, xs)

def stopping_legacy(xs: Array<U32>) -> U32:
  Old.transduce(Old.comp2(
    Old.map(~U32, ~U32, ~U32.inc), Old.take(~U32, 131072n)),
    Old.sum_rf(), 0, xs)
