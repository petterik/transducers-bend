import Base
import ../../transduce.bend as T

# Dynamic List map/fold comparison. The mapped List is built recursively from
# a runtime loop count, so its constructor spine is not a small static term.
# The transducer lane maps each item directly into the downstream reducer.
def inc(x: U32) -> U32:
  (x + 1 : U32)

def hash_step(s: U32, x: U32) -> U32:
  ((s * 33 : U32) + x : U32)

def fold_left(~step: U32 -> U32 -> U32,
  xs: List<U32>, +s: U32) -> U32:
  match xs:
    case Nil{}:
      s
    case h <> t:
      fold_left(~step, t, step(s, h))

def numbers(n: Nat, acc: List<U32>) -> List<U32>:
  match n:
    case 0n:
      acc
    case 1n++p:
      numbers(p, U32.from_nat(p) <> acc)

def materialized_sum(xs: List<U32>) -> U32:
  fold_left(~U32.add, List.map(~U32, ~U32, ~inc, xs), 0)

def stream_sum(xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.map(~U32, ~U32, ~U32, ~inc,
      ~T.reducing(~U32, ~U32, ~U32, ~U32.add, ~(s => s)))),
    0, xs)

def materialized_hash(xs: List<U32>) -> U32:
  fold_left(~hash_step, List.map(~U32, ~U32, ~inc, xs), 0)

def stream_hash(xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.map(~U32, ~U32, ~U32, ~inc,
      ~T.reducing(~U32, ~U32, ~U32, ~hash_step, ~(s => s)))),
    0, xs)

def main() -> Bool & Bool:
  (U32.is_eq(materialized_sum(numbers(4096n, [])),
      stream_sum(numbers(4096n, []))),
   U32.is_eq(materialized_hash(numbers(4096n, [])),
      stream_hash(numbers(4096n, []))))
