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

def reduce_list(~A: Type, ~S: Type, ~advance: S -> A -> Control<S>, xs: List<A>, c: Control<S>) -> Control<S>:
  match xs c:
    case Nil{} c:
      c
    case h <> t Stop{s}:
      Stop{s}
    case h <> t Continue{s}:
      reduce_list(~A, ~S, ~advance, t, advance(s, h))

# A closed reducer driver. Binding the reducer as a template parameter lets
# the compiler see the step directly in the recursive loop, while the
# generic reducer driver above remains available to source adapters that need
# a runtime advance function.
def reduce_list_static(~A: Type, ~R: Type, ~r: Reducer<A, R>,
  xs: List<A>, c: Control<State(A, R, r)>) -> Control<State(A, R, r)>:
  match xs c:
    case Nil{} c:
      c
    case h <> t Stop{s}:
      Stop{s}
    case h <> t Continue{s}:
      reduce_list_static(~A, ~R, ~r, t, step(A, R, r, s, h))

def sum() -> Reducer<U32, U32>:
  Reducer{U32, U32, x => Continue{x}, s => x => Continue{(s + x : U32)}, s => s}

def map(~A: Type, ~B: Type, ~R: Type, ~f: A -> B, ~down: Reducer<B, R>) -> Reducer<A, R>:
  Reducer{Config(B, R, down), State(B, R, down),
    c => start(B, R, down, c),
    s => x => step(B, R, down, s, f(x)),
    s => finish(B, R, down, s)}

# Flatten one list-valued input into the downstream reducer. The nested fold
# checks downstream control before every element, so take/consumer stopping can
# happen in the middle of one fragment without evaluating the rest of it.
def cat(~B: Type, ~R: Type, ~down: Reducer<B, R>) -> Reducer<List<B>, R>:
  Reducer{Config(B, R, down), State(B, R, down),
    c => start(B, R, down, c),
    s => xs => reduce_list_static(~B, ~R, ~down, xs, Continue{s}),
    s => finish(B, R, down, s)}

# One-to-many mapping is ordinary map followed by list flattening. Keeping the
# two pieces separate makes cat useful on its own and gives both operations the
# same lifecycle and stopping semantics.
def mapcat(~A: Type, ~B: Type, ~R: Type, ~f: A -> List<B>,
  ~down: Reducer<B, R>) -> Reducer<A, R>:
  map(~A, ~List<B>, ~R, ~f, ~cat(~B, ~R, ~down))

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

# Empty configuration makes these consumers start fresh on every run.
def into_list(~A: Type) -> Reducer<A, List<A>>:
  Reducer{Unit, List<A>, u => Continue{[]},
    xs => x => Continue{x <> xs}, xs => List.reverse(&1, A, xs)}

def count(~A: Type) -> Reducer<A, Nat>:
  Reducer{Unit, Nat, u => Continue{0n}, n => x => Continue{1n+n}, n => n}

# Called only for a positive remaining budget, after checking control.
# Invariant: 0 < remaining <= end - begin, so begin <= value < end.
def range_value(end: U32, remaining: Nat) -> U32:
  (end - U32.from_nat(remaining) : U32)

type Range is Data:
  Range{begin: U32, end: U32}

def range(end: U32) -> Range:
  Range{0, end}

def range_between(begin: U32, end: U32) -> Range:
  Range{begin, end}

def drive_range(~S: Type, ~advance: S -> U32 -> Control<S>, +remaining: Nat,
  c: Control<S>, +end: U32) -> Control<S>:
  match remaining c:
    case n Stop{s}:
      Stop{s}
    case 0n Continue{s}:
      Continue{s}
    case 1n+p Continue{s}:
      drive_range(~S, ~advance, p, advance(s, range_value(end, 1n+p)), end)

def range_bounds(~S: Type, ~advance: S -> U32 -> Control<S>, valid: Bool,
  begin: U32, +end: U32, c: Control<S>) -> Control<S>:
  match valid:
    case False{}:
      c
    case True{}:
      drive_range(~S, ~advance, U32.to_nat((end - begin : U32)), c, end)

def reduce_range(~S: Type, ~advance: S -> U32 -> Control<S>, source: Range, c: Control<S>) -> Control<S>:
  match source:
    case Range{+begin, +end}:
      range_bounds(~S, ~advance, U32.is_lt(begin, end), begin, end, c)

