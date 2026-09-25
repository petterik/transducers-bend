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

type Indexed<-S: Type> is Type:
  Indexed{next: Nat, inner: S}

def indexed_control(~K: Data, ~S: Type, next: Nat,
  control: Control<K, S>) -> Control<K, Indexed<S>>:
  match control:
    case Continue{state}: Continue{Indexed{next, state}}
    case Stop{permit, state}: Stop{permit, Indexed{next, state}}

def map_indexed_step(~A: Type, ~B: Type, ~R: Type,
  ~f: Nat -> A -> B, ~down: Reducer<B, R>,
  indexed: Indexed<State(B, R, down)>, x: A) ->
  Control<Permit(B, R, down), Indexed<State(B, R, down)>>:
  match indexed:
    case Indexed{+next, state}:
      indexed_control(~Permit(B, R, down), ~State(B, R, down),
        1n+next, step(B, R, down, state, f(next, x)))

def map_indexed_finish(~B: Type, ~R: Type, ~down: Reducer<B, R>,
  indexed: Indexed<State(B, R, down)>) -> R:
  match indexed:
    case Indexed{next, state}: finish(B, R, down, state)

def map_indexed(~A: Type, ~B: Type, ~R: Type,
  ~f: Nat -> A -> B, ~down: Reducer<B, R>) -> Reducer<A, R>:
  Reducer{Permit(B, R, down), Config(B, R, down),
    Indexed<State(B, R, down)>,
    config => indexed_control(~Permit(B, R, down),
      ~State(B, R, down), 0n, start(B, R, down, config)),
    state => x => map_indexed_step(~A, ~B, ~R, ~f, ~down, state, x),
    state => map_indexed_finish(~B, ~R, ~down, state)}

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

type Deduping<-A: Data, -S: Type> is Type:
  Deduping{previous: Maybe<A>, inner: S}

def dedupe_control(~A: Data, ~K: Data, ~S: Type,
  previous: Maybe<A>, control: Control<K, S>) ->
  Control<K, Deduping<A, S>>:
  match control:
    case Continue{state}: Continue{Deduping{previous, state}}
    case Stop{permit, state}: Stop{permit, Deduping{previous, state}}

def dedupe_choose(~A: Data, ~R: Type, ~down: Reducer<A, R>,
  duplicate: Bool, +x: A, state: State(A, R, down)) ->
  Control<Permit(A, R, down), Deduping<A, State(A, R, down)>>:
  match duplicate:
    case True{}: Continue{Deduping{Some{x}, state}}
    case False{}:
      dedupe_control(~A, ~Permit(A, R, down), ~State(A, R, down),
        Some{x}, step(A, R, down, state, x))

def dedupe_step(~A: Data, ~R: Type, ~equal: A -> A -> Bool,
  ~down: Reducer<A, R>, deduping: Deduping<A, State(A, R, down)>,
  +x: A) -> Control<Permit(A, R, down), Deduping<A, State(A, R, down)>>:
  match deduping:
    case Deduping{None{}, state}:
      dedupe_control(~A, ~Permit(A, R, down), ~State(A, R, down),
        Some{x}, step(A, R, down, state, x))
    case Deduping{Some{previous}, state}:
      dedupe_choose(~A, ~R, ~down, equal(previous, x), x, state)

def dedupe_finish(~A: Data, ~R: Type, ~down: Reducer<A, R>,
  deduping: Deduping<A, State(A, R, down)>) -> R:
  match deduping:
    case Deduping{previous, state}: finish(A, R, down, state)

# Compare adjacent input values. Equality is supplied by the caller; A must
# be Data because the previous value is retained while the current is emitted.
def dedupe(~A: Data, ~R: Type, ~equal: A -> A -> Bool,
  ~down: Reducer<A, R>) -> Reducer<A, R>:
  Reducer{Permit(A, R, down), Config(A, R, down),
    Deduping<A, State(A, R, down)>,
    config => dedupe_control(~A, ~Permit(A, R, down),
      ~State(A, R, down), None{}, start(A, R, down, config)),
    state => x => dedupe_step(~A, ~R, ~equal, ~down, state, x),
    state => dedupe_finish(~A, ~R, ~down, state)}

