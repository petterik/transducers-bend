import Base

type Control<-S: Type> is Type:
  Continue{state: S}
  Stop{state: S}

type Reducer<-A: Type, -R: Type> is Type:
  Reducer{C: Type, S: Type, start: C -> Control<S>, step: S -> A -> Control<S>, finish: S -> R}

def Config(-A: Type, -R: Type, r: Reducer<A, R>) -> Type:
  match r:
    case Reducer{C, S, init, advance, done}:
      C

def State(-A: Type, -R: Type, r: Reducer<A, R>) -> Type:
  match r:
    case Reducer{C, S, init, advance, done}:
      S

def start(-A: Type, -R: Type, r: Reducer<A, R>) -> Config(A, R, r) -> Control<State(A, R, r)>:
  match r:
    case Reducer{C, S, f, advance, done}:
      f

def step(-A: Type, -R: Type, r: Reducer<A, R>) -> State(A, R, r) -> A -> Control<State(A, R, r)>:
  match r:
    case Reducer{C, S, init, f, done}:
      f

def finish(-A: Type, -R: Type, r: Reducer<A, R>) -> State(A, R, r) -> R:
  match r:
    case Reducer{C, S, init, advance, f}:
      f

def drive(~A: Type, ~R: Type, ~r: Reducer<A, R>, xs: List<A>, c: Control<State(A, R, r)>) -> R:
  match xs c:
    case Nil{} Continue{s}:
      finish(A, R, r, s)
    case Nil{} Stop{s}:
      finish(A, R, r, s)
    case h <> t Stop{s}:
      finish(A, R, r, s)
    case h <> t Continue{s}:
      drive(~A, ~R, ~r, t, step(A, R, r, s, h))

def sum() -> Reducer<U32, U32>:
  Reducer{U32, U32, x => Continue{x}, s => x => Continue{(s + x : U32)}, s => s}

def mapping(~A: Type, ~B: Type, ~R: Type, ~f: A -> B, ~down: Reducer<B, R>) -> Reducer<A, R>:
  Reducer{Config(B, R, down), State(B, R, down),
    c => start(B, R, down, c),
    s => x => step(B, R, down, s, f(x)),
    s => finish(B, R, down, s)}

def transduce(~A: Type, ~R: Type, ~r: Reducer<A, R>, config: Config(A, R, r), xs: List<A>) -> R:
  drive(~A, ~R, ~r, xs, start(A, R, r, config))

def pipeline() -> Reducer<U32, U32>:
  mapping(~U32, ~U32, ~U32, ~(x => (x + 1 : U32)), ~sum())

def main() -> U32:
  transduce(~U32, ~U32, ~pipeline(), 0, [1, 2, 3])
#|9
