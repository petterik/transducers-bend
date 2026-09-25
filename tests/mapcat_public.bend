import Base
import ../xf.bend as Xf
import ../transduce_core.bend as T
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

def source_pair_after_first(~K: Data, ~S: Type, ~advance: S -> U32 -> S,
  second: U32, checked: T.Checked<K, S>) -> S:
  match checked:
    case T.Halted{permit, s}:
      s
    case T.Ready{s}:
      advance(s, second)

def source_pair_checked(~K: Data, ~S: Type, ~advance: S -> U32 -> S,
  ~inspect: S -> T.Checked<K, S>, pair: FragmentPair,
  checked: T.Checked<K, S>) -> S:
  match pair checked:
    case FragmentPair{first, second} T.Halted{permit, s}:
      s
    case FragmentPair{first, second} T.Ready{s}:
      source_pair_after_first(~K, ~S, ~advance, second,
        inspect(advance(s, first)))

def source_pair(~K: Data, ~S: Type, ~advance: S -> U32 -> S,
  ~inspect: S -> T.Checked<K, S>, pair: FragmentPair, s: S) -> S:
  source_pair_checked(~K, ~S, ~advance, ~inspect, pair, inspect(s))

def pair_fragment(+x: U32) -> FragmentPair:
  FragmentPair{x, (x + 10 : U32)}

def pair_list(+x: U32) -> List<U32>:
  [x, (x + 10 : U32)]

def array_fragment(+x: U32) -> Array<U32>:
  Array.set(U32, [x : U32*2n], 1, (x + 10 : U32))

def pair_sum(xs: List<U32>) -> U32:
  Xf.transduce(Xf.mapcat(~U32, ~U32, ~FragmentPair, ~(K => S => advance => inspect => input => s => source_pair(~K, ~S, ~advance, ~inspect, input, s)), ~(x => pair_fragment(x))),
    Xf.sum_rf(), 0, xs)

def list_sum(xs: List<U32>) -> U32:
  Xf.transduce(Xf.mapcat(~U32, ~U32, ~List<U32>, ~(K => S => advance => inspect => input => s => T.source_list(~U32, ~K, ~S, ~advance, ~inspect, input, s)), ~(x => pair_list(x))),
    Xf.sum_rf(), 0, xs)

def literal_sum(xs: List<U32>) -> U32:
  Xf.transduce(Xf.mapcat(~U32, ~U32, ~List<U32>,
    ~(K => S => advance => inspect => input => s => T.source_list(~U32, ~K, ~S, ~advance, ~inspect, input, s)),
    ~(x => [x])), Xf.sum_rf(), 0, xs)

def array_sum(xs: List<U32>) -> U32:
  Xf.transduce(Xf.mapcat(~U32, ~U32, ~Array<U32>,
    ~(K => S => advance => inspect => input => s => T.source_array(~U32, ~K, ~S,
      ~advance, ~inspect, input, s)),
    ~(x => array_fragment(x))), Xf.sum_rf(), 0, xs)

def affine_sum(xs: List<U32>) -> U32:
  Xf.transduce(Xf.comp2(
    Xf.mapcat(~U32, ~Token, ~List<Token>,
      ~(K => S => advance => inspect => input => s => T.source_list(~Token, ~K, ~S, ~advance, ~inspect, input, s)),
      ~(x => token_list(x))),
    Xf.map(~Token, ~U32, ~token_value)), Xf.sum_rf(), 0, xs)

def pair_take(xs: List<U32>) -> U32:
  Xf.transduce(Xf.comp2(Xf.mapcat(~U32, ~U32, ~FragmentPair, ~(K => S => advance => inspect => input => s => source_pair(~K, ~S, ~advance, ~inspect, input, s)), ~(x => pair_fragment(x))),
    Xf.take(~U32, 3n)), Xf.sum_rf(), 0, xs)

def empty_u32() -> List<U32>:
  []

def pair_retain(xs: List<U32>) -> List<U32>:
  Xf.into(empty_u32(), Xf.mapcat(~U32, ~U32, ~FragmentPair, ~(K => S => advance => inspect => input => s => source_pair(~K, ~S, ~advance, ~inspect, input, s)), ~(x => pair_fragment(x))), xs)

def pair_vec(xs: List<U32>) -> Vec.Vec<U32>:
  Xf.into(Vec.empty(~U32, 0),
    Xf.mapcat(~U32, ~U32, ~FragmentPair, ~(K => S => advance => inspect => input => s => source_pair(~K, ~S, ~advance, ~inspect, input, s)), ~(x => pair_fragment(x))), xs)

def from_vec(vec: Vec.Vec<U32>) -> U32:
  Xf.transduce(Xf.map(~U32, ~U32, ~U32.inc), Xf.sum_rf(), 0, vec)

def main() -> U32 & U32 & U32 & U32 & U32 & U32 & List<U32> & U32:
  (pair_sum([1, 2, 3]), list_sum([1, 2, 3]),
   literal_sum([1, 2, 3]), array_sum([1, 2, 3]),
   affine_sum([1, 2, 3]), pair_take([1, 2, 3]),
   pair_retain([1, 2]), from_vec(pair_vec([1, 2])))
#|(42, 42, 6, 42, 42, 14, [12, 2, 11, 1], 30)
