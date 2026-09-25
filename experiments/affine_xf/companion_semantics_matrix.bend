import Base
import ./rank2_companion_api.bend as Auto
import ./rank2_rf_values.bend as V
import ./rank2_auto_sources.bend as P
import ../../transduce.bend as T

def even(+x: U32) -> Bool:
  U32.is_eq((x % 2 : U32), 0)

def maybe_even_choose(is_even: Bool, x: U32) -> Maybe<U32>:
  match is_even:
    case True{}:
      Some{x}
    case False{}:
      None{}

def maybe_even(+x: U32) -> Maybe<U32>:
  maybe_even_choose(even(x), x)

def pair(+x: U32) -> List<U32>:
  [x, (x + 10 : U32)]

def array_values() -> Array<U32>:
  a = Array.set(U32, [0 : U32*4n], 0, 1)
  a = Array.set(U32, a, 1, 2)
  a = Array.set(U32, a, 2, 3)
  Array.set(U32, a, 3, 4)

def kept_sum(xs: List<U32>) -> U32:
  Auto.transduce(V.keep(~U32, ~U32, ~(x => maybe_even(x))),
    V.sum_rf(), 0, xs)

def flat_then_take(xs: List<U32>) -> U32:
  Auto.transduce(V.comp2(V.mapcat(~U32, ~U32, ~(x => pair(x))),
    V.take(~U32, 3n)), V.sum_rf(), 0, xs)

def take_then_flat(xs: List<U32>) -> U32:
  Auto.transduce(V.comp2(V.take(~U32, 2n),
    V.mapcat(~U32, ~U32, ~(x => pair(x)))), V.sum_rf(), 0, xs)

def kept_into(dest: List<U32>, xs: List<U32>) -> List<U32>:
  Auto.into(dest, V.keep(~U32, ~U32, ~(x => maybe_even(x))), xs)

def array_into(dest: List<U32>, xs: Array<U32>) -> List<U32>:
  Auto.into(dest, V.take(~U32, 3n), xs)

def pair_sum(xs: P.SamplePair) -> U32:
  Auto.transduce(V.take(~U32, 1n), V.sum_rf(), 0, xs)

def main() -> U32 & U32 & U32 & List<U32> & List<U32> & U32 & U32:
  (kept_sum([1, 2, 3, 4]),
   flat_then_take([1, 2, 3]),
   take_then_flat([1, 2, 3]),
   kept_into([], [1, 2, 3, 4]),
   array_into([], array_values()),
   pair_sum(P.SamplePair{7, 8}),
   Auto.transduce(V.take(~U32, 2n), V.sum_rf(), 0,
     T.range_between(1, 4)))
#|(6, 14, 26, [4, 2], [3, 2, 1], 7, 3)
