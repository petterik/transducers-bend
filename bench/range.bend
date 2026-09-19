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

def pipeline() -> T.Reducer<U32, U32>:
  T.map(~U32, ~U32, ~U32, ~transform,
    ~T.filter(~U32, ~U32, ~U32, ~above, ~T.take(~U32, ~U32, ~T.sum())))

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

def feed(left: Nat, acc: U32, +x: U32) -> Running:
  keep(U32.is_gt(x, 1), left, acc, x)

def direct(n: Nat, +x: U32, state: Running) -> U32:
  match n state:
    case n Running{0n, acc}:
      acc
    case 0n Running{left, acc}:
      acc
    case 1n+p Running{1n+k, acc}:
      direct(p, (x + 1 : U32), feed(1n+k, acc, transform(x)))

def main() -> U32:
  T.transduce(~T.over_range(~U32, ~pipeline()), (1, (2n, 0)), T.range_between(0, 5))
#|5
