import Base
import ../xf.bend as X
import ./array_partition/bench_clock.bend as Clock

# The public Array.source now uses Array.get, a flat indexed read.

def input_value(i: U32, seed: U32) -> U32:
  U32.add(U32.mul(i, 1664525), seed)

def transform_go(+x: U32) -> U32:
  +a = U32.mul(x, 2654435761)
  +b = U32.xor(a, U32.shrn(a, 16n))
  +c = U32.mul(b, 2246822507)
  U32.xor(c, U32.shrn(c, 13n))

def transform(x: U32) -> U32:
  transform_go(x)

def keep(x: U32) -> Bool:
  U32.is_lt(U32.and(x, 255), 96)

def add_kept(acc: U32, x: U32, flag: Bool) -> U32:
  match flag:
    case True{}: U32.add(acc, x)
    case False{}: acc

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

def transducer(xs: Array<U32>) -> U32:
  X.transduce(X.comp2(X.map(~U32, ~U32, ~transform),
    X.filter(~U32, ~keep)), X.sum_rf(), 0, xs)

def direct_step(got: Array<U32> & U32, acc: U32) -> Array<U32> & U32:
  (xs, value) = got
  +mapped = transform(value)
  (xs, add_kept(acc, mapped, keep(mapped)))

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

def keep_list(value: U32, rest: List<U32>, flag: Bool) -> List<U32>:
  match flag:
    case True{}: value <> rest
    case False{}: rest

def filter_list(xs: List<U32>) -> List<U32>:
  match xs:
    case Nil{}: Nil{}
    case +value <> rest:
      keep_list(value, filter_list(rest), keep(value))

def mask_go(+x: U32) -> U32:
  add_kept(0, x, keep(x))

def mask(x: U32) -> U32:
  mask_go(x)

def sum_step(got: Array<U32> & U32, acc: U32) -> Array<U32> & U32:
  (xs, value) = got
  (xs, U32.add(acc, value))

def sum_loop(left: Nat, pair: Array<U32> & U32, +index: U32) -> U32:
  match left:
    case 0n:
      (xs, acc) = pair
      acc
    case 1n+p:
      (xs, acc) = pair
      sum_loop(p, sum_step(Array.get(U32, xs, index), acc),
        U32.inc(index))

def sum_sized(sized: Array<U32> & U32) -> U32:
  (xs, count) = sized
  sum_loop(U32.to_nat(count), (xs, 0), 0)

def array_mask(xs: Array<U32>) -> U32:
  mapped = Array.map(~U32, ~U32, ~transform, xs)
  masked = Array.map(~U32, ~U32, ~mask, mapped)
  sum_sized(Array.size(U32, masked))

def list_materialized(xs: Array<U32>) -> U32:
  mapped = Array.map(~U32, ~U32, ~transform, xs)
  values = Array.to_list(~U32, mapped)
  kept = filter_list(values)
  List.foldl(~&1, ~U32, ~U32, ~U32.add, kept, 0)

def run(mode: Nat, xs: Array<U32>) -> U32:
  match mode:
    case 0n: transducer(xs)
    case 1n: direct(xs)
    case 2n: array_mask(xs)
    case _: list_materialized(xs)

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
