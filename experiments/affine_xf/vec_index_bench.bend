import Base
import ../../vec.bend as Vec
import ./vec_data_fill_probe.bend as Legacy
import ../../transduce.bend as T
import ./static_recipe_bench.bend as B
import ../../bench/array_partition/bench_clock.bend as Clock

def array_after(acc: U32, result: Array<U32> & U32) ->
  T.Control<(Array<U32> & U32)>:
  (slots, value) = result
  T.Continue{(slots, U32.add(acc, value))}

def array_step(state: Array<U32> & U32, index: U32) ->
  T.Control<(Array<U32> & U32)>:
  (slots, acc) = state
  array_after(acc, Array.get(U32, slots, index))

def array_finish(control: T.Control<(Array<U32> & U32)>) -> U32:
  match control:
    case T.Stop{(slots, sum)}:
      sum
    case T.Continue{(slots, sum)}:
      sum

def array_sum(slots: Array<U32>, size: U32) -> U32:
  array_finish(T.reduce_range(~(Array<U32> & U32),
    ~array_step, T.range_between(0, size),
    T.Continue{(slots, 0)}))

def vec_after(acc: U32,
  result: Vec.Vec<U32> & Maybe<&2, U32>) ->
  T.Control<(Vec.Vec<U32> & U32)>:
  (vec, value) = result
  match value:
    case None{}:
      T.Continue{(vec, acc)}
    case Some{x}:
      T.Continue{(vec, U32.add(acc, x))}

def vec_step(state: Vec.Vec<U32> & U32, index: U32) ->
  T.Control<(Vec.Vec<U32> & U32)>:
  (vec, acc) = state
  vec_after(acc, Vec.get(~U32, vec, index))

def vec_finish(control: T.Control<(Vec.Vec<U32> & U32)>) -> U32:
  match control:
    case T.Stop{(vec, sum)}:
      sum
    case T.Continue{(vec, sum)}:
      sum

def vec_sum(vec: Vec.Vec<U32>, size: U32) -> U32:
  vec_finish(T.reduce_range(~(Vec.Vec<U32> & U32),
    ~vec_step, T.range_between(0, size),
    T.Continue{(vec, 0)}))

def unchecked_after(acc: U32, result: Vec.Vec<U32> & U32) ->
  T.Control<(Vec.Vec<U32> & U32)>:
  (vec, value) = result
  T.Continue{(vec, U32.add(acc, value))}

def unchecked_step(state: Vec.Vec<U32> & U32, index: U32) ->
  T.Control<(Vec.Vec<U32> & U32)>:
  (vec, acc) = state
  unchecked_after(acc, Vec.get_unchecked(~U32, vec, index))

def unchecked_sum(vec: Vec.Vec<U32>, size: U32) -> U32:
  vec_finish(T.reduce_range(~(Vec.Vec<U32> & U32),
    ~unchecked_step, T.range_between(0, size),
    T.Continue{(vec, 0)}))

def array_mut_after(acc: U32, result: Array<U32> & U32) ->
  T.Control<(Array<U32> & U32)>:
  (slots, old) = result
  T.Continue{(slots, U32.add(acc, old))}

def array_mut_step(state: Array<U32> & U32, +index: U32) ->
  T.Control<(Array<U32> & U32)>:
  (slots, acc) = state
  array_mut_after(acc, Array.swap(U32, slots, index, U32.add(index, 1)))

def array_mut(slots: Array<U32>, size: U32) -> U32:
  array_finish(T.reduce_range(~(Array<U32> & U32),
    ~(s => i => array_mut_step(s, i)), T.range_between(0, size),
    T.Continue{(slots, 0)}))

def vec_mut_after(acc: U32, result: Vec.Vec<U32> & U32) ->
  T.Control<(Vec.Vec<U32> & U32)>:
  (vec, old) = result
  T.Continue{(vec, U32.add(acc, old))}

def vec_mut_step(state: Vec.Vec<U32> & U32, +index: U32) ->
  T.Control<(Vec.Vec<U32> & U32)>:
  (vec, acc) = state
  vec_mut_after(acc, Vec.set_unchecked(~U32, vec, index,
    U32.add(index, 1)))

def vec_mut(vec: Vec.Vec<U32>, size: U32) -> U32:
  vec_finish(T.reduce_range(~(Vec.Vec<U32> & U32),
    ~(s => i => vec_mut_step(s, i)), T.range_between(0, size),
    T.Continue{(vec, 0)}))

