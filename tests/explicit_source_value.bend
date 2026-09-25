import Base
import ../xf.bend as X
import ../transduce_core.bend as T

def three() -> List<U32>:
  [1, 2, 3]

def from_list() -> U32:
  X.transduce(X.map(~U32, ~U32, ~U32.inc), X.sum_rf(), 0,
    T.List.source(~U32, three()))

def from_string() -> U32:
  X.transduce(X.map(~Char, ~U32, ~Char.to_u32), X.sum_rf(), 0,
    T.String.source("ab"))

def main() -> U32 & U32:
  (from_list(), from_string())
#|(9, 195)
