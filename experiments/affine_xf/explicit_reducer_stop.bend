import Base
import ./explicit_reducer_types.bend as E
import ../../transduce.bend as T

def stopped() -> E.R2<U32, U32, U32, U32>:
  E.R2{x => T.Stop{x}, s => x => T.Stop{(s + 1000 : U32)},
    s => (s + 99 : U32)}

def main() -> U32:
  xf : E.Xf<U32, U32, E.plus_one> = E.Xf{2n}
  E.run(~U32, ~U32, ~U32, ~U32, ~U32,
    ~E.plus_one, ~stopped(), xf, 5, [1, 2, 3])
#|104