def vec_checked_mut_after(acc: U32, result: Vec.UpdateResult<U32>) ->
  T.Control<(Vec.Vec<U32> & U32)>:
  match result:
    case Vec.Updated{vec, old}:
      T.Continue{(vec, U32.add(acc, old))}
    case Vec.Invalid{vec, value}:
      T.Continue{(vec, acc)}

def vec_checked_mut_step(state: Vec.Vec<U32> & U32, +index: U32) ->
  T.Control<(Vec.Vec<U32> & U32)>:
  (vec, acc) = state
  vec_checked_mut_after(acc, Vec.set(~U32, vec, index,
    U32.add(index, 1)))

def vec_checked_mut(vec: Vec.Vec<U32>, size: U32) -> U32:
  vec_finish(T.reduce_range(~(Vec.Vec<U32> & U32),
    ~(s => i => vec_checked_mut_step(s, i)), T.range_between(0, size),
    T.Continue{(vec, 0)}))

def fill(xs: List<U32>, +index: U32, slots: Array<U32>) -> Array<U32>:
  match xs:
    case Nil{}:
      slots
    case x <> tail:
      fill(tail, U32.add(index, 1), Array.set(U32, slots, index, x))

def prepared(size: U32) -> Array<U32>:
  fill(B.numbers(U32.to_nat(size), []), 0, Array.new(U32, 18n, 0))

def legacy_after(acc: U32,
  result: Legacy.VecFill<U32> & Maybe<&2, U32>) ->
  T.Control<(Legacy.VecFill<U32> & U32)>:
  (vec, value) = result
  match value:
    case None{}:
      T.Continue{(vec, acc)}
    case Some{x}:
      T.Continue{(vec, U32.add(acc, x))}

def legacy_step(state: Legacy.VecFill<U32> & U32, index: U32) ->
  T.Control<(Legacy.VecFill<U32> & U32)>:
  (vec, acc) = state
  legacy_after(acc, Legacy.get(~U32, vec, index))

def legacy_finish(control: T.Control<(Legacy.VecFill<U32> & U32)>) -> U32:
  match control:
    case T.Stop{(vec, sum)}:
      sum
    case T.Continue{(vec, sum)}:
      sum

def legacy_sum(vec: Legacy.VecFill<U32>, size: U32) -> U32:
  legacy_finish(T.reduce_range(~(Legacy.VecFill<U32> & U32),
    ~legacy_step, T.range_between(0, size),
    T.Continue{(vec, 0)}))

def measure_array(+size: U32) -> IO(Nat & U32):
  slots = prepared(size)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, array_sum(slots, size))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def ready_vec(+size: U32) -> Vec.Vec<U32>:
  Vec.Vec{size, 262144, 18n, 0, prepared(size)}

def measure_vec(+size: U32) -> IO(Nat & U32):
  vec = ready_vec(size)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, vec_sum(vec, size))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def ready_legacy(+size: U32) -> Legacy.VecFill<U32>:
  Legacy.VecFill{size, 262144, 18n, 0, prepared(size)}

def measure_legacy(+size: U32) -> IO(Nat & U32):
  vec = ready_legacy(size)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, legacy_sum(vec, size))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def measure_unchecked(+size: U32) -> IO(Nat & U32):
  vec = ready_vec(size)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, unchecked_sum(vec, size))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def measure_array_mut(+size: U32) -> IO(Nat & U32):
  slots = prepared(size)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, array_mut(slots, size))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def measure_vec_mut(+size: U32) -> IO(Nat & U32):
  vec = ready_vec(size)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, vec_mut(vec, size))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def measure_vec_checked_mut(+size: U32) -> IO(Nat & U32):
  vec = ready_vec(size)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, vec_checked_mut(vec, size))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def choose(mode: Nat, size: U32) -> IO(Nat & U32):
  match mode:
    case 0n:
      measure_array(size)
    case 1n:
      measure_vec(size)
    case 2n:
      measure_legacy(size)
    case 3n:
      measure_unchecked(size)
    case 4n:
      measure_array_mut(size)
    case 5n:
      measure_vec_mut(size)
    case _:
      measure_vec_checked_mut(size)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> size <> rest:
      do IO<Unit>:
        result : Nat & U32 <- choose(B.arg_nat(mode),
          U32.from_nat(B.arg_nat(size)))
        IO.print(B.show_result(result))
    case _:
      IO.print("usage: vec_index_bench <mode> <size>")

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
