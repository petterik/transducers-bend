import Base

# A local name for a known reducer can be specialized at the call site.
def fold(~rf: U32 -> U32 -> U32, xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case h <> t:
      fold(~rf, t, rf(acc, h))

def main() -> U32:
  rf = U32.add
  fold(~rf, [1, 2, 3], 0)
#|6
