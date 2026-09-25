import Base
import ./vec_data_probe.bend as Vec
import ./vec_data_fill_probe.bend as Fill
import ./rank2_companion_api.bend as Auto
import ./rank2_rf_values.bend as V

type Quad is Data:
  Quad{a: U32, b: U32}

def to_quad(x: U32) -> Quad:
  Quad{x, 10}

def quad_sum(x: Quad) -> U32:
  match x:
    case Quad{a, b}:
      (a + b : U32)

def run_maybe(xs: List<U32>) -> U32:
  dest = Vec.empty(~Quad)
  vec = Auto.into(dest, V.map(~U32, ~Quad, ~to_quad), xs)
  Auto.transduce(V.map(~Quad, ~U32, ~quad_sum), V.sum_rf(), 0, vec)

def run_fill(xs: List<U32>) -> U32:
  dest = Fill.empty(~Quad, Quad{0, 0})
  vec = Auto.into(dest, V.map(~U32, ~Quad, ~to_quad), xs)
  Auto.transduce(V.map(~Quad, ~U32, ~quad_sum), V.sum_rf(), 0, vec)

def run_reserved(xs: List<U32>) -> U32:
  dest = Fill.reserve(~Quad, 2n, Quad{0, 0})
  vec = Auto.into(dest, V.map(~U32, ~Quad, ~to_quad), xs)
  Auto.transduce(V.map(~Quad, ~U32, ~quad_sum), V.sum_rf(), 0, vec)

def order_fill(xs: List<U32>, output: List<U32>) -> List<U32>:
  dest = Fill.empty(~Quad, Quad{0, 0})
  vec = Auto.into(dest, V.map(~U32, ~Quad, ~to_quad), xs)
  Auto.into(output, V.map(~Quad, ~U32, ~quad_sum), vec)

def get_after_set(old: U32, result: Fill.VecFill<U32> & Maybe<&2, U32>) ->
  U32 & Maybe<&2, U32>:
  (vec, found) = result
  (old, found)

def after_set(result: Fill.UpdateResult<U32>) ->
  U32 & Maybe<&2, U32>:
  match result:
    case Fill.Updated{vec, old}:
      get_after_set(old, Fill.get(~U32, vec, 1))
    case Fill.Invalid{vec, value}:
      get_after_set(value, Fill.get(~U32, vec, 1))

def indexed() -> U32 & Maybe<&2, U32>:
  vec = Fill.push(~U32, Fill.push(~U32, Fill.empty(~U32, 0), 1), 2)
  after_set(Fill.set(~U32, vec, 1, 20))

def invalid_get_after(result: Fill.VecFill<U32> & Maybe<&2, U32>) ->
  Maybe<&2, U32>:
  (vec, found) = result
  found

def invalid_get() -> Maybe<&2, U32>:
  invalid_get_after(Fill.get(~U32, Fill.push(~U32,
    Fill.empty(~U32, 0), 1), 7))

def take_fill(xs: List<U32>, n: Nat) -> U32:
  vec = Auto.into(Fill.empty(~Quad, Quad{0, 0}),
    V.map(~U32, ~Quad, ~to_quad), xs)
  Auto.transduce(V.comp2(V.map(~Quad, ~U32, ~quad_sum),
    V.taking_u32(n)), V.sum_rf(), 0, vec)

def main() -> U32 & U32 & U32 & List<U32> &
  (U32 & Maybe<&2, U32>) & Maybe<&2, U32> & U32 & U32:
  (run_maybe([1, 2, 3]), run_fill([1, 2, 3]),
    run_reserved([1, 2, 3]), order_fill([1, 2, 3], [99]),
    indexed(), invalid_get(), take_fill([1, 2, 3], 2n),
    take_fill([1, 2, 3], 0n))
#|(36, 36, 36, [13, 12, 11, 99], (2, Some{20}), None{}, 23, 0)
