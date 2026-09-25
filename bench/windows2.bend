import Base
import ../xf.bend as X
import ./array_partition/bench_clock.bend as Clock

def build(n: Nat, +value: U32) -> List<U32>:
  match n:
    case 0n: []
    case 1n+p: value <> build(p, U32.inc(value))

def direct(xs: List<U32>, previous: Maybe<U32>, sum: U32) -> U32:
  match xs previous:
    case Nil{} previous: sum
    case x <> rest None{}: direct(rest, Some{x}, sum)
    case +x <> rest Some{previous}:
      direct(rest, Some{x}, U32.add(sum, U32.add(previous, x)))

def pair_sum(pair: U32 & U32) -> U32:
  (a, b) = pair
  U32.add(a, b)

def list_pair_sum(xs: List<U32>) -> U32:
  match xs:
    case a <> b <> Nil{}: U32.add(a, b)
    case _: 0

def list_windows(xs: List<U32>) -> U32:
  X.transduce(X.comp2(X.windows(~U32, 2n),
    X.map(~List<U32>, ~U32, ~list_pair_sum)), X.sum_rf(), 0, xs)

def tuple_windows(xs: List<U32>) -> U32:
  X.transduce(X.comp2(X.window2(~U32),
    X.map(~(U32 & U32), ~U32, ~pair_sum)), X.sum_rf(), 0, xs)

def run(mode: Nat, xs: List<U32>) -> U32:
  match mode:
    case 0n: direct(xs, None{}, 0)
    case 1n: list_windows(xs)
    case _: tuple_windows(xs)

def parsed(value: Maybe<&2, Nat>) -> Nat:
  match value:
    case None{}: 0n
    case Some{n}: n

def measure(mode: Nat, count: Nat) -> IO(Unit):
  xs = build(count, 0)
  do IO<Unit>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, run(mode, xs))
    after : Nat <- Clock.now_us()
    IO.print(String.append(Nat.show(Nat.sub(after, before)),
      String.append(" ", U32.show(answer))))

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> count <> rest:
      measure(parsed(Nat.read(mode)), parsed(Nat.read(count)))
    case _:
      measure(2n, 65536n)

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