def reduce_string(~S: Type, ~advance: S -> Char -> Control<S>, xs: String, c: Control<S>) -> Control<S>:
  match xs c:
    case SNil{} c:
      c
    case SCon{h, t} Stop{s}:
      Stop{s}
    case SCon{h, t} Continue{s}:
      reduce_string(~S, ~advance, t, advance(s, h))

# Ordered depth-first traversal of Bend's balanced array tree. The source is
# consumed structurally, so this avoids Array.get's repeated indexed descent
# and does not build an intermediate list. Array nodes check Control before
# entering the right child, preserving immediate downstream stopping.
def reduce_array(~A: Type, ~S: Type, ~advance: S -> A -> Control<S>,
  xs: Array<A>, c: Control<S>) -> Control<S>:
  match xs c:
    case ALeaf{x} Stop{s}:
      Stop{s}
    case ALeaf{x} Continue{s}:
      advance(s, x)
    case ANode{left, right} Stop{s}:
      Stop{s}
    case ANode{left, right} Continue{s}:
      reduce_array(~A, ~S, ~advance, right,
        reduce_array(~A, ~S, ~advance, left, Continue{s}))

# Static binding of a source-owned stopping fold to a reducer. This is open:
# third-party adapters construct it with reducible; no source registry exists.
# Type metadata is delayed so specialization need not evaluate type expressions
# while projecting run. The code-generation tests require this record to vanish.
type Reduction is Type:
  Reduction{Input: Unit -> Type, Output: Unit -> Type, Config: Unit -> Type,
    run: Config(Unit{}) -> Input(Unit{}) -> Output(Unit{})}

def Input(p: Reduction) -> Type:
  match p:
    case Reduction{X, R, C, run}:
      X(Unit{})

def Output(p: Reduction) -> Type:
  match p:
    case Reduction{X, R, C, run}:
      R(Unit{})

def RunConfig(p: Reduction) -> Type:
  match p:
    case Reduction{X, R, C, run}:
      C(Unit{})

def execute(p: Reduction) -> RunConfig(p) -> Input(p) -> Output(p):
  match p:
    case Reduction{X, R, C, run}:
      run

def transduce(~p: Reduction, config: RunConfig(p), source: Input(p)) -> Output(p):
  execute(p, config, source)

# The fold receives initialized Control and must return it without completing.
# Its step code is closed syntax; runtime settings remain in owned state.
# recipe is delayed to avoid repeatedly evaluating the same static reducer at
# nested binding boundaries and exhausting the compiler's bounded evaluator.
def reducible(~X: Type, ~A: Type, ~R: Type, ~recipe: Unit -> Reducer<A, R>,
  ~fold: X -> Control<State(A, R, recipe(Unit{}))> -> Control<State(A, R, recipe(Unit{}))>) -> Reduction:
  Reduction{u => X, u => R, u => Config(A, R, recipe(Unit{})),
    config => xs => finish_control(~A, ~R, ~recipe(Unit{}), fold(xs, start(A, R, recipe(Unit{}), config)))}

def over_list(~A: Type, ~R: Type, ~r: Reducer<A, R>) -> Reduction:
  reducible(~List<A>, ~A, ~R, ~(u => r),
    ~(xs => c => reduce_list_static(~A, ~R, ~r, xs, c)))

def over_range(~R: Type, ~r: Reducer<U32, R>) -> Reduction:
  reducible(~Range, ~U32, ~R, ~(u => r),
    ~(xs => c => reduce_range(~State(U32, R, r), ~(s => x => step(U32, R, r, s, x)), xs, c)))

def over_string(~R: Type, ~r: Reducer<Char, R>) -> Reduction:
  reducible(~String, ~Char, ~R, ~(u => r),
    ~(xs => c => reduce_string(~State(Char, R, r), ~(s => x => step(Char, R, r, s, x)), xs, c)))

def over_array(~A: Type, ~R: Type, ~r: Reducer<A, R>) -> Reduction:
  reducible(~Array<A>, ~A, ~R, ~(u => r),
    ~(xs => c => reduce_array(~A, ~State(A, R, r), ~(s => x => step(A, R, r, s, x)), xs, c)))
