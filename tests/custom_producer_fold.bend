import Base

# These names intentionally differ from List.map and fold_left. They have the
# same checked recursive shapes, so the isolated compiler probe should fuse
# the pipeline structurally rather than by library name.
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

def incremented_sum_step(state: U32, x: U32) -> U32:
  (state + (x + 1 : U32) : U32)

def incremented_hash_step(state: U32, x: U32) -> U32:
  ((state * 33 : U32) + (x + 1 : U32) : U32)

def numbers(n: Nat, acc: List<U32>) -> List<U32>:
  match n:
    case 0n:
      acc
    case 1n++p:
      numbers(p, U32.from_nat(p) <> acc)

def mapped_sum(xs: List<U32>) -> U32:
  fold_values(~U32.add, map_values(~plus_one, xs), 0)

def direct_sum(xs: List<U32>) -> U32:
  fold_values(~incremented_sum_step, xs, 0)

def hash_step(state: U32, x: U32) -> U32:
  ((state * 33 : U32) + x : U32)

def mapped_hash(xs: List<U32>) -> U32:
  fold_values(~hash_step, map_values(~plus_one, xs), 0)

def direct_hash(xs: List<U32>) -> U32:
  fold_values(~incremented_hash_step, xs, 0)

def main() -> Bool & Bool:
  (U32.is_eq(mapped_sum(numbers(4096n, [])),
      direct_sum(numbers(4096n, []))),
   U32.is_eq(mapped_hash(numbers(4096n, [])),
      direct_hash(numbers(4096n, []))))

#|(True{}, True{})
