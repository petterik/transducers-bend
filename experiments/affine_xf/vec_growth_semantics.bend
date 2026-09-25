import Base
import ./vec_data_probe.bend as MaybeVec
import ./vec_data_fill_probe.bend as FillVec
import ./rank2_companion_api.bend as Auto
import ./rank2_rf_values.bend as V
import ./static_recipe_bench.bend as B

def empty_u32() -> List<U32>:
  []

def maybe_items(xs: List<U32>) -> List<U32>:
  vec = Auto.into(MaybeVec.empty(~U32), V.shifted(1), xs)
  Auto.into(empty_u32(), V.shifted(0), vec)

def fill_items(xs: List<U32>) -> List<U32>:
  vec = Auto.into(FillVec.empty(~U32, 0), V.shifted(1), xs)
  Auto.into(empty_u32(), V.shifted(0), vec)

def maybe_take(xs: List<U32>, n: Nat) -> List<U32>:
  vec = Auto.into(MaybeVec.empty(~U32), V.shifted(1), xs)
  Auto.into(empty_u32(), V.taking_u32(n), vec)

def fill_take(xs: List<U32>, n: Nat) -> List<U32>:
  vec = Auto.into(FillVec.empty(~U32, 0), V.shifted(1), xs)
  Auto.into(empty_u32(), V.taking_u32(n), vec)

def main() -> List<U32> & List<U32> & List<U32> & List<U32> &
  List<U32> & List<U32> & List<U32> & List<U32> &
  List<U32> & List<U32> & List<U32> & List<U32>:
  (maybe_items(B.numbers(0n, [])), fill_items(B.numbers(0n, [])),
   maybe_items(B.numbers(1n, [])), fill_items(B.numbers(1n, [])),
   maybe_items(B.numbers(5n, [])), fill_items(B.numbers(5n, [])),
   maybe_items(B.numbers(9n, [])), fill_items(B.numbers(9n, [])),
   maybe_take(B.numbers(9n, []), 0n), fill_take(B.numbers(9n, []), 0n),
   maybe_take(B.numbers(9n, []), 2n), fill_take(B.numbers(9n, []), 2n))
