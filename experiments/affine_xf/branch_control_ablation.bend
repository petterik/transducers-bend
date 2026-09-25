import Base
import ../../transduce.bend as T
import ../../bench/array_partition/bench_clock.bend as Clock
import ./static_recipe_bench.bend as B

# An independently defined branching source; neither an Array nor a List.
type Branch is Type:
  Tip{value: U32}
  Fork{left: Branch, right: Branch}

def build(depth: Nat, +seed: U32) -> Branch:
  match depth:
    case 0n:
      Tip{seed}
    case 1n++p:
      Fork{build(p, (seed * 2 : U32)), build(p, ((seed * 2 : U32) + 1 : U32))}

def direct(xs: Branch, acc: U32) -> U32:
  match xs:
    case Tip{x}:
      (acc + U32.inc(x) : U32)
    case Fork{left, right}:
      direct(right, direct(left, acc))

def control(xs: Branch, c: T.Control<U32>) -> T.Control<U32>:
  match xs c:
    case Tip{x} T.Stop{s}:
      T.Stop{s}
    case Tip{x} T.Continue{s}:
      T.Continue{(s + U32.inc(x) : U32)}
    case Fork{left, right} T.Stop{s}:
      T.Stop{s}
    case Fork{left, right} T.Continue{s}:
      control(right, control(left, T.Continue{s}))

def finish(c: T.Control<U32>) -> U32:
  match c:
    case T.Continue{s}: s
    case T.Stop{s}: s

def direct_take_tip(done: Bool, x: U32, left: U32, sum: U32) -> U32 & U32:
  match done:
    case True{}: (left, sum)
    case False{}: ((left - 1 : U32), (sum + U32.inc(x) : U32))

def direct_take(xs: Branch, state: U32 & U32) -> U32 & U32:
  match xs state:
    case Tip{x} state:
      (+left, sum) = state
      direct_take_tip(U32.is_eq(left, 0), x, left, sum)
    case Fork{a, b} state:
      (+left, sum) = state
      match left:
        case 0:
          (left, sum)
        case _:
          direct_take(b, direct_take(a, (left, sum)))

def control_take_tip(done: Bool, x: U32, left: U32, sum: U32) -> T.Control<(U32 & U32)>:
  match done:
    case True{}: T.Stop{(left, sum)}
    case False{}: T.Continue{((left - 1 : U32), (sum + U32.inc(x) : U32))}

def control_take(xs: Branch, c: T.Control<(U32 & U32)>) -> T.Control<(U32 & U32)>:
  match xs c:
    case Tip{x} T.Stop{s}:
      T.Stop{s}
    case Tip{x} T.Continue{(+left, sum)}:
      control_take_tip(U32.is_eq(left, 0), x, left, sum)
    case Fork{a, b} T.Stop{s}:
      T.Stop{s}
    case Fork{a, b} T.Continue{s}:
      control_take(b, control_take(a, T.Continue{s}))

def finish_take(c: T.Control<(U32 & U32)>) -> U32:
  match c:
    case T.Continue{(left, sum)}: sum
    case T.Stop{(left, sum)}: sum

def finish_direct_take(state: U32 & U32) -> U32:
  (left, sum) = state
  sum

def choose(mode: Nat, xs: Branch, limit: U32) -> U32:
  match mode:
    case 0n: direct(xs, 0)
    case 1n: finish(control(xs, T.Continue{0}))
    case 2n:
      finish_direct_take(direct_take(xs, (limit, 0)))
    case 3n: finish_take(control_take(xs, T.Continue{(limit, 0)}))
    case _: finish_take(control_take(xs, T.Stop{(limit, 0)}))

def measure(mode: Nat, depth: Nat, limit: U32) -> IO(Nat & U32):
  xs = build(depth, 1)
  do IO<Nat & U32>:
    before : Nat <- Clock.now_us()
    answer : U32 <- IO.pure(U32, choose(mode, xs, limit))
    after : Nat <- Clock.now_us()
    return (Nat.sub(after, before), answer)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case mode <> depth <> limit <> rest:
      do IO<Unit>:
        result : Nat & U32 <- measure(B.arg_nat(mode), B.arg_nat(depth), U32.from_nat(B.arg_nat(limit)))
        IO.print(B.show_result(result))
    case _:
      do IO<Unit>:
        result : Nat & U32 <- measure(1n, 4n, 5)
        IO.print(B.show_result(result))

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
