import Base
import ../xf.bend as X
import ./array_partition/bench_clock.bend as Clock

def input_value(i: U32, seed: U32) -> U32:
  U32.add(U32.mul(i, 1664525), seed)

def build_loop(left: Nat, +index: U32, +seed: U32,
  xs: Array<U32>) -> Array<U32>:
  match left:
    case 0n: xs
    case 1n+p:
      build_loop(p, U32.inc(index), seed,
        Array.set(U32, xs, index, input_value(index, seed)))

def build(+depth: Nat, seed: U32) -> Array<U32>:
  count = U32.shln(1, depth)
  build_loop(U32.to_nat(count), 0, seed, Array.new(U32, depth, 0))

# Clojure: (transduce (map inc) + 0 xs)
def transducer(xs: Array<U32>) -> U32:
  X.transduce(X.map(~U32, ~U32, ~U32.inc), X.sum_rf(), 0, xs)

def direct_step(got: Array<U32> & U32, acc: U32) -> Array<U32> & U32:
  (xs, value) = got
  (xs, U32.add(acc, U32.inc(value)))

def direct_loop(left: Nat, pair: Array<U32> & U32, +index: U32) -> U32:
  match left:
    case 0n:
      (xs, acc) = pair
      acc
    case 1n+p:
      (xs, acc) = pair
      direct_loop(p, direct_step(Array.get(U32, xs, index), acc),
        U32.inc(index))

def direct_sized(sized: Array<U32> & U32) -> U32:
  (xs, count) = sized
  direct_loop(U32.to_nat(count), (xs, 0), 0)

def direct(xs: Array<U32>) -> U32:
  direct_sized(Array.size(U32, xs))

def run(mode: Nat, xs: Array<U32>) -> U32:
  match mode:
    case 0n: transducer(xs)
    case _: direct(xs)

def parsed_nat(value: Maybe<&2, Nat>) -> Nat:
  match value:
    case None{}: 0n
    case Some{n}: n

def parsed_u32(value: Maybe<&2, U32>) -> U32:
  match value:
    case None{}: 0
    case Some{n}: n

def measure(mode: Nat, depth: Nat, seed: U32) -> IO(Unit):
  xs = build(depth, seed)
  do IO<Unit>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, run(mode, xs))
    after : Nat <- Clock.now_us()
    IO.print(Nat.show(Nat.sub(after, before)) ++ " " ++ U32.show(answer))

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> depth <> seed <> rest:
      measure(parsed_nat(Nat.read(mode)), parsed_nat(Nat.read(depth)),
        parsed_u32(U32.read(seed)))
    case _:
      measure(0n, 16n, 12345)

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
