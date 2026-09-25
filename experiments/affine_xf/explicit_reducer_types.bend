import Base
import ../../transduce.bend as T

type R2<-A: Type, -R: Type, -C: Type, -S: Type> is Type:
  R2{start: C -> T.Control<S>, step: S -> A -> T.Control<S>, done: S -> R}

type Xf<-A: Type, -B: Type, -f: A -> B> is Type:
  Xf{limit: Nat}

def map_take(~A: Type, ~B: Type, ~f: A -> B, limit: Nat) -> Xf<A, B, f>:
  Xf{limit}

def plus_one(x: U32) -> U32:
  (x + 1 : U32)

def sum2() -> R2<U32, U32, U32, U32>:
  R2{x => T.Continue{x}, s => x => T.Continue{(s + x : U32)}, s => s}

def start2(~A: Type, ~R: Type, ~C: Type, ~S: Type,
  r: R2<A, R, C, S>) -> C -> T.Control<S>:
  match r:
    case R2{start, advance, done}:
      start

def step2(~A: Type, ~R: Type, ~C: Type, ~S: Type,
  r: R2<A, R, C, S>) -> S -> A -> T.Control<S>:
  match r:
    case R2{start, advance, done}:
      advance

def done2(~A: Type, ~R: Type, ~C: Type, ~S: Type,
  r: R2<A, R, C, S>) -> S -> R:
  match r:
    case R2{start, advance, done}:
      done

def map2(~A: Type, ~B: Type, ~R: Type, ~C: Type, ~S: Type,
  ~f: A -> B, ~down: R2<B, R, C, S>) -> R2<A, R, C, S>:
  R2{c => start2(~B, ~R, ~C, ~S, down)(c),
    s => x => step2(~B, ~R, ~C, ~S, down)(s, f(x)),
    s => done2(~B, ~R, ~C, ~S, down)(s)}

def next(~A: Type, ~R: Type, ~C: Type, ~S: Type,
  ~r: R2<A, R, C, S>, t: T.Taking<S>, x: A) -> T.Control<T.Taking<S>>:
  match t:
    case T.Taking{0n, inner}:
      T.Stop{T.Taking{0n, inner}}
    case T.Taking{1n+p, T.Stop{s}}:
      T.Stop{T.Taking{1n+p, T.Stop{s}}}
    case T.Taking{1n+p, T.Continue{s}}:
      T.take_control(~S, p, step2(~A, ~R, ~C, ~S, r)(s, x))

def fold(~A: Type, ~R: Type, ~C: Type, ~S: Type,
  ~r: R2<A, R, C, S>, xs: List<A>, c: T.Control<T.Taking<S>>) ->
  T.Control<T.Taking<S>>:
  match xs c:
    case Nil{} c:
      c
    case h <> t T.Stop{s}:
      T.Stop{s}
    case h <> t T.Continue{s}:
      fold(~A, ~R, ~C, ~S, ~r, t, next(~A, ~R, ~C, ~S, ~r, s, h))

def complete(~A: Type, ~R: Type, ~C: Type, ~S: Type,
  ~r: R2<A, R, C, S>, c: T.Control<T.Taking<S>>) -> R:
  match c:
    case T.Continue{T.Taking{left, T.Continue{s}}}:
      done2(~A, ~R, ~C, ~S, r)(s)
    case T.Continue{T.Taking{left, T.Stop{s}}}:
      done2(~A, ~R, ~C, ~S, r)(s)
    case T.Stop{T.Taking{left, T.Continue{s}}}:
      done2(~A, ~R, ~C, ~S, r)(s)
    case T.Stop{T.Taking{left, T.Stop{s}}}:
      done2(~A, ~R, ~C, ~S, r)(s)

def run(~A: Type, ~B: Type, ~R: Type, ~C: Type, ~S: Type,
  ~f: A -> B, ~down: R2<B, R, C, S>, xf: Xf<A, B, f>,
  config: C, xs: List<A>) -> R:
  match xf:
    case Xf{limit}:
      complete(~A, ~R, ~C, ~S,
        ~map2(~A, ~B, ~R, ~C, ~S, ~f, ~down),
        fold(~A, ~R, ~C, ~S,
          ~map2(~A, ~B, ~R, ~C, ~S, ~f, ~down), xs,
          T.take_control(~S, limit,
            start2(~A, ~R, ~C, ~S,
              map2(~A, ~B, ~R, ~C, ~S, ~f, ~down))(config))))

def main() -> U32:
  xf = map_take(~U32, ~U32, ~plus_one, 2n)
  run(~U32, ~U32, ~U32, ~U32, ~U32,
    ~plus_one, ~sum2(), xf, 0, [1, 2, 3])
#|5
