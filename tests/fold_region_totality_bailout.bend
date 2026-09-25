import Base

# These callbacks produce ordinary results for the finite inputs below, but
# their termination / overflow safety is not a compiler fact. FoldRegion must
# retain the checked materializing program instead of moving them into a loop.
def map_nats(~f: Nat -> Nat, xs: +List<Nat>) -> +List<Nat>:
  match xs:
    case Nil{}:
      Nil{}
    case h <> t:
      f(h) <> map_nats(~f, t)

def count_step(acc: U32, value: Nat) -> U32:
  U32.add(acc, 1)

def count_nats(xs: List<&2, Nat>, +acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case h <> t:
      count_nats(t, count_step(acc, h))

def recursive_zero(x: Nat) -> Nat:
  match x:
    case 0n:
      0n
    case 1n+p:
      recursive_zero(p)

def multiply_by_five(x: Nat) -> Nat:
  Nat.mul(5n, x)

def map_u32(~f: U32 -> U32, xs: +List<U32>) -> +List<U32>:
  match xs:
    case Nil{}:
      Nil{}
    case h <> t:
      f(h) <> map_u32(~f, t)

def shift_by_32(x: U32) -> U32:
  U32.shln(x, 32n)

def count_u32_step(acc: U32, value: U32) -> U32:
  U32.add(acc, 1)

def count_u32(xs: List<&2, U32>, +acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case h <> t:
      count_u32(t, count_u32_step(acc, h))

def main() -> Bool & Bool & Bool:
  (U32.is_eq(count_nats(map_nats(~recursive_zero, [3n, 2n, 1n]), 0), 3),
   U32.is_eq(count_nats(map_nats(~multiply_by_five, [1n, 2n, 3n]), 0), 3),
   U32.is_eq(count_u32(map_u32(~shift_by_32, [1, 2, 3]), 0), 3))
#|(True{}, True{}, True{})
