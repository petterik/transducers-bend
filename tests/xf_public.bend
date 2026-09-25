import Base
import ../xf.bend as Xf
import ../transduce.bend as T

def inc(x: U32) -> U32:
  (x + 1 : U32)

def twice(x: U32) -> U32:
  (x * 2 : U32)

def dec(x: U32) -> U32:
  U32.sub(x, 1)

def even(x: U32) -> Bool:
  U32.is_zero(U32.mod(x, 2))

def keep_if(x: U32, yes: Bool) -> Maybe<U32>:
  match yes:
    case True{}:
      Some{x}
    case False{}:
      None{}

def keep_even(+x: U32) -> Maybe<U32>:
  keep_if(x, even(x))

def duplicate(+x: U32) -> List<U32>:
  [x, x]

def six() -> List<U32>:
  [1, 2, 3, 4, 5, 6]

def four() -> List<U32>:
  [1, 2, 3, 4]

def three() -> List<U32>:
  [1, 2, 3]

def mixed() -> U32:
  Xf.transduce(Xf.comp5(
    Xf.map(~U32, ~U32, ~inc),
    Xf.filter(~U32, ~even),
    Xf.map(~U32, ~U32, ~twice),
    Xf.take(~U32, 2n),
    Xf.map(~U32, ~U32, ~dec)),
    Xf.sum_rf(), 0, six())

def kept() -> U32:
  Xf.transduce(Xf.keep(~U32, ~U32, ~(x => keep_even(x))),
    Xf.sum_rf(), 0, four())

def flattened() -> U32:
  Xf.transduce(Xf.mapcat(~U32, ~U32, ~List<U32>,
    ~(S => advance => inspect => input => s => T.source_list(~U32, ~S, ~advance, ~inspect, input, s)),
    ~(x => duplicate(x))),
    Xf.sum_rf(), 0, three())

def main() -> U32 & U32 & U32:
  (mixed(), kept(), flattened())
#|(10, 6, 12)
