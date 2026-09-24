import Base

def some_value(x: U32) -> Maybe<U32>:
  Some{x}

def no_value(x: U32) -> Maybe<U32>:
  None{}

def bool_value(x: Bool) -> Maybe<U32>:
  match x:
    case False{}:
      None{}
    case True{}:
      Some{42}

def sum_option(acc: U32, value: Maybe<U32>) -> U32:
  match value:
    case None{}:
      acc
    case Some{x}:
      (acc + x : U32)

def hash_option(acc: U32, value: Maybe<U32>) -> U32:
  match value:
    case None{}:
      acc
    case Some{x}:
      ((acc * 33 : U32) + x : U32)

def wrap_array(value: Array<U32>) -> Maybe<Array<U32>>:
  Some{value}

def count_maybe_array(acc: U32, value: Maybe<Array<U32>>) -> U32:
  match value:
    case None{}:
      acc
    case Some{array}:
      (acc + 1 : U32)

def affine_array_source() -> List<Array<U32>>:
  first = [1 : U32*1n]
  second = [2 : U32*1n]
  [first, second]

def mapped_sum(xs: List<U32>) -> U32:
  List.foldl(~&1, ~Maybe<U32>, ~U32, ~sum_option,
    List.map(~U32, ~Maybe<U32>, ~some_value, xs), 0)

def mapped_sum_let(xs: List<U32>) -> U32:
  values = List.map(~U32, ~Maybe<U32>, ~some_value, xs)
  List.foldl(~&1, ~Maybe<U32>, ~U32, ~sum_option, values, 0)

def mapped_none_sum(xs: List<U32>) -> U32:
  List.foldl(~&1, ~Maybe<U32>, ~U32, ~sum_option,
    List.map(~U32, ~Maybe<U32>, ~no_value, xs), 0)

def mapped_bool_sum(xs: List<Bool>) -> U32:
  List.foldl(~&1, ~Maybe<U32>, ~U32, ~sum_option,
    List.map(~Bool, ~Maybe<U32>, ~bool_value, xs), 0)

def mapped_hash(xs: List<U32>) -> U32:
  List.foldl(~&1, ~Maybe<U32>, ~U32, ~hash_option,
    List.map(~U32, ~Maybe<U32>, ~some_value, xs), 0)

def mapped_array_count(xs: List<Array<U32>>) -> U32:
  List.foldl(~&1, ~Maybe<Array<U32>>, ~U32, ~count_maybe_array,
    List.map(~Array<U32>, ~Maybe<Array<U32>>, ~wrap_array, xs), 0)

def main() -> Bool & Bool & Bool & Bool & Bool & Bool & Bool:
  (U32.is_eq(mapped_sum([1, 2, 3]), 6),
   U32.is_eq(mapped_sum_let([1, 2, 3]), 6),
   U32.is_eq(mapped_none_sum([1, 2, 3]), 0),
   U32.is_eq(mapped_bool_sum([False{}, True{}, False{}, True{}]), 84),
   U32.is_eq(mapped_sum([]), 0),
   U32.is_eq(mapped_hash([1, 2, 3]), 1158),
   U32.is_eq(mapped_array_count(affine_array_source()), 2))
#|(True{}, True{}, True{}, True{}, True{}, True{}, True{})
