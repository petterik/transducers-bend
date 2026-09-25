import Base

# Isolates the ordinary-helper boundary behind composed take: the source
# loop constructs a known closure; the helper receives it as an affine value.
def apply_step(rf: U32 -> U32 -> U32, state: U32, x: U32) -> U32:
  rf(state, x)

def loop(xs: List<U32>, state: U32) -> U32:
  match xs:
    case Nil{}:
      state
    case h <> t:
      loop(t, apply_step(s => x => (s + x : U32), state, h))

def main() -> U32:
  loop([1, 2, 3], 0)
#|6
