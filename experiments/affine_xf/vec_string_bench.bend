import Base
import ./vec_data_probe.bend as MaybeVec
import ./vec_data_fill_probe.bend as FillVec
import ./rank2_companion_api.bend as Auto
import ./rank2_rf_values.bend as V
import ./static_recipe_bench.bend as B
import ../../transduce.bend as T
import ../../bench/array_partition/bench_clock.bend as Clock

def strings(xs: List<U32>, acc: List<String>) -> List<String>:
  match xs:
    case Nil{}:
      acc
    case x <> tail:
      strings(tail, U32.show(x) <> acc)

def sizes(xs: List<String>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case s <> tail:
      sizes(tail, U32.add(acc, U32.from_nat(String.length(s))))

def array_fill(xs: List<String>, +index: U32, slots: Array<String>) ->
  Array<String>:
  match xs:
    case Nil{}:
      slots
    case s <> tail:
      array_fill(tail, U32.add(index, 1), Array.set(String, slots, index, s))

def array_after_get(acc: U32, result: Array<String> & String) ->
  T.Control<(Array<String> & U32)>:
  (slots, value) = result
  T.Continue{(slots, U32.add(acc, U32.from_nat(String.length(value))))}

def array_step(pair: Array<String> & U32, index: U32) ->
  T.Control<(Array<String> & U32)>:
  (slots, acc) = pair
  array_after_get(acc, Array.get(String, slots, index))

def array_done(control: T.Control<(Array<String> & U32)>) -> U32:
  match control:
    case T.Stop{(slots, sum)}:
      sum
    case T.Continue{(slots, sum)}:
      sum

def array_sum(slots: Array<String>, size: U32) -> U32:
  array_done(T.reduce_range(~(Array<String> & U32), ~array_step,
    T.range_between(0, size), T.Continue{(slots, 0)}))

def string_size(s: String) -> U32:
  U32.from_nat(String.length(s))

def maybe_sum(vec: MaybeVec.VecData<String>) -> U32:
  Auto.transduce(V.map(~String, ~U32, ~string_size), V.sum_rf(), 0, vec)

def fill_sum(vec: FillVec.VecFill<String>) -> U32:
  Auto.transduce(V.map(~String, ~U32, ~string_size), V.sum_rf(), 0, vec)

def array_lane(xs: List<String>, size: U32) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    slots : Array<String> <- IO.pure(Array<String>,
      array_fill(xs, 0, Array.new(String, 18n, "x")))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), array_sum(slots, size))

def maybe_lane(xs: List<String>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    vec : MaybeVec.VecData<String> <- IO.pure(MaybeVec.VecData<String>,
      Auto.into(MaybeVec.reserve(~String, 18n),
        V.map(~String, ~String, ~(s => s)), xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), maybe_sum(vec))

def fill_lane(xs: List<String>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    vec : FillVec.VecFill<String> <- IO.pure(FillVec.VecFill<String>,
      Auto.into(FillVec.reserve(~String, 18n, "x"),
        V.map(~String, ~String, ~(s => s)), xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), fill_sum(vec))

def measure_for(mode: Nat, xs: List<String>, size: U32) -> IO(Nat & U32):
  match mode:
    case 0n:
      array_lane(xs, size)
    case 1n:
      maybe_lane(xs)
    case _:
      fill_lane(xs)

def measure(mode: Nat, +size: Nat) -> IO(Nat & U32):
  measure_for(mode, strings(B.numbers(size, []), []), U32.from_nat(size))

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> size <> rest:
      do IO<Unit>:
        result : Nat & U32 <- measure(B.arg_nat(mode), B.arg_nat(size))
        IO.print(B.show_result(result))
    case _:
      IO.print("usage: vec_string_bench <mode> <size>")

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
