import Base
import ../../../transduce.bend as T

def above(t: U32, x: U32) -> Bool:
  U32.is_gt(x, t)

def pipeline() -> T.Reducer<U32, U32>:
  T.filter(~U32, ~U32, ~U32, ~above,
    ~T.take(~U32, ~U32, ~T.sum()))

def values() -> Array<U32>:
  a = Array.set(U32, [0 : U32*8n], 0, 0)
  b = Array.set(U32, a, 1, 1)
  c = Array.set(U32, b, 2, 2)
  d = Array.set(U32, c, 3, 3)
  e = Array.set(U32, d, 4, 4)
  f = Array.set(U32, e, 5, 5)
  g = Array.set(U32, f, 6, 6)
  Array.set(U32, g, 7, 7)

def run(n: Nat) -> U32:
  T.transduce(~T.over_array(~U32, ~U32, ~pipeline()), (3, (n, 0)), values())

def main() -> IO(Unit):
  IO.print(U32.show(run(0n)) ++ ":" ++
    U32.show(run(2n)) ++ ":" ++
    U32.show(run(32n)))
