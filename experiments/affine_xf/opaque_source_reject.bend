import Base
import ../../transduce.bend as T

# Must fail: a source generic in S cannot manufacture a reducer Stop as S.
def forged(~S: Type, ~advance: S -> U32 -> S,
  ~inspect: S -> T.Checked<S>, xs: List<U32>, s: S) -> S:
  T.Stop{s}
