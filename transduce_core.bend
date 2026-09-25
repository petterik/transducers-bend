import Base

# Type-indexed reducer and source protocol. A source only receives and returns
# an opaque accumulator; the reducer owns the stopping permit.
type Control<-K: Data, -S: Type> is Type:
  Continue{state: S}
  Stop{permit: K, state: S}

type Checked<-K: Data, -S: Type> is Type:
  Ready{state: S}
  Halted{permit: K, state: S}

type Reducer<-A: Type, -R: Type> is Type:
  Reducer{K: Data, C: Type, S: Type,
    start: C -> Control<K, S>,
    step: S -> A -> Control<K, S>,
    finish: S -> R}

def Permit(-A: Type, -R: Type, reducer: Reducer<A, R>) -> Data:
  match reducer:
    case Reducer{K, C, S, start, step, finish}: K

def Config(-A: Type, -R: Type, reducer: Reducer<A, R>) -> Type:
  match reducer:
    case Reducer{K, C, S, start, step, finish}: C

def State(-A: Type, -R: Type, reducer: Reducer<A, R>) -> Type:
  match reducer:
    case Reducer{K, C, S, start, step, finish}: S

def start(-A: Type, -R: Type, reducer: Reducer<A, R>) ->
  Config(A, R, reducer) -> Control<Permit(A, R, reducer), State(A, R, reducer)>:
  match reducer:
    case Reducer{K, C, S, init, advance, done}: init

def step(-A: Type, -R: Type, reducer: Reducer<A, R>) ->
  State(A, R, reducer) -> A -> Control<Permit(A, R, reducer), State(A, R, reducer)>:
  match reducer:
    case Reducer{K, C, S, init, advance, done}: advance

def finish(-A: Type, -R: Type, reducer: Reducer<A, R>) ->
  State(A, R, reducer) -> R:
  match reducer:
    case Reducer{K, C, S, init, advance, done}: done

def sum() -> Reducer<U32, U32>:
  Reducer{Empty, U32, U32,
    initial => Continue{initial},
    state => x => Continue{(state + x : U32)},
    state => state}

def map(~A: Type, ~B: Type, ~R: Type, ~f: A -> B,
  ~down: Reducer<B, R>) -> Reducer<A, R>:
  Reducer{Permit(B, R, down), Config(B, R, down), State(B, R, down),
    initial => start(B, R, down, initial),
    state => x => step(B, R, down, state, f(x)),
    state => finish(B, R, down, state)}

def filter_choose(~A: Data, ~R: Type, ~down: Reducer<A, R>,
  keep: Bool, state: State(A, R, down), x: A) ->
  Control<Permit(A, R, down), State(A, R, down)>:
  match keep:
    case True{}: step(A, R, down, state, x)
    case False{}: Continue{state}

def filter_step(~A: Data, ~R: Type, ~predicate: A -> Bool,
  ~down: Reducer<A, R>, state: State(A, R, down), +x: A) ->
  Control<Permit(A, R, down), State(A, R, down)>:
  filter_choose(~A, ~R, ~down, predicate(x), state, x)

def filter(~A: Data, ~R: Type, ~predicate: A -> Bool,
  ~down: Reducer<A, R>) -> Reducer<A, R>:
  Reducer{Permit(A, R, down), Config(A, R, down), State(A, R, down),
    initial => start(A, R, down, initial),
    state => x => filter_step(~A, ~R, ~predicate, ~down, state, x),
    state => finish(A, R, down, state)}

type Taking<-K: Data, -S: Type> is Type:
  Taking{left: Nat, inner: Control<K, S>}

def take_control(~K: Data, ~S: Type,
  n: Nat, control: Control<K, S>) -> Control<Unit, Taking<K, S>>:
  match n control:
    case 0n Continue{state}:
      Stop{Unit{}, Taking{0n, Continue{state}}}
    case 0n Stop{permit, state}:
      Stop{Unit{}, Taking{0n, Stop{permit, state}}}
    case 1n+p Continue{state}:
      Continue{Taking{1n+p, Continue{state}}}
    case 1n+p Stop{permit, state}:
      Stop{Unit{}, Taking{1n+p, Stop{permit, state}}}

def take_start(~A: Type, ~R: Type, ~down: Reducer<A, R>,
  config: Nat & Config(A, R, down)) ->
  Control<Unit, Taking<Permit(A, R, down), State(A, R, down)>>:
  (n, inner) = config
  take_control(~Permit(A, R, down), ~State(A, R, down), n,
    start(A, R, down, inner))

