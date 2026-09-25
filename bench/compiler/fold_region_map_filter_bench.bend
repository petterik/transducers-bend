import Base
import ../../transduce.bend as T
import ../array_partition/bench_clock.bend as BenchClock

def plus_one(x: U32) -> U32:
  (x + 1 : U32)

def is_even(x: U32) -> Bool:
  U32.is_eq(U32.mod(x, 2), 0)

def is_even_unit(local: Unit, x: U32) -> Bool:
  is_even(x)

def hash_step(acc: U32, value: U32) -> U32:
  ((acc * 33 : U32) + value : U32)

def mapped_values(xs: List<U32>) -> +List<U32>:
  match xs:
    case Nil{}:
      Nil{}
    case h <> t:
      plus_one(h) <> mapped_values(t)

def materialized(xs: List<U32>, state: U32) -> U32:
  List.foldl(~&2, ~U32, ~U32, ~hash_step,
    List.filter(~U32, ~is_even, mapped_values(xs)), state)

def add_if_even(state: U32, mapped: U32, keep: Bool) -> U32:
  match keep:
    case False{}:
      state
    case True{}:
      hash_step(state, mapped)

def handwritten(xs: List<U32>, +state: U32) -> U32:
  match xs:
    case Nil{}:
      state
    case h <> t:
      +mapped = plus_one(h)
      keep = is_even(mapped)
      next = add_if_even(state, mapped, keep)
      handwritten(t, next)

def transducer_pipeline() -> T.Reducer<U32, U32>:
  T.map(~U32, ~U32, ~U32, ~plus_one,
    ~T.filter(~U32, ~U32, ~Unit, ~is_even_unit,
      ~T.reducing(~U32, ~U32, ~U32, ~hash_step, ~(state => state))))

def transduced(xs: List<U32>, state: U32) -> U32:
  T.transduce(~T.over_list(~U32, ~U32, ~transducer_pipeline()),
    (Unit{}, state), xs)

def once(mode: Nat, xs: List<U32>, state: U32) -> U32:
  match mode:
    case 0n:
      materialized(xs, state)
    case 1n:
      transduced(xs, state)
    case _:
      handwritten(xs, state)

def numbers(n: Nat, acc: List<U32>) -> List<U32>:
  match n:
    case 0n:
      acc
    case 1n++p:
      numbers(p, U32.from_nat(p) <> acc)

def measure(mode: Nat, size: Nat) -> IO(Nat & U32):
  xs = numbers(size, [])
  do IO<Nat & U32>:
    before : Nat <- BenchClock.now_us()
    answer : U32 <- IO.pure(U32, once(mode, xs, 5381))
    after : Nat <- BenchClock.now_us()
    return (Nat.sub(after, before), answer)

def parsed(value: Maybe<&2, Nat>) -> Nat:
  match value:
    case None{}:
      0n
    case Some{n}:
      n

def arg_nat(value: String) -> Nat:
  parsed(Nat.read(value))

def result_text(result: Nat & U32) -> String:
  (elapsed, answer) = result
  String.append(Nat.show(elapsed),
    String.append(" ", U32.show(answer)))

def run_measure(mode: Nat, size: Nat) -> IO(Unit):
  do IO<Unit>:
    result : Nat & U32 <- measure(mode, size)
    IO.print(result_text(result))

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> size <> rest:
      run_measure(arg_nat(mode), arg_nat(size))
    case _:
      run_measure(0n, 200000n)

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
