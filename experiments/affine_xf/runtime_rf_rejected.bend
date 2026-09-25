import Base

# An ordinary function value is affine. A recursive source driver cannot both
# call it on this item and carry it to the next item. The proposed public rf
# must therefore be specialized, or represented as reusable closed code.
def fold(xs: List<U32>, rf: U32 -> U32 -> U32, acc: U32) -> U32:
  match xs:
    case Nil{}:
      acc
    case h <> t:
      fold(t, rf, rf(acc, h))

def main() -> U32:
  fold([1, 2, 3], U32.add, 0)