def take_step(~A: Type, ~R: Type, ~down: Reducer<A, R>,
  taking: Taking<Permit(A, R, down), State(A, R, down)>, x: A) ->
  Control<Unit, Taking<Permit(A, R, down), State(A, R, down)>>:
  match taking:
    case Taking{0n, control}:
      Stop{Unit{}, Taking{0n, control}}
    case Taking{1n+p, Stop{permit, state}}:
      Stop{Unit{}, Taking{1n+p, Stop{permit, state}}}
    case Taking{1n+p, Continue{state}}:
      take_control(~Permit(A, R, down), ~State(A, R, down), p,
        step(A, R, down, state, x))

def finish_control(~A: Type, ~R: Type, ~reducer: Reducer<A, R>,
  control: Control<Permit(A, R, reducer), State(A, R, reducer)>) -> R:
  match control:
    case Continue{state}: finish(A, R, reducer, state)
    case Stop{permit, state}: finish(A, R, reducer, state)

def take_finish(~A: Type, ~R: Type, ~down: Reducer<A, R>,
  taking: Taking<Permit(A, R, down), State(A, R, down)>) -> R:
  match taking:
    case Taking{left, inner}: finish_control(~A, ~R, ~down, inner)

def take(~A: Type, ~R: Type, ~down: Reducer<A, R>) -> Reducer<A, R>:
  Reducer{Unit, Nat & Config(A, R, down),
    Taking<Permit(A, R, down), State(A, R, down)>,
    config => take_start(~A, ~R, ~down, config),
    state => x => take_step(~A, ~R, ~down, state, x),
    state => take_finish(~A, ~R, ~down, state)}

def inspect_control(~K: Data, ~S: Type,
  control: Control<K, S>) -> Checked<K, Control<K, S>>:
  match control:
    case Continue{state}: Ready{Continue{state}}
    case Stop{+permit, state}: Halted{permit, Stop{permit, state}}

def step_control(~A: Type, ~R: Type, ~reducer: Reducer<A, R>,
  control: Control<Permit(A, R, reducer), State(A, R, reducer)>, x: A) ->
  Control<Permit(A, R, reducer), State(A, R, reducer)>:
  match control:
    case Continue{state}: step(A, R, reducer, state, x)
    case Stop{permit, state}: Stop{permit, state}

def source_array_loop(~A: Type, ~K: Data, ~S: Type,
  ~advance: S -> A -> S, ~inspect: S -> Checked<K, S>,
  xs: Array<A>, checked: Checked<K, S>) -> S:
  match xs checked:
    case ALeaf{x} Halted{permit, state}: state
    case ALeaf{x} Ready{state}: advance(state, x)
    case ANode{left, right} Halted{permit, state}: state
    case ANode{left, right} Ready{state}:
      source_array_loop(~A, ~K, ~S, ~advance, ~inspect, right,
        inspect(source_array_loop(~A, ~K, ~S, ~advance, ~inspect,
          left, Ready{state})))

def source_array(~A: Type, ~K: Data, ~S: Type,
  ~advance: S -> A -> S, ~inspect: S -> Checked<K, S>,
  xs: Array<A>, state: S) -> S:
  source_array_loop(~A, ~K, ~S, ~advance, ~inspect, xs, inspect(state))

type Source<-A: Type, -X: Type,
  -Drive: @-K: Data -> @-S: Type -> @-advance: (S -> A -> S) ->
    @-inspect: (S -> Checked<K, S>) -> X -> S -> S> is Type:
  Source{input: X}

def Source.allow_companion() -> Unit:
  Unit{}

def Array.source(~A: Type, xs: Array<A>) ->
  Source<A, Array<A>, (K => S => advance => inspect => ys => state =>
    source_array(~A, ~K, ~S, ~advance, ~inspect, ys, state))>:
  Source{xs}

def source_list_loop(~A: Type, ~K: Data, ~S: Type,
  ~advance: S -> A -> S, ~inspect: S -> Checked<K, S>,
  xs: List<A>, checked: Checked<K, S>) -> S:
  match xs checked:
    case Nil{} Ready{state}: state
    case Nil{} Halted{permit, state}: state
    case h <> t Halted{permit, state}: state
    case h <> t Ready{state}:
      source_list_loop(~A, ~K, ~S, ~advance, ~inspect, t,
        inspect(advance(state, h)))

def source_list(~A: Type, ~K: Data, ~S: Type,
  ~advance: S -> A -> S, ~inspect: S -> Checked<K, S>,
  xs: List<A>, state: S) -> S:
  source_list_loop(~A, ~K, ~S, ~advance, ~inspect, xs, inspect(state))

