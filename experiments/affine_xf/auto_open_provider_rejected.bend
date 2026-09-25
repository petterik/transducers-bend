import Base
import ./rank2_static_provider.bend as P
import ../../transduce.bend as T

def attempt(-Code: @-R: Type -> @-down: T.Reducer<U32, R> ->
    T.Reducer<U32, R>,
  xf: P.Xf<Code>, xs: List<U32>) -> U32:
  P.run(~?AUTO, ~U32, ~T.sum(), xf, 0, xs)

def main() -> U32:
  attempt((R => down => T.take(~U32, ~R, ~down)),
    P.shift_take(2n, 1), [1, 2, 3])