type Interposing<-A: Data, -S: Type> is Type:
  Interposing{separator: A, seen: Bool, inner: S}

def interpose_control(~A: Data, ~K: Data, ~S: Type,
  separator: A, seen: Bool, control: Control<K, S>) ->
  Control<K, Interposing<A, S>>:
  match control:
    case Continue{state}: Continue{Interposing{separator, seen, state}}
    case Stop{permit, state}: Stop{permit, Interposing{separator, seen, state}}

def interpose_start(~A: Data, ~R: Type, ~down: Reducer<A, R>,
  config: A & Config(A, R, down)) ->
  Control<Permit(A, R, down), Interposing<A, State(A, R, down)>>:
  (separator, initial) = config
  interpose_control(~A, ~Permit(A, R, down), ~State(A, R, down),
    separator, False{}, start(A, R, down, initial))

def interpose_after_separator(~A: Data, ~R: Type,
  ~down: Reducer<A, R>, separator: A, x: A,
  control: Control<Permit(A, R, down), State(A, R, down)>) ->
  Control<Permit(A, R, down), Interposing<A, State(A, R, down)>>:
  match control:
    case Continue{state}:
      interpose_control(~A, ~Permit(A, R, down), ~State(A, R, down),
        separator, True{}, step(A, R, down, state, x))
    case Stop{permit, state}:
      Stop{permit, Interposing{separator, True{}, state}}

def interpose_step(~A: Data, ~R: Type, ~down: Reducer<A, R>,
  interposing: Interposing<A, State(A, R, down)>, x: A) ->
  Control<Permit(A, R, down), Interposing<A, State(A, R, down)>>:
  match interposing:
    case Interposing{separator, False{}, state}:
      interpose_control(~A, ~Permit(A, R, down), ~State(A, R, down),
        separator, True{}, step(A, R, down, state, x))
    case Interposing{+separator, True{}, state}:
      interpose_after_separator(~A, ~R, ~down, separator, x,
        step(A, R, down, state, separator))

def interpose_finish(~A: Data, ~R: Type, ~down: Reducer<A, R>,
  interposing: Interposing<A, State(A, R, down)>) -> R:
  match interposing:
    case Interposing{separator, seen, state}: finish(A, R, down, state)

# Emit separator only between inputs, and propagate a stop on that separator
# before forwarding the next input.
def interpose(~A: Data, ~R: Type,
  ~down: Reducer<A, R>) -> Reducer<A, R>:
  Reducer{Permit(A, R, down), A & Config(A, R, down),
    Interposing<A, State(A, R, down)>,
    config => interpose_start(~A, ~R, ~down, config),
    state => x => interpose_step(~A, ~R, ~down, state, x),
    state => interpose_finish(~A, ~R, ~down, state)}

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

type Dropping<-S: Type> is Type:
  Dropping{left: Nat, inner: S}

def drop_control(~K: Data, ~S: Type, left: Nat,
  control: Control<K, S>) -> Control<K, Dropping<S>>:
  match control:
    case Continue{state}: Continue{Dropping{left, state}}
    case Stop{permit, state}: Stop{permit, Dropping{left, state}}

def drop_start(~A: Type, ~R: Type, ~down: Reducer<A, R>,
  config: Nat & Config(A, R, down)) ->
  Control<Permit(A, R, down), Dropping<State(A, R, down)>>:
  (left, inner) = config
  drop_control(~Permit(A, R, down), ~State(A, R, down), left,
    start(A, R, down, inner))

def drop_step(~A: Type, ~R: Type, ~down: Reducer<A, R>,
  dropping: Dropping<State(A, R, down)>, x: A) ->
  Control<Permit(A, R, down), Dropping<State(A, R, down)>>:
  match dropping:
    case Dropping{0n, state}:
      drop_control(~Permit(A, R, down), ~State(A, R, down), 0n,
        step(A, R, down, state, x))
    case Dropping{1n+p, state}:
      Continue{Dropping{p, state}}

def drop_finish(~A: Type, ~R: Type, ~down: Reducer<A, R>,
  dropping: Dropping<State(A, R, down)>) -> R:
  match dropping:
    case Dropping{left, state}: finish(A, R, down, state)

