import Base
import ../xf.bend as X

type Token is Type:
  Token{value: U32}

def token_value(token: Token) -> U32:
  match token:
    case Token{value}: value

def tokens() -> List<Token>:
  [Token{1}, Token{2}, Token{3}]

def five() -> List<U32>:
  [1, 2, 3, 4, 5]

def three() -> List<U32>:
  [1, 2, 3]

def inc(x: U32) -> U32:
  U32.inc(x)

def twice(x: U32) -> U32:
  (x * 2 : U32)

def dec(x: U32) -> U32:
  U32.sub(x, 1)

def even(x: U32) -> Bool:
  U32.is_zero(U32.mod(x, 2))

def add_offset(offset: U32, x: U32) -> U32:
  (offset + x : U32)

def mixed() -> U32:
  X.transduce(X.comp5(
    X.map(~U32, ~U32, ~inc),
    X.filter(~U32, ~even),
    X.map(~U32, ~U32, ~twice),
    X.take(~U32, 2n),
    X.map(~U32, ~U32, ~dec)),
    X.sum_rf(), 0, five())

def configured() -> U32:
  X.transduce(X.map_with(~U32, ~U32, ~U32,
    ~add_offset, 7), X.sum_rf(), 0, three())

def removed() -> U32:
  X.transduce(X.remove(~U32, ~even), X.sum_rf(), 0, five())

def affine() -> U32:
  X.transduce(X.map(~Token, ~U32, ~token_value),
    X.sum_rf(), 0, tokens())

def counted() -> Nat:
  X.transduce(X.map(~U32, ~Nat, ~U32.to_nat),
    X.count_nat_rf(), Unit{}, three())

def main() -> U32 & U32 & U32 & U32 & Nat:
  (mixed(), configured(), removed(), affine(), counted())
#|(10, 27, 9, 6, 3n)
