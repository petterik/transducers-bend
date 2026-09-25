import Base

def nats_to_u32(xs: +List<Nat>) -> +List<U32>:
  match xs:
    case Nil{}:
      Nil{}
    case h <> t:
      U32.from_nat(h) <> nats_to_u32(t)

def is_even(x: U32) -> Bool:
  U32.is_eq(U32.mod(x, 2), 0)

def hash_step(acc: U32, value: U32) -> U32:
  ((acc * 33 : U32) + value : U32)

def filtered_hash(xs: +List<Nat>) -> U32:
  List.foldl(~&2, ~U32, ~U32, ~hash_step,
    List.filter(~U32, ~is_even, nats_to_u32(xs)), 5381)

def main() -> Bool:
  U32.is_eq(filtered_hash([0n, 1n, 2n, 3n, 4n, 5n]), 193377067)
#|True{}
