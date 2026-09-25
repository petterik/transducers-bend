import Base
import ./branch_control_ablation.bend as Tree

# Isolated public-shape prototype. The established library remains unchanged.
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

def source_tree_loop(~K: Data, ~S: Type,
  ~advance: S -> U32 -> S, ~inspect: S -> Checked<K, S>,
  xs: Tree.Branch, checked: Checked<K, S>) -> S:
  match xs checked:
    case Tree.Tip{x} Halted{permit, state}: state
    case Tree.Tip{x} Ready{state}: advance(state, x)
    case Tree.Fork{left, right} Halted{permit, state}: state
    case Tree.Fork{left, right} Ready{state}:
      source_tree_loop(~K, ~S, ~advance, ~inspect, right,
        inspect(source_tree_loop(~K, ~S, ~advance, ~inspect,
          left, Ready{state})))

def source_tree(~K: Data, ~S: Type,
  ~advance: S -> U32 -> S, ~inspect: S -> Checked<K, S>,
  xs: Tree.Branch, state: S) -> S:
  source_tree_loop(~K, ~S, ~advance, ~inspect, xs, inspect(state))

def branch_source(xs: Tree.Branch) ->
  Source<U32, Tree.Branch,
    (K => S => advance => inspect => ys => state =>
      source_tree(~K, ~S, ~advance, ~inspect, ys, state))>:
  Source{xs}

def transduce_array(~A: Type, ~R: Type, ~reducer: Reducer<A, R>,
  initial: Config(A, R, reducer), xs: Array<A>) -> R:
  finish_control(~A, ~R, ~reducer,
    source_array(~A, ~Permit(A, R, reducer),
      ~(Control<Permit(A, R, reducer), State(A, R, reducer)>),
      ~(control => x => step_control(~A, ~R, ~reducer, control, x)),
      ~(control => inspect_control(~Permit(A, R, reducer),
        ~State(A, R, reducer), control)),
      xs, start(A, R, reducer, initial)))

type Xf<-A: Type, -B: Type,
  -P: @-R: Type -> @-down: Reducer<B, R> -> Reducer<A, R>> is Type:
  Xf{configure: @-R: Type -> @-down: Reducer<B, R> ->
    Config(B, R, down) -> Config(A, R, P(R, down))}

type Rf<-B: Type, -R: Type, -Q: Reducer<B, R>, -Init: Type> is Type:
  Rf{prepare: Init -> Config(B, R, Q)}

def sum_rf() -> Rf<U32, U32, sum(), U32>:
  Rf{initial => initial}

def map_xf(~A: Type, ~B: Type, ~f: A -> B) -> Xf<A, B,
  (R => down => map(~A, ~B, ~R, ~f, ~down))>:
  Xf{R => down => config => config}

def filter_xf(~A: Data, ~predicate: A -> Bool) -> Xf<A, A,
  (R => down => filter(~A, ~R, ~predicate, ~down))>:
  Xf{R => down => config => config}

def take_xf(~A: Type, n: Nat) -> Xf<A, A,
  (R => down => take(~A, ~R, ~down))>:
  Xf{R => down => config => (n, config)}

def compose(~A: Type, ~B: Type, ~C: Type,
  ~Outer: @-R: Type -> @-down: Reducer<B, R> -> Reducer<A, R>,
  ~Inner: @-R: Type -> @-down: Reducer<C, R> -> Reducer<B, R>,
  xf: Xf<A, B, Outer>, xg: Xf<B, C, Inner>) ->
  Xf<A, C, (R => down => Outer(R, Inner(R, down)))>:
  match xf xg:
    case Xf{configureF} Xf{configureG}:
      Xf{R => down => config =>
        configureF(R, Inner(R, down), configureG(R, down, config))}

def run_xf_array(~A: Type, ~B: Type,
  ~P: @-R: Type -> @-down: Reducer<B, R> -> Reducer<A, R>,
  ~R: Type, ~Q: Reducer<B, R>, ~Init: Type,
  xf: Xf<A, B, P>, rf: Rf<B, R, Q, Init>,
  initial: Init, xs: Array<A>) -> R:
  match xf rf:
    case Xf{configure} Rf{prepare}:
      transduce_array(~A, ~R, ~P(R, Q),
        configure(R, Q, prepare(initial)), xs)

def transduce(~A: Type, ~B: Type,
  ~P: @-R: Type -> @-down: Reducer<B, R> -> Reducer<A, R>,
  ~R: Type, ~Q: Reducer<B, R>, ~Init: Type,
  ~X: Type,
  ~Drive: @-K: Data -> @-S: Type -> @-advance: (S -> A -> S) ->
    @-inspect: (S -> Checked<K, S>) -> X -> S -> S,
  xf: Xf<A, B, P>, rf: Rf<B, R, Q, Init>,
  initial: Init, source: Source<A, X, Drive>) -> R:
  match xf rf source:
    case Xf{configure} Rf{prepare} Source{input}:
      config = configure(R, Q, prepare(initial))
      finish_control(~A, ~R, ~P(R, Q),
        Drive(Permit(A, R, P(R, Q)),
          (Control<Permit(A, R, P(R, Q)), State(A, R, P(R, Q))>),
          (control => x => step_control(~A, ~R, ~P(R, Q), control, x)),
          (control => inspect_control(~Permit(A, R, P(R, Q)),
            ~State(A, R, P(R, Q)), control)),
          input, start(A, R, P(R, Q), config)))

def inc(x: U32) -> U32:
  (x + 1 : U32)

def even(x: U32) -> Bool:
  U32.is_zero(U32.mod(x, 2))

def total_array(xs: Array<U32>) -> U32:
  transduce(map_xf(~U32, ~U32, ~inc), sum_rf(), 0, xs)

def filtered_array(xs: Array<U32>) -> U32:
  transduce(compose(map_xf(~U32, ~U32, ~inc),
    filter_xf(~U32, ~even)), sum_rf(), 0, xs)

def take_array(xs: Array<U32>, n: Nat) -> U32:
  transduce(compose(map_xf(~U32, ~U32, ~inc),
    take_xf(~U32, n)), sum_rf(), 0, xs)

def total_tree(xs: Tree.Branch) -> U32:
  transduce(map_xf(~U32, ~U32, ~inc), sum_rf(), 0,
    branch_source(xs))

def take_tree(xs: Tree.Branch, n: Nat) -> U32:
  transduce(take_xf(~U32, n), sum_rf(), 0, branch_source(xs))

def main() -> List<U32>:
  [total_array(Array.new(U32, 3n, 1)),
   filtered_array(Array.new(U32, 3n, 1)),
   take_array(Array.new(U32, 3n, 1), 0n),
   take_array(Array.new(U32, 3n, 1), 3n),
   total_tree(Tree.build(3n, 1)),
   take_tree(Tree.build(3n, 1), 3n)]
