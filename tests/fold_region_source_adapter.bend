import Base

# A small independent source adapter builds a runtime-sized List from a Nat.
# Fusion may remove the mapped List after the adapter, but must keep this
# source representation and item order intact.
def plus_one(x: U32) -> U32:
  (x + 1 : U32)

def map_values(~f: U32 -> U32, xs: List<U32>) -> List<U32>:
  match xs:
    case Nil{}:
      []
    case h <> t:
      f(h) <> map_values(~f, t)

def fold_values(~step: U32 -> U32 -> U32,
  xs: List<U32>, +state: U32) -> U32:
  match xs:
    case Nil{}:
      state
    case h <> t:
      fold_values(~step, t, step(state, h))

def range_list(n: Nat, acc: List<U32>) -> List<U32>:
  match n:
    case 0n:
      acc
    case 1n++p:
      range_list(p, U32.from_nat(p) <> acc)

def incremented_sum_step(state: U32, x: U32) -> U32:
  (state + (x + 1 : U32) : U32)

def hash_step(state: U32, x: U32) -> U32:
  ((state * 33 : U32) + x : U32)

def incremented_hash_step(state: U32, x: U32) -> U32:
  ((state * 33 : U32) + (x + 1 : U32) : U32)

def mapped_sum(n: Nat) -> U32:
  fold_values(~U32.add,
    map_values(~plus_one, range_list(n, [])), 0)

def direct_sum(n: Nat) -> U32:
  fold_values(~incremented_sum_step, range_list(n, []), 0)

def mapped_hash(n: Nat) -> U32:
  fold_values(~hash_step,
    map_values(~plus_one, range_list(n, [])), 0)

def direct_hash(n: Nat) -> U32:
  fold_values(~incremented_hash_step, range_list(n, []), 0)

def main() -> Bool & Bool:
  (U32.is_eq(mapped_sum(4096n), direct_sum(4096n)),
   U32.is_eq(mapped_hash(4096n), direct_hash(4096n)))

#|(True{}, True{})
