import Base
import ./rank2_probe.bend as P
import ../../transduce.bend as T

type PairU32 is Type:
  PairU32{first: U32, second: U32}

def second(~r: T.Reducer<U32, U32>, x: U32,
  c: T.Control<T.State(U32, U32, r)>) -> T.Control<T.State(U32, U32, r)>:
  match c:
    case T.Stop{s}:
      T.Stop{s}
    case T.Continue{s}:
      T.step(U32, U32, r, s, x)

def fold_pair(~r: T.Reducer<U32, U32>, src: PairU32,
  c: T.Control<T.State(U32, U32, r)>) -> T.Control<T.State(U32, U32, r)>:
  match src c:
    case PairU32{a, b} T.Stop{s}:
      T.Stop{s}
    case PairU32{a, b} T.Continue{s}:
      second(~r, b, T.step(U32, U32, r, s, a))

def main() -> U32:
  xf : P.Xf<U32, U32> = P.Xf{R => down => P.map_apply(~U32, ~U32, ~P.plus_one, R, down)}
  T.transduce(~T.reducible(~PairU32, ~U32, ~U32,
    ~(u => P.apply_xf(U32, U32, U32, xf, T.sum())),
    ~(src => c => fold_pair(~P.apply_xf(U32, U32, U32, xf, T.sum()), src, c))),
    0, PairU32{1, 2})
#|5
