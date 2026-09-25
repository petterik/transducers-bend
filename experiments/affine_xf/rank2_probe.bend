import Base
import ../../transduce.bend as T

type Xf<-A: Type, -B: Type> is Type:
  Xf{apply: @-R: Type -> T.Reducer<B, R> -> T.Reducer<A, R>}

def plus_one(x: U32) -> U32:
  (x + 1 : U32)

def map_apply(~A: Type, ~B: Type, ~f: A -> B, -R: Type,
  down: T.Reducer<B, R>) -> T.Reducer<A, R>:
  match down:
    case T.Reducer{C, S, init, advance, done}:
      T.Reducer{C, S, init,
        s => x => advance(s, f(x)), done}

def map_xf(~A: Type, ~B: Type, ~f: A -> B) -> Xf<A, B>:
  Xf{R => down => map_apply(~A, ~B, ~f, R, down)}

def apply_xf(-A: Type, -B: Type, -R: Type,
  xf: Xf<A, B>, down: T.Reducer<B, R>) -> T.Reducer<A, R>:
  match xf:
    case Xf{f}:
      f(R, down)

def main() -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~apply_xf(U32, U32, U32,
      map_xf(~U32, ~U32, ~plus_one), T.sum())),
    0, [1, 2, 3])
#|9
