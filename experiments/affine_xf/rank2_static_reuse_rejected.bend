import Base
import ./rank2_static_provider.bend as P
import ./custom_shift.bend as Shift
import ../../transduce.bend as T

def main() -> U32:
  xf = P.shift_take(2n, 1)
  first = P.run(~(R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~T.take(~U32, ~R, ~down))),
    ~U32, ~T.sum(), xf, 0, [1, 2, 3])
  second = P.run(~(R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~T.take(~U32, ~R, ~down))),
    ~U32, ~T.sum(), xf, 0, [1, 2, 3])
  (first + second : U32)
