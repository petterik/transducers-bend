import Base

def plus_one(x: U32) -> U32:
  (x + 1 : U32)

def map_values(~f: U32 -> U32, xs: List<U32>) -> List<U32>:
  match xs:
    case Nil{}:
      []
    case h <> t:
      f(h) <> map_values(~f, t)

def closure_plus_one(x: U32) -> U32:
  add = U32.add(x)
  add(1)

@unsafe def unsafe_plus_one(x: U32) -> U32:
  (x + 1 : U32)

def fold_values(~step: U32 -> U32 -> U32,
  xs: List<U32>, +state: U32) -> U32:
  match xs:
    case Nil{}:
      state
    case h <> t:
      fold_values(~step, t, step(state, h))

def numbers(n: Nat, acc: List<U32>) -> List<U32>:
  match n:
    case 0n:
      acc
    case 1n++p:
      numbers(p, U32.from_nat(p) <> acc)

# This List escapes the producer call and is consumed by a different operation.
# A producer/fold rewrite must leave this materialization alone.
def retained(xs: List<U32>) -> List<U32>:
  map_values(~plus_one, xs)

def mapped_length(xs: List<U32>) -> Nat:
  List.length(&1, U32, map_values(~plus_one, xs))

def closure_mapped_sum(xs: List<U32>) -> U32:
  fold_values(~U32.add, map_values(~closure_plus_one, xs), 0)

def unsafe_mapped_sum(xs: List<U32>) -> U32:
  fold_values(~U32.add, map_values(~unsafe_plus_one, xs), 0)

def main() -> Bool & Bool & Bool & Bool:
  (Nat.is_eq(List.length(&1, U32,
      retained(numbers(8n, []))), 8n),
   Nat.is_eq(mapped_length(numbers(8n, [])), 8n),
   U32.is_eq(closure_mapped_sum(numbers(8n, [])), 36),
   U32.is_eq(unsafe_mapped_sum(numbers(8n, [])), 36))

#|(True{}, True{}, True{}, True{})
