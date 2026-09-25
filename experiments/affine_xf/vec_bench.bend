import Base
import ./vec_probe.bend as VecProbe
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

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> size <> rest:
      do IO<Unit>:
        result : Nat & U32 <- measure(B.arg_nat(mode), B.arg_nat(size))
        IO.print(B.show_result(result))
    case _:
      IO.print("usage: vec_bench <mode> <size>")

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
