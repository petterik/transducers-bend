import Base
import ./composable_xf_probe.bend as C
import ./custom_shift.bend as Shift
import ./explicit_reducer_types.bend as E
import ./rank2_static_compose.bend as S
import ./rank2_static_provider.bend as P
import ../../transduce.bend as T
import ../../bench/array_partition/bench_clock.bend as Clock

# The source is prebuilt outside the timed region. All four paths compute
# sum(x + 1) for the first n items of 0..n-1.
def direct(xs: List<U32>, n: Nat, acc: U32) -> U32:
  match xs n:
    case Nil{} n:
      acc
    case h <> t 0n:
      acc
    case h <> t 1n+p:
      direct(t, p, (acc + Shift.add(1, h) : U32))

def current(xs: List<U32>, n: Nat) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.map_with(~U32, ~U32, ~U32, ~U32, ~Shift.add,
      ~T.take(~U32, ~U32, ~T.sum()))),
    (1, (n, 0)), xs)

def staged(xs: List<U32>, n: Nat) -> U32:
  xf = C.compose(
    ~(K => U32 & K), ~(K => T.Configured<U32, K>), ~Shift.code,
    ~(K => Nat & K), ~(K => T.Taking<K>), ~C.take_code,
    Shift.shifted(1), C.taking(n))
  config = C.configure(
    (K => U32 & Nat & K),
    (K => T.Configured<U32, T.Taking<K>>),
    (R => K => S => down =>
      Shift.code(R, Nat & K, T.Taking<S>, C.take_code(R, K, S, down))),
    U32, xf, 0)
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.map_with(~U32, ~U32, ~U32, ~U32, ~Shift.add,
      ~T.take(~U32, ~U32, ~T.sum()))), config, xs)

def generic(xs: List<U32>, n: Nat) -> U32:
  xf = C.compose(
    ~(K => U32 & K), ~(K => T.Configured<U32, K>), ~Shift.code,
    ~(K => Nat & K), ~(K => T.Taking<K>), ~C.take_code,
    Shift.shifted(1), C.taking(n))
  C.run(~U32, ~U32, ~U32,
    ~(K => U32 & Nat & K),
    ~(K => T.Configured<U32, T.Taking<K>>),
    ~(R => K => S => down =>
      Shift.code(R, Nat & K, T.Taking<S>, C.take_code(R, K, S, down))),
    ~E.sum2(), xf, 0, xs)

def rank2(xs: List<U32>, n: Nat) -> U32:
  xf = S.compose(
    (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~down)),
    (R => down => T.take(~U32, ~R, ~down)),
    S.shifted(1), S.taking(n))
  P.run(~(R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~T.take(~U32, ~R, ~down))),
    ~U32, ~T.sum(), xf, 0, xs)

def once(mode: Nat, xs: List<U32>, n: Nat) -> U32:
  match mode:
    case 0n:
      direct(xs, n, 0)
    case 1n:
      current(xs, n)
    case 2n:
      staged(xs, n)
    case 3n:
      generic(xs, n)
    case _:
      rank2(xs, n)

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