def drop(~A: Type, ~R: Type, ~down: Reducer<A, R>) -> Reducer<A, R>:
  Reducer{Permit(A, R, down), Nat & Config(A, R, down),
    Dropping<State(A, R, down)>,
    config => drop_start(~A, ~R, ~down, config),
    state => x => drop_step(~A, ~R, ~down, state, x),
    state => drop_finish(~A, ~R, ~down, state)}

type EveryNth<-S: Type> is Type:
  EveryNth{spacing: Nat, left: Nat, inner: S}

def every_nth_control(~K: Data, ~S: Type, spacing: Nat, left: Nat,
  control: Control<K, S>) -> Control<K, EveryNth<S>>:
  match control:
    case Continue{state}: Continue{EveryNth{spacing, left, state}}
    case Stop{permit, state}: Stop{permit, EveryNth{spacing, left, state}}

def take_nth_start(~A: Type, ~R: Type, ~down: Reducer<A, R>,
  config: Nat & Config(A, R, down)) ->
  Control<Permit(A, R, down), EveryNth<State(A, R, down)>>:
  (spacing, inner) = config
  every_nth_control(~Permit(A, R, down), ~State(A, R, down),
    spacing, 0n, start(A, R, down, inner))

def take_nth_step(~A: Type, ~R: Type, ~down: Reducer<A, R>,
  every: EveryNth<State(A, R, down)>, x: A) ->
  Control<Permit(A, R, down), EveryNth<State(A, R, down)>>:
  match every:
    case EveryNth{0n, left, state}:
      Continue{EveryNth{0n, left, state}}
    case EveryNth{1n++p, 0n, state}:
      every_nth_control(~Permit(A, R, down), ~State(A, R, down),
        1n+p, p, step(A, R, down, state, x))
    case EveryNth{1n+p, 1n+q, state}:
      Continue{EveryNth{1n+p, q, state}}

def take_nth_finish(~A: Type, ~R: Type, ~down: Reducer<A, R>,
  every: EveryNth<State(A, R, down)>) -> R:
  match every:
    case EveryNth{spacing, left, state}: finish(A, R, down, state)

# At zero spacing, no values are emitted. The source still drives its items,
# preserving a total downstream permit; use take(0) to stop before traversal.
def take_nth(~A: Type, ~R: Type,
  ~down: Reducer<A, R>) -> Reducer<A, R>:
  Reducer{Permit(A, R, down), Nat & Config(A, R, down),
    EveryNth<State(A, R, down)>,
    config => take_nth_start(~A, ~R, ~down, config),
    state => x => take_nth_step(~A, ~R, ~down, state, x),
    state => take_nth_finish(~A, ~R, ~down, state)}

type DroppingWhile<-S: Type> is Type:
  DroppingWhile{active: Bool, inner: S}

def drop_while_control(~K: Data, ~S: Type, active: Bool,
  control: Control<K, S>) -> Control<K, DroppingWhile<S>>:
  match control:
    case Continue{state}: Continue{DroppingWhile{active, state}}
    case Stop{permit, state}: Stop{permit, DroppingWhile{active, state}}

def drop_while_choose(~A: Data, ~R: Type,
  ~down: Reducer<A, R>, keep_dropping: Bool,
  state: State(A, R, down), x: A) ->
  Control<Permit(A, R, down), DroppingWhile<State(A, R, down)>>:
  match keep_dropping:
    case True{}: Continue{DroppingWhile{True{}, state}}
    case False{}:
      drop_while_control(~Permit(A, R, down), ~State(A, R, down), False{},
        step(A, R, down, state, x))

def drop_while_step(~A: Data, ~R: Type, ~predicate: A -> Bool,
  ~down: Reducer<A, R>, dropping: DroppingWhile<State(A, R, down)>,
  +x: A) -> Control<Permit(A, R, down), DroppingWhile<State(A, R, down)>>:
  match dropping:
    case DroppingWhile{True{}, state}:
      drop_while_choose(~A, ~R, ~down, predicate(x), state, x)
    case DroppingWhile{False{}, state}:
      drop_while_control(~Permit(A, R, down), ~State(A, R, down), False{},
        step(A, R, down, state, x))

