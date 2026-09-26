import Base
import ../xf.bend as X
import ../transduce_core.bend as T

type Token is Type:
  Token{value: U32}

def token_value(token: Token) -> U32:
  match token:
    case Token{value}: value

def tokens() -> Array<Token>:
  ANode{ALeaf{Token{2}}, ALeaf{Token{3}}}

def token_arrays() -> List<Array<Token>>:
  [tokens(), tokens()]

def from_array() -> U32:
  X.transduce(X.map(~Token, ~U32, ~token_value), X.sum_rf(), 0,
    T.Array.affine_source(~Token, tokens()))

def from_fragments() -> U32:
  X.transduce(X.comp2(X.cat(T.Array.affine_adapter(~Token)),
    X.map(~Token, ~U32, ~token_value)), X.sum_rf(), 0,
    token_arrays())

def main() -> U32 & U32:
  (from_array(), from_fragments())
#|(5, 10)
