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

def map(~A: Type, ~B: Type, ~R: Type, ~f: A -> B, ~down: Reducer<B, R>) -> Reducer<A, R>:
  Reducer{Config(B, R, down), State(B, R, down),
    c => start(B, R, down, c),
    s => x => step(B, R, down, s, f(x)),
    s => finish(B, R, down, s)}

def transduce(~A: Type, ~R: Type, ~r: Reducer<A, R>, config: Config(A, R, r), xs: List<A>) -> R:
  drive(~A, ~R, ~r, xs, start(A, R, r, config))


# A consumer with an ordinary reducing callback and a separate completion.
def reducing(~A: Type, ~S: Type, ~R: Type, ~f: S -> A -> S, ~done: S -> R) -> Reducer<A, R>:
  Reducer{S, S, s => Continue{s}, s => x => Continue{f(s, x)}, done}

# Configuration is runtime data, while callback code is a closed template.
type Configured<-C: Data, -S: Type> is Type:
  Configured{config: C, inner: S}

def configured_wrap(~C: Data, ~S: Type, config: C, c: Control<S>) -> Control<Configured<C, S>>:
  match c:
    case Continue{s}:
      Continue{Configured{config, s}}
    case Stop{s}:
      Stop{Configured{config, s}}

def configured_start(~A: Type, ~R: Type, ~C: Data, ~down: Reducer<A, R>, config: C & Config(A, R, down)) -> Control<Configured<C, State(A, R, down)>>:
  (local, inner) = config
  configured_wrap(~C, ~State(A, R, down), local, start(A, R, down, inner))

def configured_finish(~A: Type, ~R: Type, ~C: Data, ~down: Reducer<A, R>, state: Configured<C, State(A, R, down)>) -> R:
  match state:
    case Configured{local, inner}:
      finish(A, R, down, inner)

def map_with_step(~A: Type, ~B: Type, ~R: Type, ~C: Data,
  ~f: C -> A -> B, ~down: Reducer<B, R>, state: Configured<C, State(B, R, down)>, x: A) -> Control<Configured<C, State(B, R, down)>>:
  match state:
    case Configured{+local, inner}:
      configured_wrap(~C, ~State(B, R, down), local, step(B, R, down, inner, f(local, x)))

def map_with(~A: Type, ~B: Type, ~R: Type, ~C: Data,
  ~f: C -> A -> B, ~down: Reducer<B, R>) -> Reducer<A, R>:
  Reducer{C & Config(B, R, down), Configured<C, State(B, R, down)>,
    c => configured_start(~B, ~R, ~C, ~down, c),
    s => x => map_with_step(~A, ~B, ~R, ~C, ~f, ~down, s, x),
    s => configured_finish(~B, ~R, ~C, ~down, s)}

def filter_choose(~A: Data, ~R: Type, ~C: Data, ~down: Reducer<A, R>,
  keep: Bool, local: C, inner: State(A, R, down), x: A) -> Control<Configured<C, State(A, R, down)>>:
  match keep:
    case False{}:
      Continue{Configured{local, inner}}
    case True{}:
      configured_wrap(~C, ~State(A, R, down), local, step(A, R, down, inner, x))

def filter_step(~A: Data, ~R: Type, ~C: Data, ~predicate: C -> A -> Bool,
  ~down: Reducer<A, R>, state: Configured<C, State(A, R, down)>, +x: A) -> Control<Configured<C, State(A, R, down)>>:
  match state:
    case Configured{+local, inner}:
      filter_choose(~A, ~R, ~C, ~down, predicate(local, x), local, inner, x)

def filter(~A: Data, ~R: Type, ~C: Data, ~predicate: C -> A -> Bool,
  ~down: Reducer<A, R>) -> Reducer<A, R>:
  Reducer{C & Config(A, R, down), Configured<C, State(A, R, down)>,
    c => configured_start(~A, ~R, ~C, ~down, c),
    s => x => filter_step(~A, ~R, ~C, ~predicate, ~down, s, x),
    s => configured_finish(~A, ~R, ~C, ~down, s)}

# Keeping downstream control allows a wrapper to distinguish its own limit
# from a downstream consumer stopping. Completion always runs once.
type Taking<-S: Type> is Type:
  Taking{left: Nat, inner: Control<S>}

def take_control(~S: Type, n: Nat, c: Control<S>) -> Control<Taking<S>>:
  match n c:
    case 0n Continue{s}:
      Stop{Taking{0n, Continue{s}}}
    case 0n Stop{s}:
      Stop{Taking{0n, Stop{s}}}
    case 1n+p Continue{s}:
      Continue{Taking{1n+p, Continue{s}}}
    case 1n+p Stop{s}:
      Stop{Taking{1n+p, Stop{s}}}

def take_start(~A: Type, ~R: Type, ~down: Reducer<A, R>, config: Nat & Config(A, R, down)) -> Control<Taking<State(A, R, down)>>:
  (n, inner) = config
  take_control(~State(A, R, down), n, start(A, R, down, inner))

def take_step(~A: Type, ~R: Type, ~down: Reducer<A, R>, state: Taking<State(A, R, down)>, x: A) -> Control<Taking<State(A, R, down)>>:
  match state:
    case Taking{0n, c}:
      Stop{Taking{0n, c}}
    case Taking{1n+p, Stop{s}}:
      Stop{Taking{1n+p, Stop{s}}}
    case Taking{1n+p, Continue{s}}:
      take_control(~State(A, R, down), p, step(A, R, down, s, x))

def finish_control(~A: Type, ~R: Type, ~down: Reducer<A, R>, c: Control<State(A, R, down)>) -> R:
  match c:
    case Continue{s}:
      finish(A, R, down, s)
    case Stop{s}:
      finish(A, R, down, s)

def take_finish(~A: Type, ~R: Type, ~down: Reducer<A, R>, state: Taking<State(A, R, down)>) -> R:
  match state:
    case Taking{n, c}:
      finish_control(~A, ~R, ~down, c)

def take(~A: Type, ~R: Type, ~down: Reducer<A, R>) -> Reducer<A, R>:
  Reducer{Nat & Config(A, R, down), Taking<State(A, R, down)>,
    c => take_start(~A, ~R, ~down, c),
    s => x => take_step(~A, ~R, ~down, s, x),
    s => take_finish(~A, ~R, ~down, s)}

# Identity composition is the downstream description itself.
def identity(~A: Type, ~R: Type, ~down: Reducer<A, R>) -> Reducer<A, R>:
  down
