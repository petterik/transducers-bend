import Base
import ../xf.bend as Xf
import ../transduce.bend as T
import ../vec.bend as Vec

type FragmentPair is Type:
  FragmentPair{first: U32, second: U32}

type Token is Type:
  Token{value: U32}

def token_value(token: Token) -> U32:
  match token:
    case Token{value}:
      value

def token_list(+x: U32) -> List<Token>:
  [Token{x}, Token{(x + 10 : U32)}]

def second(~R: Type, ~r: T.Reducer<U32, R>, x: U32,
  control: T.Control<T.State(U32, R, r)>) ->
  T.Control<T.State(U32, R, r)>:
  match control:
    case T.Stop{s}:
      T.Stop{s}
    case T.Continue{s}:
      T.step(U32, R, r, s, x)

def drive_pair(~R: Type, ~r: T.Reducer<U32, R>, pair: FragmentPair,
  control: T.Control<T.State(U32, R, r)>) ->
  T.Control<T.State(U32, R, r)>:
  match pair control:
    case FragmentPair{a, b} T.Stop{s}:
      T.Stop{s}
    case FragmentPair{a, b} T.Continue{s}:
      second(~R, ~r, b, T.step(U32, R, r, s, a))

def pair_fragment(+x: U32) -> FragmentPair:
  FragmentPair{x, (x + 10 : U32)}

def pair_list(+x: U32) -> List<U32>:
  [x, (x + 10 : U32)]

def array_fragment(+x: U32) -> Array<U32>:
  Array.set(U32, [x : U32*2n], 1, (x + 10 : U32))

def pair_sum(xs: List<U32>) -> U32:
  Xf.transduce(Xf.mapcat(~U32, ~U32, ~FragmentPair, ~(R => r => input => c => drive_pair(~R, ~r, input, c)), ~(x => pair_fragment(x))),
    Xf.sum_rf(), 0, xs)

def list_sum(xs: List<U32>) -> U32:
  Xf.transduce(Xf.mapcat(~U32, ~U32, ~List<U32>, ~(R => r => input => c => T.reduce_list_static(~U32, ~R, ~r, input, c)), ~(x => pair_list(x))),
    Xf.sum_rf(), 0, xs)

def literal_sum(xs: List<U32>) -> U32:
  Xf.transduce(Xf.mapcat(~U32, ~U32, ~List<U32>,
    ~(R => r => input => c => T.reduce_list_static(~U32, ~R, ~r, input, c)),
    ~(x => [x])), Xf.sum_rf(), 0, xs)

def array_sum(xs: List<U32>) -> U32:
  Xf.transduce(Xf.mapcat(~U32, ~U32, ~Array<U32>,
    ~(R => r => input => c => T.reduce_array(~U32, ~T.State(U32, R, r),
      ~(s => x => T.step(U32, R, r, s, x)), input, c)),
    ~(x => array_fragment(x))), Xf.sum_rf(), 0, xs)

def affine_sum(xs: List<U32>) -> U32:
  Xf.transduce(Xf.comp2(
    Xf.mapcat(~U32, ~Token, ~List<Token>,
      ~(R => r => input => c => T.reduce_list_static(~Token, ~R, ~r, input, c)),
      ~(x => token_list(x))),
    Xf.map(~Token, ~U32, ~token_value)), Xf.sum_rf(), 0, xs)

def pair_take(xs: List<U32>) -> U32:
  Xf.transduce(Xf.comp2(Xf.mapcat(~U32, ~U32, ~FragmentPair, ~(R => r => input => c => drive_pair(~R, ~r, input, c)), ~(x => pair_fragment(x))),
    Xf.take(~U32, 3n)), Xf.sum_rf(), 0, xs)

def empty_u32() -> List<U32>:
  []

def pair_retain(xs: List<U32>) -> List<U32>:
  Xf.into(empty_u32(), Xf.mapcat(~U32, ~U32, ~FragmentPair, ~(R => r => input => c => drive_pair(~R, ~r, input, c)), ~(x => pair_fragment(x))), xs)

def pair_vec(xs: List<U32>) -> Vec.Vec<U32>:
  Xf.into(Vec.empty(~U32, 0),
    Xf.mapcat(~U32, ~U32, ~FragmentPair, ~(R => r => input => c => drive_pair(~R, ~r, input, c)), ~(x => pair_fragment(x))), xs)

def from_vec(vec: Vec.Vec<U32>) -> U32:
  Xf.transduce(Xf.map(~U32, ~U32, ~U32.inc), Xf.sum_rf(), 0, vec)

def main() -> U32 & U32 & U32 & U32 & U32 & U32 & List<U32> & U32:
  (pair_sum([1, 2, 3]), list_sum([1, 2, 3]),
   literal_sum([1, 2, 3]), array_sum([1, 2, 3]),
   affine_sum([1, 2, 3]), pair_take([1, 2, 3]),
   pair_retain([1, 2]), from_vec(pair_vec([1, 2])))
#|(42, 42, 6, 42, 42, 14, [12, 2, 11, 1], 30)
