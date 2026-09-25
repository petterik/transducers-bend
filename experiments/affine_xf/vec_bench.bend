import Base
import ./vec_probe.bend as VecProbe
import ./vec_data_probe.bend as Fast
import ./vec_data_fill_probe.bend as Fill
import ../../vec.bend as PublicVec
import ../../vec_maybe.bend as PublicMaybe
import ../../xf.bend as Xf
import ./rank2_companion_api.bend as Auto
import ./rank2_rf_values.bend as V
import ./static_recipe_bench.bend as B
import ../../transduce.bend as T
import ../../bench/array_partition/bench_clock.bend as Clock

def vec_direct(xs: List<U32>, vec: VecProbe.Vec<U32>) ->
  VecProbe.Vec<U32>:
  match xs:
    case Nil{}:
      vec
    case +x <> tail:
      vec_direct(tail, VecProbe.push(~U32, vec, (x + 1 : U32)))

def fast_direct(xs: List<U32>, vec: Fast.VecData<U32>) -> Fast.VecData<U32>:
  match xs:
    case Nil{}:
      vec
    case +x <> tail:
      fast_direct(tail, Fast.push(~U32, vec, (x + 1 : U32)))

def fill_direct(xs: List<U32>, vec: Fill.VecFill<U32>) -> Fill.VecFill<U32>:
  match xs:
    case Nil{}:
      vec
    case +x <> tail:
      fill_direct(tail, Fill.push(~U32, vec, (x + 1 : U32)))

def list_direct(xs: List<U32>, acc: List<U32>) -> List<U32>:
  match xs:
    case Nil{}:
      acc
    case +x <> tail:
      list_direct(tail, (x + 1 : U32) <> acc)

def sum_list(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case x <> tail:
      sum_list(tail, (acc + x : U32))

def vec_sum(vec: VecProbe.Vec<U32>) -> U32:
  Auto.transduce(V.shifted(0), V.sum_rf(), 0, vec)

def fast_sum(vec: Fast.VecData<U32>) -> U32:
  Auto.transduce(V.shifted(0), V.sum_rf(), 0, vec)

def fill_sum(vec: Fill.VecFill<U32>) -> U32:
  Auto.transduce(V.shifted(0), V.sum_rf(), 0, vec)

def add(offset: U32, x: U32) -> U32:
  (offset + x : U32)

def public_sum(vec: PublicVec.Vec<U32>) -> U32:
  Xf.transduce(Xf.map_with(~U32, ~U32, ~U32, ~add, 0),
    Xf.sum_rf(), 0, vec)

def public_build_at(xs: List<U32>,
  choice: Maybe<PublicVec.Vec<U32>>) -> Maybe<PublicVec.Vec<U32>>:
  match choice:
    case None{}:
      None{}
    case Some{vec}:
      Some{Xf.into(vec, Xf.map_with(~U32, ~U32, ~U32, ~add, 1), xs)}

def public_build(xs: List<U32>) -> Maybe<PublicVec.Vec<U32>>:
  public_build_at(xs, PublicVec.with_capacity(~U32, 200000, 0))

def public_sum_maybe(choice: Maybe<PublicVec.Vec<U32>>) -> U32:
  match choice:
    case None{}:
      0
    case Some{vec}:
      public_sum(vec)

def public_dynamic(xs: List<U32>) -> PublicVec.Vec<U32>:
  Xf.into(PublicVec.empty(~U32, 0),
    Xf.map_with(~U32, ~U32, ~U32, ~add, 1), xs)

def maybe_sum_public(vec: PublicMaybe.VecMaybe<U32>) -> U32:
  Xf.transduce(Xf.map_with(~U32, ~U32, ~U32, ~add, 0),
    Xf.sum_rf(), 0, vec)

def maybe_build_at(xs: List<U32>,
  choice: Maybe<PublicMaybe.VecMaybe<U32>>) ->
  Maybe<PublicMaybe.VecMaybe<U32>>:
  match choice:
    case None{}:
      None{}
    case Some{vec}:
      Some{Xf.into(vec, Xf.map_with(~U32, ~U32, ~U32, ~add, 1), xs)}

def maybe_build(xs: List<U32>) -> Maybe<PublicMaybe.VecMaybe<U32>>:
  maybe_build_at(xs, PublicMaybe.with_capacity(~U32, 200000))

def maybe_sum_result(choice: Maybe<PublicMaybe.VecMaybe<U32>>) -> U32:
  match choice:
    case None{}:
      0
    case Some{vec}:
      maybe_sum_public(vec)

def array_fill(xs: List<U32>, +index: U32, array: Array<U32>) -> Array<U32>:
  match xs:
    case Nil{}:
      array
    case +x <> tail:
      array_fill(tail, U32.add(index, 1),
        Array.set(U32, array, index, (x + 1 : U32)))

def array_after_get(acc: U32, result: Array<U32> & U32) ->
  T.Control<(Array<U32> & U32)>:
  (array, value) = result
  T.Continue{(array, U32.add(acc, value))}

def array_sum_step(pair: Array<U32> & U32, index: U32) ->
  T.Control<(Array<U32> & U32)>:
  (array, acc) = pair
  array_after_get(acc, Array.get(U32, array, index))

def array_sum_done(control: T.Control<(Array<U32> & U32)>) -> U32:
  match control:
    case T.Stop{(array, sum)}:
      sum
    case T.Continue{(array, sum)}:
      sum

def array_sum(array: Array<U32>, size: U32) -> U32:
  array_sum_done(T.reduce_range(~(Array<U32> & U32),
    ~array_sum_step, T.range_between(0, size),
    T.Continue{(array, 0)}))

def array_direct(xs: List<U32>, size: U32) -> U32:
  array_sum(array_fill(xs, 0, Array.new(U32, 18n, 0)), size)

def empty_list() -> List<U32>:
  []

def run_lane(mode: Nat, xs: List<U32>, size: U32) -> U32:
  match mode:
    case 0n:
      sum_list(list_direct(xs, []), 0)
    case 1n:
      sum_list(Auto.into(empty_list(), V.shifted(1), xs), 0)
    case 2n:
      vec_sum(vec_direct(xs, VecProbe.empty(~U32)))
    case 4n:
      array_direct(xs, size)
    case 5n:
      fast_sum(fast_direct(xs, Fast.empty(~U32)))
    case 6n:
      fast_sum(Auto.into(Fast.empty(~U32), V.shifted(1), xs))
    case 7n:
      fill_sum(fill_direct(xs, Fill.empty(~U32, 0)))
    case 8n:
      fill_sum(Auto.into(Fill.empty(~U32, 0), V.shifted(1), xs))
    case 9n:
      fill_sum(Auto.into(Fill.reserve(~U32, 18n, 0),
        V.shifted(1), xs))
    case 10n:
      fast_sum(Auto.into(Fast.reserve(~U32, 18n),
        V.shifted(1), xs))
    case 15n:
      public_sum_maybe(public_build(xs))
    case 17n:
      public_sum(public_dynamic(xs))
    case 19n:
      maybe_sum_result(maybe_build(xs))
    case _:
      vec = VecProbe.empty(~U32)
      vec_sum(Auto.into(vec, V.shifted(1), xs))

def measure(mode: Nat, +size: Nat) -> IO(Nat & U32):
  xs = B.numbers(size, [])
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, run_lane(mode, xs, U32.from_nat(size)))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

