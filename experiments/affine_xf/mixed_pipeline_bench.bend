import Base
import ./rank2_rf_values.bend as V
import ./static_recipe_bench.bend as B
import ./custom_shift.bend as Shift
import ../../transduce.bend as T
import ../../bench/array_partition/bench_clock.bend as Clock

def even(x: U32) -> Bool:
  U32.is_eq((x % 2 : U32), 0)

def third(x: U32) -> Bool:
  U32.is_eq((x % 3 : U32), 0)

def allow(+x: U32) -> Bool:
  Bool.and(even(x), Bool.not(third(x)))

@unsafe
def direct_choose(keep: Bool, tail: List<U32>, n: Nat,
  y: U32, acc: U32) -> U32:
  match keep:
    case False{}:
      direct(tail, n, acc)
    case True{}:
      match n:
        case 0n:
          acc
        case 1n+p:
          direct(tail, p, (acc + Shift.add(2, y) : U32))

@unsafe
def direct(xs: List<U32>, n: Nat, acc: U32) -> U32:
  match xs n:
    case Nil{} n:
      acc
    case h <> t 0n:
      acc
    case h <> t 1n+p:
      +y = Shift.add(1, h)
      direct_choose(allow(y), t, 1n+p, y, acc)

def static(xs: List<U32>, n: Nat) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.map_with(~U32, ~U32, ~U32, ~U32, ~Shift.add,
      ~T.filter(~U32, ~U32, ~Unit, ~(unused => x => even(x)),
        ~T.filter(~U32, ~U32, ~Unit,
          ~(unused => x => Bool.not(third(x))),
          ~T.take(~U32, ~U32,
            ~T.map_with(~U32, ~U32, ~U32, ~U32,
              ~Shift.add, ~T.sum())))))),
    (1, (Unit{}, (Unit{}, (n, (2, 0))))), xs)

def generic(xs: List<U32>, n: Nat) -> U32:
  V.transduce(V.comp5(
    V.map_with(~U32, ~U32, ~U32, ~Shift.add, 1),
    V.filter(~U32, ~even),
    V.remove(~U32, ~third),
    V.take(~U32, n),
    V.map_with(~U32, ~U32, ~U32, ~Shift.add, 2)),
    V.sum_rf(), 0, xs)

def once(mode: Nat, xs: List<U32>, n: Nat) -> U32:
  match mode:
    case 0n:
      direct(xs, n, 0)
    case 1n:
      static(xs, n)
    case _:
      generic(xs, n)

def measure(mode: Nat, +size: Nat) -> IO(Nat & U32):
  xs = B.numbers(size, [])
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, once(mode, xs, size))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> size <> rest:
      do IO<Unit>:
        result : Nat & U32 <- measure(B.arg_nat(mode), B.arg_nat(size))
        IO.print(B.show_result(result))
    case _:
      do IO<Unit>:
        result : Nat & U32 <- measure(0n, 20n)
        IO.print(B.show_result(result))

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