def List.source(~A: Type, xs: List<A>) ->
  Source<A, List<A>, (K => S => advance => inspect => ys => state =>
    source_list(~A, ~K, ~S, ~advance, ~inspect, ys, state))>:
  Source{xs}

type Range is Data:
  Range{begin: U32, end: U32}

def range(end: U32) -> Range:
  Range{0, end}

def range_between(begin: U32, end: U32) -> Range:
  Range{begin, end}

def range_value(end: U32, remaining: Nat) -> U32:
  (end - U32.from_nat(remaining) : U32)

def source_range_loop(~K: Data, ~S: Type,
  ~advance: S -> U32 -> S, ~inspect: S -> Checked<K, S>,
  +remaining: Nat, checked: Checked<K, S>, +end: U32) -> S:
  match remaining checked:
    case n Halted{permit, state}: state
    case 0n Ready{state}: state
    case 1n+p Ready{state}:
      source_range_loop(~K, ~S, ~advance, ~inspect, p,
        inspect(advance(state, range_value(end, 1n+p))), end)

def source_range_bounds(~K: Data, ~S: Type,
  ~advance: S -> U32 -> S, ~inspect: S -> Checked<K, S>,
  valid: Bool, begin: U32, +end: U32, state: S) -> S:
  match valid:
    case False{}: state
    case True{}:
      source_range_loop(~K, ~S, ~advance, ~inspect,
        U32.to_nat((end - begin : U32)), inspect(state), end)

def source_range(~K: Data, ~S: Type,
  ~advance: S -> U32 -> S, ~inspect: S -> Checked<K, S>,
  xs: Range, state: S) -> S:
  match xs:
    case Range{+begin, +end}:
      source_range_bounds(~K, ~S, ~advance, ~inspect,
        U32.is_lt(begin, end), begin, end, state)

def Range.source(xs: Range) ->
  Source<U32, Range, (K => S => advance => inspect => ys => state =>
    source_range(~K, ~S, ~advance, ~inspect, ys, state))>:
  Source{xs}

def source_string_loop(~K: Data, ~S: Type,
  ~advance: S -> Char -> S, ~inspect: S -> Checked<K, S>,
  xs: String, checked: Checked<K, S>) -> S:
  match xs checked:
    case SNil{} Ready{state}: state
    case SNil{} Halted{permit, state}: state
    case SCon{h, t} Halted{permit, state}: state
    case SCon{h, t} Ready{state}:
      source_string_loop(~K, ~S, ~advance, ~inspect, t,
        inspect(advance(state, h)))

def source_string(~K: Data, ~S: Type,
  ~advance: S -> Char -> S, ~inspect: S -> Checked<K, S>,
  xs: String, state: S) -> S:
  source_string_loop(~K, ~S, ~advance, ~inspect, xs, inspect(state))

def String.source(xs: String) ->
  Source<Char, String, (K => S => advance => inspect => ys => state =>
    source_string(~K, ~S, ~advance, ~inspect, ys, state))>:
  Source{xs}

def cat_maybe_step(~B: Type, ~R: Type, ~down: Reducer<B, R>,
  item: Maybe<B>, state: State(B, R, down)) ->
  Control<Permit(B, R, down), State(B, R, down)>:
  match item:
    case None{}: Continue{state}
    case Some{x}: step(B, R, down, state, x)

def cat_maybe(~B: Type, ~R: Type,
  ~down: Reducer<B, R>) -> Reducer<Maybe<B>, R>:
  Reducer{Permit(B, R, down), Config(B, R, down), State(B, R, down),
    config => start(B, R, down, config),
    state => item => cat_maybe_step(~B, ~R, ~down, item, state),
    state => finish(B, R, down, state)}

# keep is map followed by consuming the resulting option.
def keep(~A: Type, ~B: Type, ~R: Type, ~f: A -> Maybe<B>,
  ~down: Reducer<B, R>) -> Reducer<A, R>:
  map(~A, ~Maybe<B>, ~R, ~f, ~cat_maybe(~B, ~R, ~down))

# The inner source moves the same stop permit through its opaque accumulator.
# The outer source sees a downstream stop even in the middle of a fragment.
def cat_source_step(~B: Type, ~X: Type,
  ~Drive: @-K: Data -> @-S: Type -> @-advance: (S -> B -> S) ->
    @-inspect: (S -> Checked<K, S>) -> X -> S -> S,
  ~R: Type, ~down: Reducer<B, R>,
  input: X, state: State(B, R, down)) ->
  Control<Permit(B, R, down), State(B, R, down)>:
  Drive(Permit(B, R, down),
    (Control<Permit(B, R, down), State(B, R, down)>),
    (control => x => step_control(~B, ~R, ~down, control, x)),
    (control => inspect_control(~Permit(B, R, down),
      ~State(B, R, down), control)),
    input, Continue{state})