# Keep the built collection live past the second clock read. This makes
# construction, rather than construction plus traversal, the timed operation.
def measure_array_retained(xs: List<U32>, size: U32) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    array : Array<U32> <- IO.pure(Array<U32>,
      array_fill(xs, 0, Array.new(U32, 18n, 0)))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), array_sum(array, size))

def measure_data_retained(xs: List<U32>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    vec : Fast.VecData<U32> <- IO.pure(Fast.VecData<U32>,
      Auto.into(Fast.reserve(~U32, 18n), V.shifted(1), xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), fast_sum(vec))

def measure_fill_retained(xs: List<U32>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    vec : Fill.VecFill<U32> <- IO.pure(Fill.VecFill<U32>,
      Auto.into(Fill.reserve(~U32, 18n, 0), V.shifted(1), xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), fill_sum(vec))

def measure_list_retained(xs: List<U32>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    ys : List<U32> <- IO.pure(List<U32>,
      Auto.into(empty_list(), V.shifted(1), xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), sum_list(ys, 0))

def measure_public_retained(xs: List<U32>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    result : Maybe<PublicVec.Vec<U32>> <- IO.pure(Maybe<PublicVec.Vec<U32>>,
      public_build(xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), public_sum_maybe(result))

def measure_public_dynamic_retained(xs: List<U32>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    vec : PublicVec.Vec<U32> <- IO.pure(PublicVec.Vec<U32>,
      public_dynamic(xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), public_sum(vec))

def measure_maybe_retained(xs: List<U32>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    result : Maybe<PublicMaybe.VecMaybe<U32>> <-
      IO.pure(Maybe<PublicMaybe.VecMaybe<U32>>, maybe_build(xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), maybe_sum_result(result))

def measure_any(mode: Nat, +size: Nat) -> IO(Nat & U32):
  match mode:
    case 11n:
      measure_array_retained(B.numbers(size, []), U32.from_nat(size))
    case 12n:
      measure_data_retained(B.numbers(size, []))
    case 13n:
      measure_fill_retained(B.numbers(size, []))
    case 14n:
      measure_list_retained(B.numbers(size, []))
    case 16n:
      measure_public_retained(B.numbers(size, []))
    case 18n:
      measure_public_dynamic_retained(B.numbers(size, []))
    case 20n:
      measure_maybe_retained(B.numbers(size, []))
    case _:
      measure(mode, size)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> size <> rest:
      do IO<Unit>:
        result : Nat & U32 <- measure_any(B.arg_nat(mode), B.arg_nat(size))
        IO.print(B.show_result(result))
    case _:
      IO.print("usage: vec_bench <mode> <size>")

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
