import Base
import ../xf.bend as X
import ../transduce_core.bend as T

def inc(x: U32) -> U32:
  U32.inc(x)

def even(x: U32) -> Bool:
  U32.is_zero(U32.mod(x, 2))

def three() -> List<U32>:
  [1, 2, 3]

def empty_u32() -> List<U32>:
  []

def total_array() -> U32:
  X.transduce(X.comp2(X.map(~U32, ~U32, ~inc),
    X.filter(~U32, ~even)), X.sum_rf(), 0,
    Array.new(U32, 3n, 1))

def zero_array() -> U32:
  X.transduce(X.take(~U32, 0n), X.sum_rf(), 0,
    Array.new(U32, 3n, 1))

def from_list() -> U32:
  X.transduce(X.map(~U32, ~U32, ~inc), X.sum_rf(), 0,
    three())

def from_range() -> U32:
  X.transduce(X.map(~U32, ~U32, ~inc), X.sum_rf(), 0,
    T.range_between(0, 3))

def from_string() -> U32:
  X.transduce(X.map(~Char, ~U32, ~Char.to_u32), X.sum_rf(), 0,
    T.String.source("ab"))

def into_list() -> List<U32>:
  X.into(empty_u32(), X.map(~U32, ~U32, ~inc), three())

def main() -> U32 & U32 & U32 & U32 & U32 & List<U32>:
  (total_array(), zero_array(), from_list(), from_range(),
    from_string(), into_list())
#|(16, 0, 9, 6, 195, [4, 3, 2])
