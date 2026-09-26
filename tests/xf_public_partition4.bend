import Base
import ../xf.bend as X
import ../transduce_core.bend as T

type Token is Type:
  Token{value: U32}

def values() -> List<U32>:
  [1, 2, 3, 4, 5, 6, 7, 8, 9]

def short() -> List<U32>:
  [1, 2, 3]

def tokens() -> List<Token>:
  [Token{1}, Token{2}, Token{3}, Token{4}, Token{5}]

def token_group_sum(group: Token & Token & Token & Token) -> U32:
  match group:
    case (Token{v1}, Token{v2}, Token{v3}, Token{v4}):
      U32.add(U32.add(v1, v2), U32.add(v3, v4))

def group_sum(group: U32 & U32 & U32 & U32) -> U32:
  (a, b, c, d) = group
  U32.add(U32.add(a, b), U32.add(c, d))

def full() -> U32:
  X.transduce(X.comp2(X.partition4(~U32),
    X.map(~(U32 & U32 & U32 & U32), ~U32, ~group_sum)),
    X.sum_rf(), 0, values())

def stopped() -> U32:
  X.transduce(X.comp3(X.partition4(~U32),
    X.map(~(U32 & U32 & U32 & U32), ~U32, ~group_sum),
    X.take(~U32, 1n)), X.sum_rf(), 0, T.range(100))

def affine() -> U32:
  X.transduce(X.comp2(X.partition4(~Token),
    X.map(~(Token & Token & Token & Token), ~U32,
      ~token_group_sum)), X.sum_rf(), 0, tokens())

def main() -> U32 & U32 & U32 & U32:
  (full(), stopped(),
   X.transduce(X.comp2(X.partition4(~U32),
     X.map(~(U32 & U32 & U32 & U32), ~U32, ~group_sum)),
     X.sum_rf(), 0, short()), affine())
#|(36, 6, 0, 10)
