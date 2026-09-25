import Base
import ../xf.bend as X
import ./array_partition/bench_clock.bend as Clock

# Build the owned input before starting the clock. Each path consumes it once.
def build(n: Nat, +value: U32) -> List<U32>:
  match n:
    case 0n: []
    case 1n+p: value <> build(p, U32.inc(value))

def direct(xs: List<U32>, +sum: U32) -> U32:
  match xs:
    case Nil{}: sum
    case x <> rest: direct(rest, U32.add(sum, U32.inc(x)))

def run(mode: Nat, xs: List<U32>) -> U32:
  match mode:
    case 0n: direct(xs, 0)
    case 1n: X.transduce(X.map(~U32, ~U32, ~U32.inc), X.sum_rf(), 0, xs)
    case _: List.foldl(~&1, ~U32, ~U32, ~U32.add,
      List.map(~U32, ~U32, ~U32.inc, xs), 0)

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