def cat_source(~B: Type, ~X: Type,
  ~Drive: @-K: Data -> @-S: Type -> @-advance: (S -> B -> S) ->
    @-inspect: (S -> Checked<K, S>) -> X -> S -> S,
  ~R: Type, ~down: Reducer<B, R>) -> Reducer<X, R>:
  Reducer{Permit(B, R, down), Config(B, R, down), State(B, R, down),
    config => start(B, R, down, config),
    state => input => cat_source_step(~B, ~X, ~Drive, ~R, ~down,
      input, state),
    state => finish(B, R, down, state)}

def mapcat(~A: Type, ~B: Type, ~X: Type,
  ~Drive: @-K: Data -> @-S: Type -> @-advance: (S -> B -> S) ->
    @-inspect: (S -> Checked<K, S>) -> X -> S -> S,
  ~R: Type, ~f: A -> X,
  ~down: Reducer<B, R>) -> Reducer<A, R>:
  map(~A, ~X, ~R, ~f,
    ~cat_source(~B, ~X, ~Drive, ~R, ~down))

def count(~A: Type) -> Reducer<A, Nat>:
  Reducer{Empty, Unit, Nat,
    config => Continue{0n},
    state => item => Continue{1n+state},
    state => state}

def reducing(~A: Type, ~S: Type, ~R: Type,
  ~f: S -> A -> S, ~done: S -> R) -> Reducer<A, R>:
  Reducer{Empty, S, S,
    state => Continue{state},
    state => item => Continue{f(state, item)},
    done}

type Configured<-C: Data, -S: Type> is Type:
  Configured{config: C, inner: S}

def configured_wrap(~K: Data, ~C: Data, ~S: Type,
  config: C, control: Control<K, S>) ->
  Control<K, Configured<C, S>>:
  match control:
    case Continue{state}: Continue{Configured{config, state}}
    case Stop{permit, state}: Stop{permit, Configured{config, state}}

def configured_start(~A: Type, ~R: Type, ~C: Data,
  ~down: Reducer<A, R>, config: C & Config(A, R, down)) ->
  Control<Permit(A, R, down), Configured<C, State(A, R, down)>>:
  (local, inner) = config
  configured_wrap(~Permit(A, R, down), ~C, ~State(A, R, down),
    local, start(A, R, down, inner))

def configured_finish(~A: Type, ~R: Type, ~C: Data,
  ~down: Reducer<A, R>, state: Configured<C, State(A, R, down)>) -> R:
  match state:
    case Configured{local, inner}: finish(A, R, down, inner)

def map_with_step(~A: Type, ~B: Type, ~R: Type, ~C: Data,
  ~f: C -> A -> B, ~down: Reducer<B, R>,
  state: Configured<C, State(B, R, down)>, x: A) ->
  Control<Permit(B, R, down), Configured<C, State(B, R, down)>>:
  match state:
    case Configured{+local, inner}:
      configured_wrap(~Permit(B, R, down), ~C,
        ~State(B, R, down), local,
        step(B, R, down, inner, f(local, x)))

def map_with(~A: Type, ~B: Type, ~R: Type, ~C: Data,
  ~f: C -> A -> B, ~down: Reducer<B, R>) -> Reducer<A, R>:
  Reducer{Permit(B, R, down),
    C & Config(B, R, down), Configured<C, State(B, R, down)>,
    config => configured_start(~B, ~R, ~C, ~down, config),
    state => x => map_with_step(~A, ~B, ~R, ~C, ~f, ~down,
      state, x),
    state => configured_finish(~B, ~R, ~C, ~down, state)}

# A zero width stops before the source runs. A partial group is emitted once
# on completion, unless downstream has already stopped.
type Partitioning<-A: Type, -K: Data, -S: Type> is Type:
  Partitioning{size: Nat, left: Nat, items: List<A>,
    inner: Control<K, S>}

def partition_start_control(~A: Type, ~K: Data, ~S: Type,
  size: Nat, control: Control<K, S>) ->
  Control<Unit, Partitioning<A, K, S>>:
  match size control:
    case 0n Stop{permit, state}:
      Stop{Unit{}, Partitioning{0n, 0n, [], Stop{permit, state}}}
    case 0n Continue{state}:
      Stop{Unit{}, Partitioning{0n, 0n, [], Continue{state}}}
    case 1n++p Stop{permit, state}:
      Stop{Unit{}, Partitioning{1n+p, 1n+p, [], Stop{permit, state}}}
    case 1n++p Continue{state}:
      Continue{Partitioning{1n+p, 1n+p, [], Continue{state}}}

