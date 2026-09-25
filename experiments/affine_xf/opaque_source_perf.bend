import Base
import ../../xf_legacy.bend as Xf
import ../../transduce.bend as T
import ../../bench/array_partition/bench_clock.bend as Clock
import ./static_recipe_bench.bend as B

type ProbePair is Type:
  ProbePair{first: U32, second: U32}

def pair_after(~S: Type, ~advance: S -> U32 -> S,
  second: U32, checked: T.Checked<S>) -> S:
  match checked:
    case T.Halted{s}:
      s
    case T.Ready{s}:
      advance(s, second)

def pair_checked(~S: Type, ~advance: S -> U32 -> S,
  ~inspect: S -> T.Checked<S>, pair: ProbePair,
  checked: T.Checked<S>) -> S:
  match pair checked:
    case ProbePair{first, second} T.Halted{s}:
      s
    case ProbePair{first, second} T.Ready{s}:
      pair_after(~S, ~advance, second, inspect(advance(s, first)))

def pair_drive(~S: Type, ~advance: S -> U32 -> S,
  ~inspect: S -> T.Checked<S>, pair: ProbePair, s: S) -> S:
  pair_checked(~S, ~advance, ~inspect, pair, inspect(s))

def make_pair(+x: U32) -> ProbePair:
  ProbePair{x, (x + 10 : U32)}

def direct(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case +x <> t:
      direct(t, (acc + x + x + 10 : U32))

def public(xs: List<U32>) -> U32:
  Xf.transduce(Xf.mapcat(~U32, ~U32, ~ProbePair,
    ~(S => advance => inspect => pair => s =>
      pair_drive(~S, ~advance, ~inspect, pair, s)),
    ~(x => make_pair(x))), Xf.sum_rf(), 0, xs)

def public_list(xs: List<U32>) -> U32:
  Xf.transduce(Xf.map(~U32, ~U32, ~U32.inc),
    Xf.sum_rf(), 0, xs)

def direct_list(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case x <> t:
      direct_list(t, (acc + x + 1 : U32))

def direct_array(xs: Array<U32>, acc: U32) -> U32:
  match xs:
    case ALeaf{x}:
      (acc + x + 1 : U32)
    case ANode{left, right}:
      direct_array(right, direct_array(left, acc))

def total_step(acc: U32, x: U32) -> U32:
  (acc + x + 1 : U32)

def total_inspect(s: U32) -> T.Checked<U32>:
  T.Ready{s}

def total_array(xs: Array<U32>) -> U32:
  T.source_array(~U32, ~U32, ~total_step, ~total_inspect, xs, 0)

def total_list(xs: List<U32>) -> U32:
  T.source_list(~U32, ~U32, ~total_step, ~total_inspect, xs, 0)

def choose_array(mode: Nat, xs: Array<U32>) -> U32:
  match mode:
    case 4n:
      direct_array(xs, 0)
    case 6n:
      total_array(xs)
    case _:
      Xf.transduce(Xf.map(~U32, ~U32, ~U32.inc),
        Xf.sum_rf(), 0, xs)

def choose(mode: Nat, xs: List<U32>) -> U32:
  match mode:
    case 0n:
      direct(xs, 0)
    case 1n:
      public(xs)
    case 2n:
      direct_list(xs, 0)
    case 7n:
      total_list(xs)
    case _:
      public_list(xs)

def measure(mode: Nat, n: Nat) -> IO(Nat & U32):
  xs = B.numbers(n, [])
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, choose(mode, xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def measure_array(mode: Nat, depth: Nat) -> IO(Nat & U32):
  xs = Array.new(U32, depth, 1)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, choose_array(mode, xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def choose_measure(mode: Nat, n: Nat) -> IO(Nat & U32):
  match mode:
    case 4n:
      measure_array(mode, n)
    case 5n:
      measure_array(mode, n)
    case 6n:
      measure_array(mode, n)
    case _:
      measure(mode, n)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> size <> rest:
      do IO<Unit>:
        result : Nat & U32 <- choose_measure(B.arg_nat(mode), B.arg_nat(size))
        IO.print(B.show_result(result))
    case _:
      IO.print("usage: mode size")

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
