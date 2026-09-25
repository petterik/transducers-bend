import Base
import ../xf.bend as X
import ../transduce_core.bend as T

def three() -> List<U32>:
  [1, 2, 3]

def four() -> List<U32>:
  [1, 2, 3, 4]

def fragment(x: U32) -> List<U32>:
  +x = x
  [x, (x + 10 : U32)]

def even_choice_case(yes: Bool, x: U32) -> Maybe<U32>:
  match yes:
    case True{}: Some{x}
    case False{}: None{}

def even_choice(x: U32) -> Maybe<U32>:
  +x = x
  even_choice_case(U32.is_zero(U32.mod(x, 2)), x)

def cat_total() -> U32:
  X.transduce(X.comp2(X.map(~U32, ~List<U32>, ~fragment),
    X.cat(T.List.adapter(~U32))),
    X.sum_rf(), 0, three())

def cat_take() -> U32:
  X.transduce(X.comp2(
    X.mapcat(~U32, ~U32, ~List<U32>,
      ~(K => S => advance => inspect => input => state =>
        T.source_list(~U32, ~K, ~S, ~advance, ~inspect, input, state)),
      ~fragment),
    X.take(~U32, 3n)), X.sum_rf(), 0, three())

def cat_zero() -> U32:
  X.transduce(X.comp2(
    X.mapcat(~U32, ~U32, ~List<U32>,
      ~(K => S => advance => inspect => input => state =>
        T.source_list(~U32, ~K, ~S, ~advance, ~inspect, input, state)),
      ~fragment),
    X.take(~U32, 0n)), X.sum_rf(), 0, three())

def kept() -> U32:
  X.transduce(X.keep(~U32, ~U32, ~even_choice),
    X.sum_rf(), 0, four())

def main() -> U32 & U32 & U32 & U32:
  (cat_total(), cat_take(), cat_zero(), kept())
#|(42, 14, 0, 6)
