import Base
import ../xf.bend as X
import ../transduce_core.bend as T

def ranges() -> List<T.Range>:
  [T.range_between(0, 3), T.range_between(5, 7)]

def strings() -> List<String>:
  ["ab", "", "c"]

def range_sum() -> U32:
  X.transduce(X.cat(T.Range.adapter()), X.sum_rf(), 0, ranges())

def string_sum() -> U32:
  X.transduce(X.comp2(X.cat(T.String.adapter()),
    X.map(~Char, ~U32, ~Char.to_u32)), X.sum_rf(), 0, strings())

def range_take() -> U32:
  X.transduce(X.comp2(X.cat(T.Range.adapter()), X.take(~U32, 4n)),
    X.sum_rf(), 0, ranges())

def main() -> U32 & U32 & U32:
  (range_sum(), string_sum(), range_take())
#|(14, 294, 8)
