import Base

def identity_array(x: Array<U32>) -> Array<U32>:
  x

def map_arrays(~f: Array<U32> -> Array<U32>,
  xs: List<Array<U32>>) -> List<Array<U32>>:
  match xs:
    case Nil{}:
      []
    case h <> t:
      f(h) <> map_arrays(~f, t)

def fold_arrays(~step: U32 -> Array<U32> -> U32,
  xs: List<Array<U32>>, +state: U32) -> U32:
  match xs:
    case Nil{}:
      state
    case h <> t:
      fold_arrays(~step, t, step(state, h))

def count_step(state: U32, array: Array<U32>) -> U32:
  (state + 1 : U32)

def fresh_arrays(n: Nat, acc: List<Array<U32>>) -> List<Array<U32>>:
  match n:
    case 0n:
      acc
    case 1n++p:
      array = [0 : U32*2n]
      fresh_arrays(p, array <> acc)

def mapped_count(n: Nat) -> U32:
  fold_arrays(~count_step,
    map_arrays(~identity_array, fresh_arrays(n, [])), 0)

def direct_count(n: Nat) -> U32:
  fold_arrays(~count_step, fresh_arrays(n, []), 0)

def main() -> Bool:
  U32.is_eq(mapped_count(128n), direct_count(128n))

#|True{}