def partition_start(~A: Type, ~R: Type,
  ~down: Reducer<List<A>, R>,
  config: Nat & Config(List<A>, R, down)) ->
  Control<Unit, Partitioning<A, Permit(List<A>, R, down),
    State(List<A>, R, down)>>:
  (size, inner) = config
  partition_start_control(~A, ~Permit(List<A>, R, down),
    ~State(List<A>, R, down), size,
    start(List<A>, R, down, inner))

def partition_after_step(~A: Type, ~R: Type,
  ~down: Reducer<List<A>, R>, +size: Nat,
  control: Control<Permit(List<A>, R, down),
    State(List<A>, R, down)>) ->
  Control<Unit, Partitioning<A, Permit(List<A>, R, down),
    State(List<A>, R, down)>>:
  match control:
    case Stop{permit, state}:
      Stop{Unit{}, Partitioning{size, size, [], Stop{permit, state}}}
    case Continue{state}:
      Continue{Partitioning{size, size, [], Continue{state}}}

def partition_emit(~A: Type, ~R: Type,
  ~down: Reducer<List<A>, R>, +size: Nat,
  inner: Control<Permit(List<A>, R, down),
    State(List<A>, R, down)>, group: List<A>) ->
  Control<Unit, Partitioning<A, Permit(List<A>, R, down),
    State(List<A>, R, down)>>:
  match inner:
    case Stop{permit, state}:
      Stop{Unit{}, Partitioning{size, size, [], Stop{permit, state}}}
    case Continue{state}:
      partition_after_step(~A, ~R, ~down, size,
        step(List<A>, R, down, state, group))

def partition_step_nonzero(~A: Type, ~R: Type,
  ~down: Reducer<List<A>, R>, +size: Nat, p: Nat,
  items: List<A>, state: State(List<A>, R, down), x: A) ->
  Control<Unit, Partitioning<A, Permit(List<A>, R, down),
    State(List<A>, R, down)>>:
  match p:
    case 0n:
      partition_emit(~A, ~R, ~down, size, Continue{state},
        List.reverse(&1, A, x <> items))
    case 1n+q:
      Continue{Partitioning{size, 1n+q, x <> items,
        Continue{state}}}

def partition_step(~A: Type, ~R: Type,
  ~down: Reducer<List<A>, R>,
  grouping: Partitioning<A, Permit(List<A>, R, down),
    State(List<A>, R, down)>, x: A) ->
  Control<Unit, Partitioning<A, Permit(List<A>, R, down),
    State(List<A>, R, down)>>:
  match grouping:
    case Partitioning{size, left, items, Stop{permit, state}}:
      Stop{Unit{}, Partitioning{size, left, items, Stop{permit, state}}}
    case Partitioning{size, 0n, items, Continue{state}}:
      Stop{Unit{}, Partitioning{size, 0n, items, Continue{state}}}
    case Partitioning{size, 1n+p, items, Continue{state}}:
      partition_step_nonzero(~A, ~R, ~down, size, p, items,
        state, x)

def partition_finish(~A: Type, ~R: Type,
  ~down: Reducer<List<A>, R>,
  grouping: Partitioning<A, Permit(List<A>, R, down),
    State(List<A>, R, down)>) -> R:
  match grouping:
    case Partitioning{size, left, items, Stop{permit, state}}:
      finish(List<A>, R, down, state)
    case Partitioning{size, left, [], Continue{state}}:
      finish(List<A>, R, down, state)
    case Partitioning{size, left, items, Continue{state}}:
      finish_control(~List<A>, ~R, ~down,
        step(List<A>, R, down, state, List.reverse(&1, A, items)))

def partition_all(~A: Type, ~R: Type,
  ~down: Reducer<List<A>, R>) -> Reducer<A, R>:
  Reducer{Unit, Nat & Config(List<A>, R, down),
    Partitioning<A, Permit(List<A>, R, down), State(List<A>, R, down)>,
    config => partition_start(~A, ~R, ~down, config),
    state => x => partition_step(~A, ~R, ~down, state, x),
    state => partition_finish(~A, ~R, ~down, state)}

def identity(~A: Type, ~R: Type,
  ~down: Reducer<A, R>) -> Reducer<A, R>:
  down

def into_list(~A: Type) -> Reducer<A, List<A>>:
  Reducer{Empty, Unit, List<A>,
    config => Continue{[]},
    xs => x => Continue{x <> xs},
    xs => List.reverse(&1, A, xs)}
