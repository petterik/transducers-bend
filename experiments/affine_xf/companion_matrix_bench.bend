import Base
import ./rank2_companion_api.bend as Auto
import ./rank2_rf_values.bend as V
import ./static_recipe_bench.bend as B
import ./companion_semantics_matrix.bend as M
import ./reducible_cat_probe.bend as Cat
import ../../transduce.bend as T
import ../../bench/array_partition/bench_clock.bend as Clock

type Counted is Type:
  Counted{items: List<U32>}

def fold_counted(~R: Type, ~r: T.Reducer<U32, R>, xs: Counted,
  c: T.Control<T.State(U32, R, r)>) -> T.Control<T.State(U32, R, r)>:
  match xs:
    case Counted{items}:
      T.reduce_list_static(~U32, ~R, ~r, items, c)

def Counted.source(xs: Counted) -> T.Source<U32, Counted,
  (R => r => input => c => fold_counted(~R, ~r, input, c))>:
  T.Source{xs}

def count_loop(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case x <> tail:
      count_loop(tail, (acc + x + 1 : U32))

def counted_generic(xs: Counted) -> U32:
  Auto.transduce(V.map(~U32, ~U32, ~U32.inc), V.sum_rf(), 0, xs)

def keep_add(yes: Bool, x: U32, acc: U32) -> U32:
  match yes:
    case True{}:
      (acc + x : U32)
    case False{}:
      acc

def keep_direct(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case +x <> tail:
      keep_direct(tail, keep_add(M.even(x), x, acc))

def keep_static(xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.keep(~U32, ~U32, ~U32,
      ~(x => M.maybe_even(x)), ~T.sum())), 0, xs)

def keep_generic(xs: List<U32>) -> U32:
  Auto.transduce(V.keep(~U32, ~U32, ~(x => M.maybe_even(x))),
    V.sum_rf(), 0, xs)

def mapcat_direct(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case +x <> tail:
      mapcat_direct(tail, (acc + x + x + 10 : U32))

def mapcat_static(xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.mapcat(~U32, ~U32, ~U32,
      ~(x => M.pair(x)), ~T.sum())), 0, xs)

def mapcat_generic(xs: List<U32>) -> U32:
  Auto.transduce(V.mapcat(~U32, ~U32, ~(x => M.pair(x))),
    V.sum_rf(), 0, xs)

def first_pairs(xs: List<U32>, remaining: Nat, acc: U32) -> U32:
  match xs remaining:
    case Nil{} n:
      acc
    case x <> tail 0n:
      acc
    case +x <> tail 1n+p:
      first_pairs(tail, p, (acc + x + x + 10 : U32))

def take_pair_direct(xs: List<U32>, n: Nat) -> U32:
  first_pairs(xs, Nat.div(n, 2n), 0)

def take_after_generic(xs: List<U32>, n: Nat) -> U32:
  Auto.transduce(V.comp2(V.mapcat(~U32, ~U32, ~(x => M.pair(x))),
    V.take(~U32, n)), V.sum_rf(), 0, xs)

def take_before_generic(xs: List<U32>, n: Nat) -> U32:
  Auto.transduce(V.comp2(V.take(~U32, Nat.div(n, 2n)),
    V.mapcat(~U32, ~U32, ~(x => M.pair(x)))), V.sum_rf(), 0, xs)

def array_direct(xs: Array<U32>, acc: U32) -> U32:
  match xs:
    case ALeaf{x}:
      (acc + x + 1 : U32)
    case ANode{left, right}:
      array_direct(right, array_direct(left, acc))

def array_generic(xs: Array<U32>) -> U32:
  Auto.transduce(V.map(~U32, ~U32, ~U32.inc), V.sum_rf(), 0, xs)

def list_sum(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case x <> tail:
      list_sum(tail, (acc + x : U32))

def keep_prepend(yes: Bool, x: U32, acc: List<U32>) -> List<U32>:
  match yes:
    case True{}:
      x <> acc
    case False{}:
      acc

def keep_build(xs: List<U32>, acc: List<U32>) -> List<U32>:
  match xs:
    case Nil{}:
      acc
    case +x <> tail:
      keep_build(tail, keep_prepend(M.even(x), x, acc))

def retain_direct(xs: List<U32>) -> U32:
  list_sum(keep_build(xs, []), 0)

def retain_into(dest: List<U32>, xs: List<U32>) -> List<U32>:
  Auto.into(dest, V.keep(~U32, ~U32,
    ~(x => M.maybe_even(x))), xs)

def retain_generic(xs: List<U32>) -> U32:
  list_sum(retain_into([], xs), 0)

def once_list(mode: Nat, xs: List<U32>, n: Nat) -> U32:
  match mode:
    case 0n: keep_direct(xs, 0)
    case 1n: keep_static(xs)
    case 2n: keep_generic(xs)
    case 3n: mapcat_direct(xs, 0)
    case 4n: mapcat_static(xs)
    case 5n: mapcat_generic(xs)
    case 8n: retain_direct(xs)
    case 9n: retain_generic(xs)
    case 10n: take_pair_direct(xs, n)
    case 11n: take_after_generic(xs, n)
    case 15n: Cat.via_source(xs)
    case _: take_before_generic(xs, n)

def once_array(mode: Nat, xs: Array<U32>) -> U32:
  match mode:
    case 6n: array_direct(xs, 0)
    case _: array_generic(xs)

def measure_list(mode: Nat, +size: Nat) -> IO(Nat & U32):
  xs = B.numbers(size, [])
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, once_list(mode, xs, size))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def measure_array(mode: Nat, depth: Nat) -> IO(Nat & U32):
  xs = Array.new(U32, depth, 1)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, once_array(mode, xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def count_once(mode: Nat, xs: List<U32>) -> U32:
  match mode:
    case 13n: count_loop(xs, 0)
    case _: counted_generic(Counted{xs})

def measure_count(mode: Nat, +size: Nat) -> IO(Nat & U32):
  xs = B.numbers(size, [])
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, count_once(mode, xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def choose_measure(mode: Nat, n: Nat) -> IO(Nat & U32):
  match mode:
    case 6n: measure_array(6n, n)
    case 7n: measure_array(7n, n)
    case 13n: measure_count(13n, n)
    case 14n: measure_count(14n, n)
    case _: measure_list(mode, n)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> size <> rest:
      do IO<Unit>:
        result : Nat & U32 <- choose_measure(B.arg_nat(mode), B.arg_nat(size))
        IO.print(B.show_result(result))
    case _:
      do IO<Unit>:
        result : Nat & U32 <- measure_list(0n, 20n)
        IO.print(B.show_result(result))

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
