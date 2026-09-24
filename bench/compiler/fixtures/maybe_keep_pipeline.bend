import Base
import ../../../transduce.bend as T
import ../../array_partition/bench_clock.bend as BenchClock

def numbers(n: Nat, acc: List<U32>) -> List<U32>:
  match n:
    case 0n:
      acc
    case 1n++p:
      numbers(p, U32.from_nat(p) <> acc)

def batch_inputs(+n: Nat, count: Nat, acc: List<List<U32>>) -> List<List<U32>>:
  match count:
    case 0n:
      acc
    case 1n+p:
      batch_inputs(n, p, numbers(n, []) <> acc)

def some_value(x: U32) -> Maybe<U32>:
  Some{x}

def add_option(acc: U32, value: Maybe<U32>) -> U32:
  match value:
    case None{}:
      acc
    case Some{x}:
      (acc + x : U32)

def map_fold_sum(xs: List<U32>) -> U32:
  List.foldl(~&1, ~Maybe<U32>, ~U32, ~add_option,
    List.map(~U32, ~Maybe<U32>, ~some_value, xs), 0)

def let_bound_map_fold_sum(xs: List<U32>) -> U32:
  values = List.map(~U32, ~Maybe<U32>, ~some_value, xs)
  List.foldl(~&1, ~Maybe<U32>, ~U32, ~add_option, values, 0)

def keep_sum(xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.keep(~U32, ~U32, ~U32, ~some_value, ~T.sum())), 0, xs)

def direct_loop(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case x <> rest:
      direct_loop(rest, (acc + x : U32))

def direct_sum(xs: List<U32>, acc: U32) -> U32:
  direct_loop(xs, acc)

def keep_batch(xs: List<List<U32>>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case input <> rest:
      keep_batch(rest, (acc + keep_sum(input) : U32))

def map_fold_batch(xs: List<List<U32>>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case input <> rest:
      map_fold_batch(rest, (acc + map_fold_sum(input) : U32))

def let_bound_map_fold_batch(xs: List<List<U32>>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case input <> rest:
      let_bound_map_fold_batch(rest,
        (acc + let_bound_map_fold_sum(input) : U32))

def direct_batch(xs: List<List<U32>>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case input <> rest:
      direct_batch(rest, (acc + direct_sum(input, 0) : U32))

def measure_keep(xs: List<List<U32>>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- BenchClock.now_us()
    total : U32 = keep_batch(xs, 0)
    after : Nat <- BenchClock.now_us()
    return (Nat.sub(after, before), total)

def measure_map_fold(xs: List<List<U32>>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- BenchClock.now_us()
    total : U32 = map_fold_batch(xs, 0)
    after : Nat <- BenchClock.now_us()
    return (Nat.sub(after, before), total)

def measure_let_bound_map_fold(xs: List<List<U32>>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- BenchClock.now_us()
    total : U32 = let_bound_map_fold_batch(xs, 0)
    after : Nat <- BenchClock.now_us()
    return (Nat.sub(after, before), total)

def measure_direct(xs: List<List<U32>>) -> IO(Nat & U32):
  do IO<Nat & U32>:
    before : Nat <- BenchClock.now_us()
    total : U32 = direct_batch(xs, 0)
    after : Nat <- BenchClock.now_us()
    return (Nat.sub(after, before), total)

def result_text(name: String, result: Nat & U32) -> String:
  (elapsed, total) = result
  String.append(name, String.append(" ", String.append(Nat.show(elapsed),
    String.append(" ", U32.show(total)))))

def main() -> IO(Unit):
  keep_inputs = batch_inputs(200000n, 8n, [])
  map_fold_inputs = batch_inputs(200000n, 8n, [])
  let_bound_inputs = batch_inputs(200000n, 8n, [])
  direct_inputs = batch_inputs(200000n, 8n, [])
  do IO<Unit>:
    kept : Nat & U32 <- measure_keep(keep_inputs)
    map_fold : Nat & U32 <- measure_map_fold(map_fold_inputs)
    let_bound_map_fold : Nat & U32 <- measure_let_bound_map_fold(let_bound_inputs)
    direct : Nat & U32 <- measure_direct(direct_inputs)
    IO.print(result_text("keep", kept))
    IO.print(result_text("map_fold", map_fold))
    IO.print(result_text("let_bound_map_fold", let_bound_map_fold))
    IO.print(result_text("direct", direct))
