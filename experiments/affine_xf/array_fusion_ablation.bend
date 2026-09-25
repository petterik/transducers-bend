import Base
import ./companion_matrix_bench.bend as Matrix
import ./static_recipe_bench.bend as B
import ../../transduce.bend as T
import ../../bench/array_partition/bench_clock.bend as Clock

# These five paths traverse and sum the same ordered Array. They separate
# expression shape, stopping Control, reducer composition, and public source
# companion selection.
def direct_inc(xs: Array<U32>, acc: U32) -> U32:
  match xs:
    case ALeaf{x}:
      (acc + U32.inc(x) : U32)
    case ANode{left, right}:
      direct_inc(right, direct_inc(left, acc))

def finish_control(c: T.Control<U32>) -> U32:
  match c:
    case T.Continue{s}:
      s
    case T.Stop{s}:
      s

def control_fold(xs: Array<U32>) -> U32:
  finish_control(T.reduce_array(~U32, ~U32,
    ~(s => x => T.Continue{(s + U32.inc(x) : U32)}),
    xs, T.Continue{0}))

def static_fold(xs: Array<U32>) -> U32:
  T.transduce(~T.over_array(~U32, ~U32,
    ~T.map(~U32, ~U32, ~U32, ~U32.inc, ~T.sum())), 0, xs)

def choose(mode: Nat, xs: Array<U32>) -> U32:
  match mode:
    case 0n: Matrix.array_direct(xs, 0)
    case 1n: direct_inc(xs, 0)
    case 2n: control_fold(xs)
    case 3n: static_fold(xs)
    case _: Matrix.array_generic(xs)

def measure(mode: Nat, depth: Nat) -> IO(Nat & U32):
  xs = Array.new(U32, depth, 1)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, choose(mode, xs))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> depth <> rest:
      do IO<Unit>:
        result : Nat & U32 <- measure(B.arg_nat(mode), B.arg_nat(depth))
        IO.print(B.show_result(result))
    case _:
      do IO<Unit>:
        result : Nat & U32 <- measure(4n, 4n)
        IO.print(B.show_result(result))

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