def drop_while_finish(~A: Data, ~R: Type, ~down: Reducer<A, R>,
  dropping: DroppingWhile<State(A, R, down)>) -> R:
  match dropping:
    case DroppingWhile{active, state}: finish(A, R, down, state)

def drop_while(~A: Data, ~R: Type, ~predicate: A -> Bool,
  ~down: Reducer<A, R>) -> Reducer<A, R>:
  Reducer{Permit(A, R, down), Config(A, R, down),
    DroppingWhile<State(A, R, down)>,
    config => drop_while_control(~Permit(A, R, down),
      ~State(A, R, down), True{}, start(A, R, down, config)),
    state => x => drop_while_step(~A, ~R, ~predicate, ~down, state, x),
    state => drop_while_finish(~A, ~R, ~down, state)}

type TakingWhile<-S: Type> is Type:
  TakingWhile{inner: S}

def take_while_control(~K: Data, ~S: Type,
  control: Control<K, S>) -> Control<Unit, TakingWhile<S>>:
  match control:
    case Continue{state}: Continue{TakingWhile{state}}
    case Stop{permit, state}: Stop{Unit{}, TakingWhile{state}}

def take_while_choose(~A: Data, ~R: Type, ~down: Reducer<A, R>,
  keep: Bool, state: State(A, R, down), x: A) ->
  Control<Unit, TakingWhile<State(A, R, down)>>:
  match keep:
    case True{}:
      take_while_control(~Permit(A, R, down), ~State(A, R, down),
        step(A, R, down, state, x))
    case False{}: Stop{Unit{}, TakingWhile{state}}

def take_while_step(~A: Data, ~R: Type, ~predicate: A -> Bool,
  ~down: Reducer<A, R>, taking: TakingWhile<State(A, R, down)>,
  +x: A) -> Control<Unit, TakingWhile<State(A, R, down)>>:
  match taking:
    case TakingWhile{state}:
      take_while_choose(~A, ~R, ~down, predicate(x), state, x)

def take_while_finish(~A: Data, ~R: Type, ~down: Reducer<A, R>,
  taking: TakingWhile<State(A, R, down)>) -> R:
  match taking:
    case TakingWhile{state}: finish(A, R, down, state)

def take_while(~A: Data, ~R: Type, ~predicate: A -> Bool,
  ~down: Reducer<A, R>) -> Reducer<A, R>:
  Reducer{Unit, Config(A, R, down),
    TakingWhile<State(A, R, down)>,
    config => take_while_control(~Permit(A, R, down),
      ~State(A, R, down), start(A, R, down, config)),
    state => x => take_while_step(~A, ~R, ~predicate, ~down, state, x),
    state => take_while_finish(~A, ~R, ~down, state)}

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

# A source's closed drive without a fragment value. cat accepts this
# zero-field witness and still receives raw fragments from upstream.
type SourceAdapter<-A: Type, -X: Type,
  -Drive: @-K: Data -> @-S: Type -> @-advance: (S -> A -> S) ->
    @-inspect: (S -> Checked<K, S>) -> X -> S -> S> is Type:
  SourceAdapter{}

def Source.allow_companion() -> Unit:
  Unit{}

def Array.source(~A: Type, xs: Array<A>) ->
  Source<A, Array<A>, (K => S => advance => inspect => ys => state =>
    source_array(~A, ~K, ~S, ~advance, ~inspect, ys, state))>:
  Source{xs}

def Array.adapter(~A: Type) -> SourceAdapter<A, Array<A>,
  (K => S => advance => inspect => ys => state =>
    source_array(~A, ~K, ~S, ~advance, ~inspect, ys, state))>:
  SourceAdapter{}

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

def List.adapter(~A: Type) -> SourceAdapter<A, List<A>,
  (K => S => advance => inspect => ys => state =>
    source_list(~A, ~K, ~S, ~advance, ~inspect, ys, state))>:
  SourceAdapter{}

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

def Range.adapter() -> SourceAdapter<U32, Range,
  (K => S => advance => inspect => ys => state =>
    source_range(~K, ~S, ~advance, ~inspect, ys, state))>:
  SourceAdapter{}

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

def String.adapter() -> SourceAdapter<Char, String,
  (K => S => advance => inspect => ys => state =>
    source_string(~K, ~S, ~advance, ~inspect, ys, state))>:
  SourceAdapter{}

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

