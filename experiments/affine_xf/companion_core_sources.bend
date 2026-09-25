import Base
import ./rank2_companion_api.bend as Auto
import ./rank2_rf_values.bend as V
import ../../transduce.bend as T

# Range owns its source method in the core. Array, like List, uses the
# protocol-owned Base extension. Both traverse in source order and stop early.
def main() -> U32 & U32 & U32:
  xs = Array.set(U32, Array.set(U32, [0 : U32*4n], 0, 1), 1, 2)
  (Auto.transduce(V.take(~U32, 2n), V.sum_rf(), 0,
     T.range_between(1, 4)),
   Auto.transduce(V.take(~U32, 2n), V.sum_rf(), 0, xs),
   Auto.transduce(V.map(~U32, ~U32, ~U32.inc), V.sum_rf(), 0,
     [1 : U32*4n]))
#|(3, 3, 8)
