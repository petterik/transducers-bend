import Base
import ../xf.bend as X
import ./array_partition/bench_clock.bend as Clock

def build(n: Nat, +value: U32) -> List<U32>:
  match n:
    case 0n: []
    case 1n+p: value <> build(p, U32.inc(value))

def indexed(index: Nat, value: U32) -> U32:
  U32.add(value, U32.from_nat(index))

# Equivalent to drop(32), map_indexed(indexed), take_nth(3), and sum.
# The direct version has a separate prefix-skip loop and a steady-state loop.
def direct_steady(xs: List<U32>, +index: Nat,
  nth_left: Nat, +sum: U32) -> U32:
  match xs nth_left:
    case Nil{} nth_left:
      sum
    case x <> rest 0n:
      direct_steady(rest, 1n+index, 2n,
        U32.add(sum, indexed(index, x)))
    case x <> rest 1n+p:
      direct_steady(rest, 1n+index, p, sum)

def direct_skip(xs: List<U32>, drop_left: Nat) -> U32:
  match xs drop_left:
    case Nil{} drop_left:
      0
    case x <> rest 1n+p:
      direct_skip(rest, p)
    case x <> rest 0n:
      direct_steady(x <> rest, 0n, 0n, 0)

def pipeline(xs: List<U32>) -> U32:
  X.transduce(X.comp3(X.drop(~U32, 32n),
    X.map_indexed(~U32, ~U32, ~indexed),
    X.take_nth(~U32, 3n)), X.sum_rf(), 0, xs)

def run(mode: Nat, xs: List<U32>) -> U32:
  match mode:
    case 0n: direct_skip(xs, 32n)
    case _: pipeline(xs)

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
      measure(1n, 65536n)

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
