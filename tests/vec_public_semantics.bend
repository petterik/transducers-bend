import Base
import ../xf.bend as Xf
import ../vec.bend as Vec

type Duo is Data:
  Duo{left: U32, right: U32}

def make_pair(x: U32) -> Duo:
  Duo{x, 10}

def pair_sum(pair: Duo) -> U32:
  match pair:
    case Duo{left, right}:
      U32.add(left, right)

def nums() -> List<U32>:
  [1, 2, 3]

def composite() -> U32:
  vec = Xf.into(Vec.empty(~Duo, Duo{0, 0}),
    Xf.map(~U32, ~Duo, ~make_pair), nums())
  Xf.transduce(Xf.map(~Duo, ~U32, ~pair_sum),
    Xf.sum_rf(), 0, vec)

def identity_string(s: String) -> String:
  s

def size_string(s: String) -> U32:
  U32.from_nat(String.length(s))

def strings() -> List<String>:
  ["a", "bb", "ccc"]

def string_sum() -> U32:
  vec = Xf.into(Vec.empty(~String, ""),
    Xf.map(~String, ~String, ~identity_string), strings())
  Xf.transduce(Xf.map(~String, ~U32, ~size_string),
    Xf.sum_rf(), 0, vec)

def get_value(result: Vec.Vec<U32> & Maybe<&2, U32>) -> Maybe<&2, U32>:
  (vec, value) = result
  value

def after_set(result: Vec.UpdateResult<U32>) -> U32 & Maybe<&2, U32>:
  match result:
    case Vec.Updated{vec, old}:
      (old, get_value(Vec.get(~U32, vec, 1)))
    case Vec.Invalid{vec, value}:
      (value, get_value(Vec.get(~U32, vec, 1)))

def indexed_fin(result: U32 & Maybe<&2, U32>) ->
  U32 & Maybe<&2, U32> & Maybe<&2, U32>:
  (old, found) = result
  (old, found, get_value(Vec.get(~U32, Vec.empty(~U32, 0), 7)))

def indexed() -> U32 & Maybe<&2, U32> & Maybe<&2, U32>:
  vec = Vec.push(~U32, Vec.push(~U32, Vec.empty(~U32, 0), 1), 2)
  indexed_fin(after_set(Vec.set(~U32, vec, 1, 20)))

def unchecked_get(result: Vec.Vec<U32> & U32, old: U32) -> U32 & U32:
  (vec, value) = result
  (old, value)

def unchecked_set(result: Vec.Vec<U32> & U32) -> U32 & U32:
  (vec, old) = result
  unchecked_get(Vec.get_unchecked(~U32, vec, 1), old)

def unchecked() -> U32 & U32:
  vec = Vec.push(~U32, Vec.push(~U32, Vec.empty(~U32, 0), 1), 2)
  unchecked_set(Vec.set_unchecked(~U32, vec, 1, 20))

def take_zero() -> U32:
  vec = Xf.into(Vec.empty(~U32, 0),
    Xf.map(~U32, ~U32, ~(x => x)), nums())
  Xf.transduce(Xf.take(~U32, 0n), Xf.sum_rf(), 0, vec)

def set_was_invalid(result: Vec.UpdateResult<U32>) -> Bool:
  match result:
    case Vec.Updated{vec, old}:
      False{}
    case Vec.Invalid{vec, value}:
      True{}

def bad() -> Vec.Vec<U32>:
  Vec.Vec{2, 1, 0n, 0, Array.new(U32, 0n, 7)}

def forged() -> Maybe<&2, U32> & Bool & U32:
  (get_value(Vec.get(~U32, bad(), 1)),
   set_was_invalid(Vec.set(~U32, bad(), 1, 99)),
   Xf.transduce(Xf.map(~U32, ~U32, ~(x => x)), Xf.sum_rf(), 0,
     bad()))

def is_none(choice: Maybe<Vec.Vec<U32>>) -> Bool:
  match choice:
    case None{}:
      True{}
    case Some{vec}:
      False{}

def over_limit() -> Bool:
  is_none(Vec.with_capacity(~U32, 8388609, 0))

def main() -> U32 & U32 & (U32 & Maybe<&2, U32> & Maybe<&2, U32>) &
  (U32 & U32) & U32 & (Maybe<&2, U32> & Bool & U32) & Bool:
  (composite(), string_sum(), indexed(), unchecked(),
   take_zero(), forged(), over_limit())
#|(36, 6, (2, Some{20}, None{}), (2, 20), 0, (None{}, True{}, 7), True{})
