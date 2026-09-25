import Base
import ./rank2_companion_api.bend as Auto
import ./rank2_rf_values.bend as V
import ./rank2_auto_sources.bend as P

def list_into(xs: List<U32>) -> List<U32>:
  Auto.into([], V.take(~U32, 2n), xs)

def empty_sum() -> U32:
  Auto.transduce(V.take(~U32, 3n), V.sum_rf(), 0, [])

def pair_sum() -> U32:
  Auto.transduce(V.take(~U32, 2n), V.sum_rf(), 0,
    P.SamplePair{1, 2})

def main() -> List<U32> & U32 & U32:
  (list_into([1, 2, 3]), empty_sum(), pair_sum())
#|([2, 1], 0, 3)
