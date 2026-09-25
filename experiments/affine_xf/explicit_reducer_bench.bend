import Base
import ./explicit_reducer_types.bend as E
import ../../transduce.bend as T
import ../../bench/array_partition/bench_clock.bend as Clock

def direct(xs: List<U32>, n: Nat, acc: U32) -> U32:
  match xs n:
    case Nil{} n:
      acc
    case h <> t 0n:
      acc
    case h <> t 1n+p:
      direct(t, p, (acc + E.plus_one(h) : U32))

def old_static(xs: List<U32>, n: Nat) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.take(~U32, ~U32,
      ~T.map(~U32, ~U32, ~U32, ~E.plus_one, ~T.sum()))),
    (n, 0), xs)

def explicit(xs: List<U32>, n: Nat) -> U32:
  xf : E.Xf<U32, U32, E.plus_one> = E.Xf{n}
  E.run(~U32, ~U32, ~U32, ~U32, ~U32,
    ~E.plus_one, ~E.sum2(), xf, 0, xs)

def once(mode: Nat, xs: List<U32>, n: Nat) -> U32:
  match mode:
    case 0n:
      direct(xs, n, 0)
    case 1n:
      old_static(xs, n)
    case _:
      explicit(xs, n)

def numbers(n: Nat, acc: List<U32>) -> List<U32>:
  match n:
    case 0n:
      acc
    case 1n++p:
      numbers(p, U32.from_nat(p) <> acc)

def measure(mode: Nat, +size: Nat) -> IO(Nat & U32):
  xs = numbers(size, [])
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, once(mode, xs, size))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def parsed(value: Maybe<&2, Nat>) -> Nat:
  match value:
    case None{}:
      0n
    case Some{n}:
      n

def arg_nat(value: String) -> Nat:
  parsed(Nat.read(value))

def show_result(result: Nat & U32) -> String:
  (elapsed, answer) = result
  String.append(Nat.show(elapsed), String.append(" ", U32.show(answer)))

def run_measure(mode: Nat, size: Nat) -> IO(Unit):
  do IO<Unit>:
    result : Nat & U32 <- measure(mode, size)
    IO.print(show_result(result))

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
