import Base

def plus_one(x: U32) -> U32:
  (x + 1 : U32)

def mapped_values(xs: +List<U32>) -> +List<U32>:
  match xs:
    case Nil{}:
      Nil{}
    case h <> t:
      plus_one(h) <> mapped_values(t)

def is_even(x: U32) -> Bool:
  U32.is_eq(U32.mod(x, 2), 0)

def always_false(x: U32) -> Bool:
  False{}

def sum_step(acc: U32, value: U32) -> U32:
  (acc + value : U32)

def hash_step(acc: U32, value: U32) -> U32:
  ((acc * 33 : U32) + value : U32)

def count_step(acc: U32, value: U32) -> U32:
  (acc + 1 : U32)

def map_filter_sum(xs: +List<U32>) -> U32:
  List.foldl(~&2, ~U32, ~U32, ~sum_step,
    List.filter(~U32, ~is_even,
      mapped_values(xs)), 0)

def map_filter_hash(xs: +List<U32>) -> U32:
  List.foldl(~&2, ~U32, ~U32, ~hash_step,
    List.filter(~U32, ~is_even,
      mapped_values(xs)), 5381)

def map_filter_count(xs: +List<U32>) -> U32:
  List.foldl(~&2, ~U32, ~U32, ~count_step,
    List.filter(~U32, ~is_even,
      mapped_values(xs)), 0)

def map_filter_none(xs: +List<U32>) -> U32:
  List.foldl(~&2, ~U32, ~U32, ~hash_step,
    List.filter(~U32, ~always_false,
      mapped_values(xs)), 5381)

def main() -> Bool & Bool & Bool & Bool & Bool:
  (U32.is_eq(map_filter_sum([0, 1, 2, 3, 4, 5]), 12),
   U32.is_eq(map_filter_hash([0, 1, 2, 3, 4, 5]), 193379313),
   U32.is_eq(map_filter_count([0, 1, 2, 3, 4, 5]), 3),
   U32.is_eq(map_filter_none([0, 1, 2, 3, 4, 5]), 5381),
   U32.is_eq(map_filter_hash([]), 5381))
#|(True{}, True{}, True{}, True{}, True{})
