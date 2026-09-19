# Experimental scalar specialization of map/filter/take/sum, not a public API.
# Keeps the original initializer, completion, state representation and driver.
import Base
import ../transduce.bend as T

def work(n: Nat, +x: U32) -> U32:
  match n:
    case 0n:
      x
    case 1n+p:
      work(p, (U32.xor(U32.mul(x, 1664525), U32.shrn(x, 13n)) + 1013904223 : U32))

def cheap(+x: U32) -> U32:
  (U32.xor(x, U32.shrn(x, 13n)) + 1 : U32)

# The runner substitutes expensive work in this one definition.
def transform(x: U32) -> U32:
  cheap(x)

def above(t: U32, x: U32) -> Bool:
  U32.is_gt(x, t)

def base_pipeline() -> T.Reducer<U32, U32>:
  T.map(~U32, ~U32, ~U32, ~transform,
      ~T.filter(~U32, ~U32, ~U32, ~above, ~T.take(~U32, ~U32, ~T.sum())))

def scalar_control(stop: Bool, state: T.Configured<U32, T.Taking<U32>>) -> T.Control<T.Configured<U32, T.Taking<U32>>>:
  match stop:
    case True{}:
      T.Stop{state}
    case False{}:
      T.Continue{state}

def scalar_positive(+p: Nat, +threshold: U32, +sum: U32, +x: U32) -> T.Control<T.Configured<U32, T.Taking<U32>>>:
  +yes = above(threshold, x)
  scalar_control(Bool.and(yes, Nat.is_eq(p, 0n)),
    T.Configured{threshold, T.Taking{Bool.pick(Nat, yes, p, 1n+p),
      T.Continue{Bool.pick(U32, yes, (sum + x : U32), sum)}}})

def scalar_filter(+threshold: U32, state: T.Taking<U32>, +x: U32) -> T.Control<T.Configured<U32, T.Taking<U32>>>:
  match state:
    case T.Taking{0n, T.Continue{sum}}:
      scalar_control(above(threshold, x), T.Configured{threshold, T.Taking{0n, T.Continue{sum}}})
    case T.Taking{1n+p, T.Continue{sum}}:
      scalar_positive(p, threshold, sum, x)
    case T.Taking{n, T.Stop{sum}}:
      scalar_control(above(threshold, x), T.Configured{threshold, T.Taking{n, T.Stop{sum}}})

def scalar_step(state: T.Configured<U32, T.Taking<U32>>, x: U32) -> T.Control<T.Configured<U32, T.Taking<U32>>>:
  match state:
    case T.Configured{threshold, inner}:
      scalar_filter(threshold, inner, transform(x))

def pipeline() -> T.Reducer<U32, U32>:
  T.Reducer{T.Config(U32, U32, base_pipeline()), T.State(U32, U32, base_pipeline()),
    c => T.start(U32, U32, base_pipeline(), c),
    s => x => scalar_step(s, x),
    s => T.finish(U32, U32, base_pipeline(), s)}

type Running is Type:
  Running{left: Nat, acc: U32}

def keep(yes: Bool, left: Nat, acc: U32, x: U32) -> Running:
  match yes left:
    case False{} n:
      Running{n, acc}
    case True{} 0n:
      Running{0n, acc}
    case True{} 1n+p:
      Running{p, (acc + x : U32)}

def feed(threshold: U32, left: Nat, acc: U32, +x: U32) -> Running:
  keep(above(threshold, x), left, acc, x)

def direct(n: Nat, +x: U32, state: Running, +threshold: U32) -> U32:
  match n state:
    case n Running{0n, acc}:
      acc
    case 0n Running{left, acc}:
      acc
    case 1n+p Running{1n+k, acc}:
      direct(p, (x + 1 : U32), feed(threshold, 1n+k, acc, transform(x)), threshold)

def main() -> U32:
  T.transduce(~T.over_range(~U32, ~pipeline()), (1, (2n, 0)), T.range_between(0, 5))
#|5
