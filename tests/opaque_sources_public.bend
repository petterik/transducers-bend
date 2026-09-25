import Base
import ../xf.bend as Xf
import ../transduce_core.bend as T

def range_sum() -> U32:
  Xf.transduce(Xf.map(~U32, ~U32, ~U32.inc),
    Xf.sum_rf(), 0, T.range_between(0, 3))

def range_stop() -> U32:
  Xf.transduce(Xf.take(~U32, 0n), Xf.sum_rf(), 0,
    T.range_between(0, 3))

def array_sum() -> U32:
  Xf.transduce(Xf.map(~U32, ~U32, ~U32.inc),
    Xf.sum_rf(), 0, Array.new(U32, 2n, 1))

def array_stop() -> U32:
  Xf.transduce(Xf.take(~U32, 2n), Xf.sum_rf(), 0,
    Array.new(U32, 2n, 1))

def string_sum() -> U32:
  Xf.transduce(Xf.map(~Char, ~U32, ~Char.to_u32),
    Xf.sum_rf(), 0, T.String.source("ab"))

def string_empty() -> U32:
  Xf.transduce(Xf.map(~Char, ~U32, ~Char.to_u32),
    Xf.sum_rf(), 0, T.String.source(""))

def main() -> U32 & U32 & U32 & U32 & U32 & U32:
  (range_sum(), range_stop(), array_sum(), array_stop(),
   string_sum(), string_empty())
#|(6, 0, 8, 2, 195, 0)
