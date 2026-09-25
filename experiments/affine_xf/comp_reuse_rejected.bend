import Base
import ./rank2_rf_values.bend as V

def main() -> U32:
  xf = V.shifted(1)
  V.transduce(V.comp2(xf, xf), V.sum_rf(), 0, [1, 2])