def keep_indexed(~A: Type, ~B: Type, ~R: Type,
  ~f: Nat -> A -> Maybe<B>,
  ~down: Reducer<B, R>) -> Reducer<A, R>:
  map_indexed(~A, ~Maybe<B>, ~R, ~f,
    ~cat_maybe(~B, ~R, ~down))

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

type GroupingBy<-A: Data, -K: Data, -S: Type> is Type:
  GroupingBy{previous: Maybe<K>, items: List<A>, inner: S}

def group_by_control(~A: Data, ~K: Data, ~P: Data, ~S: Type,
  previous: Maybe<K>, items: List<A>, control: Control<P, S>) ->
  Control<P, GroupingBy<A, K, S>>:
  match control:
    case Continue{state}: Continue{GroupingBy{previous, items, state}}
    case Stop{permit, state}:
      Stop{permit, GroupingBy{None{}, [], state}}

def group_by_choose(~A: Data, ~K: Data, ~R: Type,
  ~down: Reducer<List<A>, R>, same: Bool, key: K, x: A,
  items: List<A>, state: State(List<A>, R, down)) ->
  Control<Permit(List<A>, R, down),
    GroupingBy<A, K, State(List<A>, R, down)>>:
  match same:
    case True{}: Continue{GroupingBy{Some{key}, x <> items, state}}
    case False{}:
      group_by_control(~A, ~K, ~Permit(List<A>, R, down),
        ~State(List<A>, R, down), Some{key}, [x],
        step(List<A>, R, down, state, List.reverse(&1, A, items)))

def group_by_step_key(~A: Data, ~K: Data, ~R: Type,
  ~equal: K -> K -> Bool,
  ~down: Reducer<List<A>, R>,
  grouping: GroupingBy<A, K, State(List<A>, R, down)>,
  +current: K, x: A) ->
  Control<Permit(List<A>, R, down),
    GroupingBy<A, K, State(List<A>, R, down)>>:
  match grouping:
    case GroupingBy{None{}, items, state}:
      Continue{GroupingBy{Some{current}, x <> items, state}}
    case GroupingBy{Some{previous}, items, state}:
      group_by_choose(~A, ~K, ~R, ~down,
        equal(previous, current), current, x, items, state)

def group_by_step(~A: Data, ~K: Data, ~R: Type,
  ~key: A -> K, ~equal: K -> K -> Bool,
  ~down: Reducer<List<A>, R>,
  grouping: GroupingBy<A, K, State(List<A>, R, down)>, +x: A) ->
  Control<Permit(List<A>, R, down),
    GroupingBy<A, K, State(List<A>, R, down)>>:
  group_by_step_key(~A, ~K, ~R, ~equal, ~down,
    grouping, key(x), x)

def group_by_finish(~A: Data, ~K: Data, ~R: Type,
  ~down: Reducer<List<A>, R>,
  grouping: GroupingBy<A, K, State(List<A>, R, down)>) -> R:
  match grouping:
    case GroupingBy{previous, [], state}:
      finish(List<A>, R, down, state)
    case GroupingBy{previous, items, state}:
      finish_control(~List<A>, ~R, ~down,
        step(List<A>, R, down, state, List.reverse(&1, A, items)))

# Group consecutive equal keys. The key callback needs a reusable input
# because that same input is also retained in an ordered output group.
def partition_by(~A: Data, ~K: Data, ~R: Type,
  ~key: A -> K, ~equal: K -> K -> Bool,
  ~down: Reducer<List<A>, R>) -> Reducer<A, R>:
  Reducer{Permit(List<A>, R, down), Config(List<A>, R, down),
    GroupingBy<A, K, State(List<A>, R, down)>,
    config => group_by_control(~A, ~K, ~Permit(List<A>, R, down),
      ~State(List<A>, R, down), None{}, [],
      start(List<A>, R, down, config)),
    state => x => group_by_step(~A, ~K, ~R, ~key, ~equal,
      ~down, state, x),
    state => group_by_finish(~A, ~K, ~R, ~down, state)}

type Windowing<-A: Data, -S: Type> is Type:
  Windowing{left: Nat, items: +List<A>, inner: S}

