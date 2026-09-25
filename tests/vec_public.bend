import Base
import ../xf.bend as Xf
import ../vec.bend as Vec
import ../transduce.bend as T
import ./support/vec_pair_source.bend as Custom

def empty_u32() -> List<U32>:
  []

def inc(x: U32) -> U32:
  (x + 1 : U32)

def identity(x: U32) -> U32:
  x

def collect(xs: List<U32>) -> List<U32>:
  vec = Xf.into(Vec.empty(~U32, 0), Xf.map(~U32, ~U32, ~inc), xs)
  Xf.into(empty_u32(), Xf.map(~U32, ~U32, ~identity), vec)

def collect_reserved_at(xs: List<U32>, choice: Maybe<Vec.Vec<U32>>) ->
  Maybe<List<U32>>:
  match choice:
    case None{}:
      None{}
    case Some{vec}:
      Some{Xf.into(empty_u32(), Xf.map(~U32, ~U32, ~identity),
        Xf.into(vec, Xf.map(~U32, ~U32, ~inc), xs))}

def collect_reserved(xs: List<U32>) -> Maybe<List<U32>>:
  collect_reserved_at(xs, Vec.with_capacity(~U32, 4, 0))

def take2(xs: List<U32>) -> U32:
  vec = Xf.into(Vec.empty(~U32, 0), Xf.map(~U32, ~U32, ~inc), xs)
  Xf.transduce(Xf.take(~U32, 2n), Xf.sum_rf(), 0, vec)

def from_range() -> U32:
  vec = Xf.into(Vec.empty(~U32, 0), Xf.map(~U32, ~U32, ~inc),
    T.range(5))
  Xf.transduce(Xf.map(~U32, ~U32, ~identity), Xf.sum_rf(), 0, vec)

def from_array() -> U32:
  vec = Xf.into(Vec.empty(~U32, 0), Xf.map(~U32, ~U32, ~inc),
    [3 : U32*2n])
  Xf.transduce(Xf.map(~U32, ~U32, ~identity), Xf.sum_rf(), 0, vec)

def char_code(c: Char) -> U32:
  match c:
    case Chr{code}:
      code

def abc() -> String:
  "abc"

def from_string() -> U32:
  vec = Xf.into(Vec.empty(~U32, 0), Xf.map(~Char, ~U32, ~char_code),
    abc())
  Xf.transduce(Xf.map(~U32, ~U32, ~identity), Xf.sum_rf(), 0, vec)

def from_custom() -> U32:
  vec = Xf.into(Vec.empty(~U32, 0), Xf.map(~U32, ~U32, ~inc),
    Custom.example())
  Xf.transduce(Xf.map(~U32, ~U32, ~identity), Xf.sum_rf(), 0, vec)

def custom_stop() -> U32 & U32:
  (Xf.transduce(Xf.take(~U32, 0n), Xf.sum_rf(), 0,
     Custom.example()),
   Xf.transduce(Xf.take(~U32, 1n), Xf.sum_rf(), 0,
     Custom.example()))

def main() -> List<U32> & Maybe<List<U32>> & U32 & U32 & U32 & U32 &
  U32 & (U32 & U32):
  (collect([1, 2, 3, 4, 5]), collect_reserved([1, 2, 3]),
   take2([1, 2, 3, 4, 5]), from_range(), from_array(),
   from_string(), from_custom(), custom_stop())
#|([6, 5, 4, 3, 2], Some{[4, 3, 2]}, 5, 15, 8, 294, 9, 0, 3)
