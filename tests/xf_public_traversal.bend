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

def small(x: U32) -> Bool:
  U32.is_lt(x, 4)

def numbers() -> List<U32>:
  [1, 2, 3, 4, 5]

def empty() -> List<U32>:
  []

def empty_u32() -> List<U32>:
  []

def starts_large() -> List<U32>:
  [4, 1]

def affine_drop() -> U32:
  X.transduce(X.comp2(X.drop(~Token, 1n),
    X.map(~Token, ~U32, ~token_value)), X.sum_rf(), 0, tokens())

def take_before_drop() -> U32:
  X.transduce(X.comp2(X.take(~U32, 3n), X.drop(~U32, 1n)),
    X.sum_rf(), 0, numbers())

def drop_before_take() -> U32:
  X.transduce(X.comp2(X.drop(~U32, 1n), X.take(~U32, 2n)),
    X.sum_rf(), 0, numbers())

def take_while_before_take() -> U32:
  X.transduce(X.comp2(X.take_while(~U32, ~small),
    X.take(~U32, 2n)), X.sum_rf(), 0, numbers())

def take_before_take_while() -> U32:
  X.transduce(X.comp2(X.take(~U32, 2n),
    X.take_while(~U32, ~small)), X.sum_rf(), 0, numbers())

def ordered_drop_while() -> List<U32>:
  X.into(empty_u32(), X.drop_while(~U32, ~small), numbers())

def main() -> List<U32> & List<U32>:
  ([X.transduce(X.drop(~U32, 0n), X.sum_rf(), 0, numbers()),
    X.transduce(X.drop(~U32, 2n), X.sum_rf(), 0, numbers()),
    X.transduce(X.drop(~U32, 8n), X.sum_rf(), 0, numbers()),
    X.transduce(X.drop(~U32, 1n), X.sum_rf(), 0, empty()),
    affine_drop(), take_before_drop(), drop_before_take(),
    X.transduce(X.take_while(~U32, ~small), X.sum_rf(), 0, numbers()),
    X.transduce(X.take_while(~U32, ~small), X.sum_rf(), 0,
      starts_large()),
    X.transduce(X.drop_while(~U32, ~small), X.sum_rf(), 0, numbers()),
    X.transduce(X.drop_while(~U32, ~small), X.sum_rf(), 0,
      starts_large()),
    take_while_before_take(), take_before_take_while(),
    X.transduce(X.drop(~U32, 2n), X.sum_rf(), 0,
      Array.new(U32, 2n, 2)),
    X.transduce(X.take_while(~U32, ~small), X.sum_rf(), 0,
      Array.new(U32, 2n, 2)),
    X.transduce(X.drop_while(~U32, ~small), X.sum_rf(), 0,
      T.range(5)),
    X.transduce(X.drop(~U32, 1n), X.sum_rf(), 0, Pair.example()),
    X.transduce(X.take_while(~U32, ~small), X.sum_rf(), 0,
      Pair.example())],
   ordered_drop_while())
#|([15, 12, 0, 0, 7, 5, 5, 6, 0, 9, 5, 3, 3, 4, 8, 4, 4, 3], [5, 4])