def windows_control(~A: Data, ~K: Data, ~S: Type,
  left: Nat, items: +List<A>, control: Control<K, S>) ->
  Control<Unit, Windowing<A, S>>:
  match control:
    case Continue{state}:
      Continue{Windowing{left, items, state}}
    case Stop{permit, state}:
      Stop{Unit{}, Windowing{left, [], state}}

def windows_start_width(~A: Data, ~K: Data, ~S: Type,
  +width: Nat, control: Control<K, S>) ->
  Control<Unit, Windowing<A, S>>:
  match width:
    case 0n:
      match control:
        case Continue{state}: Stop{Unit{}, Windowing{0n, [], state}}
        case Stop{permit, state}:
          Stop{Unit{}, Windowing{0n, [], state}}
    case 1n+p:
      windows_control(~A, ~K, ~S, 1n+p, [], control)

def windows_start(~A: Data, ~R: Type,
  ~down: Reducer<List<A>, R>,
  config: Nat & Config(List<A>, R, down)) ->
  Control<Unit, Windowing<A, State(List<A>, R, down)>>:
  (width, initial) = config
  windows_start_width(~A, ~Permit(List<A>, R, down),
    ~State(List<A>, R, down), width,
    start(List<A>, R, down, initial))

def windows_after_step(~A: Data, ~R: Type,
  ~down: Reducer<List<A>, R>,
  window: +List<A>, control: Control<Permit(List<A>, R, down),
    State(List<A>, R, down)>) ->
  Control<Unit, Windowing<A, State(List<A>, R, down)>>:
  match control:
    case Continue{state}:
      Continue{Windowing{0n, List.tail(&2, A, window), state}}
    case Stop{permit, state}:
      Stop{Unit{}, Windowing{0n, [], state}}

def windows_copy(~A: Data, xs: +List<A>) -> List<A>:
  match xs:
    case Nil{}: Nil{}
    case h <> t: h <> windows_copy(~A, t)

def windows_emit(~A: Data, ~R: Type,
  ~down: Reducer<List<A>, R>,
  +window: +List<A>, state: State(List<A>, R, down)) ->
  Control<Unit, Windowing<A, State(List<A>, R, down)>>:
  windows_after_step(~A, ~R, ~down, window,
    step(List<A>, R, down, state, windows_copy(~A, window)))

def windows_step(~A: Data, ~R: Type,
  ~down: Reducer<List<A>, R>,
  windowing: Windowing<A, State(List<A>, R, down)>, x: A) ->
  Control<Unit, Windowing<A, State(List<A>, R, down)>>:
  match windowing:
    case Windowing{0n, items, state}:
      windows_emit(~A, ~R, ~down,
        List.append(&2, A, items, [x]), state)
    case Windowing{1n, items, state}:
      windows_emit(~A, ~R, ~down,
        List.reverse(&2, A, x <> items), state)
    case Windowing{1n+p, items, state}:
      Continue{Windowing{p, x <> items, state}}

def windows_finish(~A: Data, ~R: Type,
  ~down: Reducer<List<A>, R>,
  windowing: Windowing<A, State(List<A>, R, down)>) -> R:
  match windowing:
    case Windowing{left, items, state}:
      finish(List<A>, R, down, state)

# Full sliding windows only. Width zero stops before the first source item.
# Overlap shares Data values between the emitted window and retained tail.
def windows(~A: Data, ~R: Type,
  ~down: Reducer<List<A>, R>) -> Reducer<A, R>:
  Reducer{Unit, Nat & Config(List<A>, R, down),
    Windowing<A, State(List<A>, R, down)>,
    config => windows_start(~A, ~R, ~down, config),
    state => x => windows_step(~A, ~R, ~down, state, x),
    state => windows_finish(~A, ~R, ~down, state)}

type Windows2<-A: Data, -S: Type> is Type:
  Windows2{previous: Maybe<A>, inner: S}

def windows2_control(~A: Data, ~K: Data, ~S: Type,
  previous: Maybe<A>, control: Control<K, S>) ->
  Control<K, Windows2<A, S>>:
  match control:
    case Continue{state}: Continue{Windows2{previous, state}}
    case Stop{permit, state}: Stop{permit, Windows2{previous, state}}

