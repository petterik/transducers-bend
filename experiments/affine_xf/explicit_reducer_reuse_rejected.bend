import Base
import ./explicit_reducer_types.bend as E

# An owned Xf may enter only one reduction.
def main() -> U32:
  xf : E.Xf<U32, U32, E.plus_one> = E.Xf{2n}
  a = E.run(~U32, ~U32, ~U32, ~U32, ~U32,
    ~E.plus_one, ~E.sum2(), xf, 0, [1, 2, 3])
  b = E.run(~U32, ~U32, ~U32, ~U32, ~U32,
    ~E.plus_one, ~E.sum2(), xf, 0, [4, 5, 6])
  (a + b : U32)
