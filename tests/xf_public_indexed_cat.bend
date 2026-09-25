import Base
import ../xf.bend as X
import ../transduce_core.bend as T
import ./support/vec_pair_source.bend as Pair

type Token is Type:
  Token{value: U32}

def token_value(token: Token) -> U32:
  match token:
    case Token{value}: value

def tokens() -> List<Token>:
  [Token{2}, Token{3}, Token{4}]

def indexed_token(index: Nat, token: Token) -> U32:
  U32.add(U32.from_nat(index), token_value(token))

def indexed_value(index: Nat, value: U32) -> U32:
  U32.add(U32.from_nat(index), value)

def choose(keep: Bool, value: U32) -> Maybe<U32>:
  match keep:
    case True{}: Some{value}
    case False{}: None{}

def keep_even_index(index: Nat, value: U32) -> Maybe<U32>:
  choose(Nat.is_eq(Nat.mod(index, 2n), 0n), value)

def values() -> List<U32>:
  [1, 2, 3, 4, 5]

def empty() -> List<U32>:
  []

def fragments() -> List<List<U32>>:
  [[1, 2], [], [3]]

def token_fragments() -> List<List<Token>>:
  [[Token{2}], [Token{3}, Token{4}]]

def array_fragments() -> List<Array<U32>>:
  [Array.new(U32, 1n, 2), Array.new(U32, 1n, 3)]

def pair_fragments() -> List<Pair.PairSource>:
  [Pair.PairSource{1, 2}, Pair.PairSource{3, 4}]

def list_cat() -> U32:
  X.transduce(X.cat(~U32, ~List<U32>,
    ~(K => S => advance => inspect => input => state =>
      T.source_list(~U32, ~K, ~S, ~advance, ~inspect, input, state))),
    X.sum_rf(), 0, fragments())

def list_cat_take() -> U32:
  X.transduce(X.comp2(X.cat(~U32, ~List<U32>,
    ~(K => S => advance => inspect => input => state =>
      T.source_list(~U32, ~K, ~S, ~advance, ~inspect, input, state))),
    X.take(~U32, 2n)), X.sum_rf(), 0, fragments())

def array_cat() -> U32:
  X.transduce(X.cat(~U32, ~Array<U32>,
    ~(K => S => advance => inspect => input => state =>
      T.source_array(~U32, ~K, ~S, ~advance, ~inspect, input, state))),
    X.sum_rf(), 0, array_fragments())

def pair_cat() -> U32:
  X.transduce(X.cat(~U32, ~Pair.PairSource,
    ~(K => S => advance => inspect => input => state =>
      Pair.source_pair(~K, ~S, ~advance, ~inspect, input, state))),
    X.sum_rf(), 0, pair_fragments())

def pair_cat_take() -> U32:
  X.transduce(X.comp2(X.cat(~U32, ~Pair.PairSource,
    ~(K => S => advance => inspect => input => state =>
      Pair.source_pair(~K, ~S, ~advance, ~inspect, input, state))),
    X.take(~U32, 3n)), X.sum_rf(), 0, pair_fragments())

def affine_cat() -> U32:
  X.transduce(X.comp2(X.cat(~Token, ~List<Token>,
    ~(K => S => advance => inspect => input => state =>
      T.source_list(~Token, ~K, ~S, ~advance, ~inspect, input, state))),
    X.map(~Token, ~U32, ~token_value)), X.sum_rf(), 0,
    token_fragments())

def retained_cat() -> List<U32>:
  X.into(empty(), X.cat(~U32, ~List<U32>,
    ~(K => S => advance => inspect => input => state =>
      T.source_list(~U32, ~K, ~S, ~advance, ~inspect, input, state))),
    fragments())

def retained_indexed() -> List<U32>:
  X.into(empty(), X.map_indexed(~U32, ~U32, ~indexed_value), values())

def retained_kept() -> List<U32>:
  X.into(empty(), X.keep_indexed(~U32, ~U32, ~keep_even_index), values())

def retained_nth() -> List<U32>:
  X.into(empty(), X.take_nth(~U32, 2n), values())

def main() -> List<U32> & List<U32> & List<U32> &
  List<U32> & List<U32>:
  ([X.transduce(X.map_indexed(~U32, ~U32, ~indexed_value),
      X.sum_rf(), 0, values()),
    X.transduce(X.map_indexed(~Token, ~U32, ~indexed_token),
      X.sum_rf(), 0, tokens()),
    X.transduce(X.keep_indexed(~U32, ~U32, ~keep_even_index),
      X.sum_rf(), 0, values()),
    X.transduce(X.comp2(X.drop(~U32, 1n),
      X.map_indexed(~U32, ~U32, ~indexed_value)),
      X.sum_rf(), 0, values()),
    X.transduce(X.comp2(X.map_indexed(~U32, ~U32, ~indexed_value),
      X.drop(~U32, 1n)), X.sum_rf(), 0, values()),
    X.transduce(X.take_nth(~U32, 2n), X.sum_rf(), 0, values()),
    X.transduce(X.take_nth(~U32, 1n), X.sum_rf(), 0, values()),
    X.transduce(X.take_nth(~U32, 0n), X.sum_rf(), 0, values()),
    X.transduce(X.take_nth(~U32, 8n), X.sum_rf(), 0, values()),
    X.transduce(X.comp2(X.take_nth(~U32, 2n), X.take(~U32, 2n)),
      X.sum_rf(), 0, values()),
    X.transduce(X.comp2(X.take(~U32, 2n), X.take_nth(~U32, 2n)),
      X.sum_rf(), 0, values()),
    X.transduce(X.comp2(X.take_nth(~Token, 2n),
      X.map(~Token, ~U32, ~token_value)), X.sum_rf(), 0, tokens()),
    X.transduce(X.take_nth(~U32, 2n), X.sum_rf(), 0,
      Array.new(U32, 2n, 2)),
    X.transduce(X.map_indexed(~U32, ~U32, ~indexed_value),
      X.sum_rf(), 0, T.range(3)),
    X.transduce(X.take_nth(~U32, 2n), X.sum_rf(), 0,
      Pair.example()),
    list_cat(), list_cat_take(), array_cat(), pair_cat(),
    pair_cat_take(), affine_cat()],
   retained_cat(), retained_indexed(), retained_kept(), retained_nth())
#|([25, 12, 9, 20, 24, 9, 15, 0, 1, 4, 1, 6, 4, 6, 3, 6, 3, 10, 10, 6, 9], [3, 2, 1], [9, 7, 5, 3, 1], [5, 3, 1], [5, 3, 1])