def windows2_step(~A: Data, ~R: Type,
  ~down: Reducer<(A & A), R>,
  windowing: Windows2<A, State((A & A), R, down)>, +x: A) ->
  Control<Permit((A & A), R, down), Windows2<A, State((A & A), R, down)>>:
  match windowing:
    case Windows2{None{}, state}:
      Continue{Windows2{Some{x}, state}}
    case Windows2{Some{previous}, state}:
      windows2_control(~A, ~Permit((A & A), R, down),
        ~State((A & A), R, down), Some{x},
        step((A & A), R, down, state, (previous, x)))

def windows2_finish(~A: Data, ~R: Type,
  ~down: Reducer<(A & A), R>,
  windowing: Windows2<A, State((A & A), R, down)>) -> R:
  match windowing:
    case Windows2{previous, state}: finish((A & A), R, down, state)

# Full adjacent pairs. The current Data value also becomes the next pair's
# previous value; unlike List windows, no group List is built.
def windows2(~A: Data, ~R: Type,
  ~down: Reducer<(A & A), R>) -> Reducer<A, R>:
  Reducer{Permit((A & A), R, down), Config((A & A), R, down),
    Windows2<A, State((A & A), R, down)>,
    config => windows2_control(~A, ~Permit((A & A), R, down),
      ~State((A & A), R, down), None{},
      start((A & A), R, down, config)),
    state => x => windows2_step(~A, ~R, ~down, state, x),
    state => windows2_finish(~A, ~R, ~down, state)}

type Windows3Prefix<-A: Data> is Type:
  Windows3Zero{}
  Windows3One{first: A}
  Windows3Two{first: A, second: A}

type Windows3<-A: Data, -S: Type> is Type:
  Windows3{prefix: Windows3Prefix<A>, inner: S}

def windows3_control(~A: Data, ~K: Data, ~S: Type,
  prefix: Windows3Prefix<A>, control: Control<K, S>) ->
  Control<K, Windows3<A, S>>:
  match control:
    case Continue{state}: Continue{Windows3{prefix, state}}
    case Stop{permit, state}: Stop{permit, Windows3{prefix, state}}

def windows3_step(~A: Data, ~R: Type,
  ~down: Reducer<(A & A & A), R>,
  windowing: Windows3<A, State((A & A & A), R, down)>, +x: A) ->
  Control<Permit((A & A & A), R, down),
    Windows3<A, State((A & A & A), R, down)>>:
  match windowing:
    case Windows3{Windows3Zero{}, state}:
      Continue{Windows3{Windows3One{x}, state}}
    case Windows3{Windows3One{first}, state}:
      Continue{Windows3{Windows3Two{first, x}, state}}
    case Windows3{Windows3Two{first, +second}, state}:
      windows3_control(~A, ~Permit((A & A & A), R, down),
        ~State((A & A & A), R, down), Windows3Two{second, x},
        step((A & A & A), R, down, state, (first, second, x)))

def windows3_finish(~A: Data, ~R: Type,
  ~down: Reducer<(A & A & A), R>,
  windowing: Windows3<A, State((A & A & A), R, down)>) -> R:
  match windowing:
    case Windows3{prefix, state}:
      finish((A & A & A), R, down, state)

# Full adjacent triples without List construction.
def windows3(~A: Data, ~R: Type,
  ~down: Reducer<(A & A & A), R>) -> Reducer<A, R>:
  Reducer{Permit((A & A & A), R, down),
    Config((A & A & A), R, down),
    Windows3<A, State((A & A & A), R, down)>,
    config => windows3_control(~A, ~Permit((A & A & A), R, down),
      ~State((A & A & A), R, down), Windows3Zero{},
      start((A & A & A), R, down, config)),
    state => x => windows3_step(~A, ~R, ~down, state, x),
    state => windows3_finish(~A, ~R, ~down, state)}

def identity(~A: Type, ~R: Type,
  ~down: Reducer<A, R>) -> Reducer<A, R>:
  down

def into_list(~A: Type) -> Reducer<A, List<A>>:
  Reducer{Empty, Unit, List<A>,
    config => Continue{[]},
    xs => x => Continue{x <> xs},
    xs => List.reverse(&1, A, xs)}
