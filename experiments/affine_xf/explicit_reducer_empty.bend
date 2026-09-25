import Base
import ./explicit_reducer_types.bend as E

def main() -> U32:
  xf : E.Xf<U32, U32, E.plus_one> = E.Xf{2n}
  E.run(~U32, ~U32, ~U32, ~U32, ~U32,
    ~E.plus_one, ~E.sum2(), xf, 0, [])
#|0
