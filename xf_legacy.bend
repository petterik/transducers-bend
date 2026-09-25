import Base
import ./transduce.bend as T

type Xf<-A: Type, -B: Type,
  -P: @-R: Type -> @-down: T.Reducer<B, R> ->
    T.Reducer<A, R>> is Type:
  Xf{configure: @-R: Type -> @-down: T.Reducer<B, R> ->
    T.Config(B, R, down) -> T.Config(A, R, P(R, down))}


# A consumer value also carries checked static reducer code in its type.
# Its live field consumes the caller's initial value and produces the
# configuration the reducer requires. No runtime reducer record is needed.
type Rf<-B: Type, -R: Type, -Q: T.Reducer<B, R>, -Init: Type> is Type:
  Rf{prepare: Init -> T.Config(B, R, Q)}

def sum_rf() -> Rf<U32, U32, T.sum(), U32>:
  Rf{initial => initial}

def count_nat_rf() -> Rf<Nat, Nat, T.count(~Nat), Unit>:
  Rf{initial => initial}

# A stage owns its runtime settings; its reducer recipe is checked, closed
# code in the result type. The leading type parameters remain explicit because
# today's omitted-template inference uses ordinary value arguments only.
def map(~A: Type, ~B: Type, ~f: A -> B) -> Xf<A, B,
  (R => down => T.map(~A, ~B, ~R, ~f, ~down))>:
  Xf{R => down => config => config}

def map_with(~A: Type, ~B: Type, ~C: Data, ~f: C -> A -> B,
  setting: C) -> Xf<A, B,
  (R => down => T.map_with(~A, ~B, ~R, ~C, ~f, ~down))>:
  Xf{R => down => config => (setting, config)}

def take(~A: Type, n: Nat) -> Xf<A, A,
  (R => down => T.take(~A, ~R, ~down))>:
  Xf{R => down => config => (n, config)}

# f returns a raw fragment whose closed source drive is supplied once in the
# stage type. It may be a List, Array, or custom collection; no per-fragment
# Source wrapper is needed. A mapper that builds a List still allocates that
# List; a small structural fragment can avoid per-input allocation.
def mapcat(~A: Type, ~B: Type, ~X: Type,
  ~Drive: @-S: Type -> @-advance: (S -> B -> S) ->
    @-inspect: (S -> T.Checked<S>) -> X -> S -> S,
  ~f: A -> X) -> Xf<A, B,
    (R => down => T.mapcat(~A, ~B, ~X, ~Drive, ~R, ~f, ~down))>:
  Xf{R => down => config => config}

def keep(~A: Type, ~B: Type, ~f: A -> Maybe<B>) -> Xf<A, B,
  (R => down => T.keep(~A, ~B, ~R, ~f, ~down))>:
  Xf{R => down => config => config}

def filter(~A: Data, ~predicate: A -> Bool) -> Xf<A, A,
  (R => down => T.filter(~A, ~R, ~Unit,
    ~(unused => x => predicate(x)), ~down))>:
  Xf{R => down => config => (Unit{}, config)}

def remove(~A: Data, ~predicate: A -> Bool) -> Xf<A, A,
  (R => down => T.filter(~A, ~R, ~Unit,
    ~(unused => x => Bool.not(predicate(x))), ~down))>:
  Xf{R => down => config => (Unit{}, config)}

# Inferred static indices make composition look like an ordinary value call.
def compose(~A: Type, ~B: Type, ~C: Type,
  ~Outer: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Inner: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  xf: Xf<A, B, Outer>, xg: Xf<B, C, Inner>) ->
  Xf<A, C, (R => down => Outer(R, Inner(R, down)))>:
  match xf xg:
    case Xf{configureF} Xf{configureG}:
      Xf{R => down => config =>
        configureF(R, Inner(R, down), configureG(R, down, config))}

# Fixed arities preserve each stage's distinct input, output, and closed
# provider type. They elaborate to the same binary composition, in source
# order, without constructing a runtime collection of stages.
def comp2(~A: Type, ~B: Type, ~C: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  a: Xf<A, B, P>, b: Xf<B, C, Q>) ->
  Xf<A, C, (R => down => P(R, Q(R, down)))>:
  compose(~A, ~B, ~C, ~P, ~Q, a, b)

def comp3(~A: Type, ~B: Type, ~C: Type, ~D: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  ~S: @-R: Type -> @-down: T.Reducer<D, R> -> T.Reducer<C, R>,
  a: Xf<A, B, P>, b: Xf<B, C, Q>, c: Xf<C, D, S>) ->
  Xf<A, D, (R => down => P(R, Q(R, S(R, down))))>:
  comp2(~A, ~B, ~D, ~P, ~(R => down => Q(R, S(R, down))),
    a, comp2(~B, ~C, ~D, ~Q, ~S, b, c))

def comp4(~A: Type, ~B: Type, ~C: Type, ~D: Type, ~E: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  ~S: @-R: Type -> @-down: T.Reducer<D, R> -> T.Reducer<C, R>,
  ~U: @-R: Type -> @-down: T.Reducer<E, R> -> T.Reducer<D, R>,
  a: Xf<A, B, P>, b: Xf<B, C, Q>,
  c: Xf<C, D, S>, d: Xf<D, E, U>) ->
  Xf<A, E, (R => down => P(R, Q(R, S(R, U(R, down)))))>:
  comp2(~A, ~B, ~E, ~P,
    ~(R => down => Q(R, S(R, U(R, down)))),
    a, comp3(~B, ~C, ~D, ~E, ~Q, ~S, ~U, b, c, d))

def comp5(~A: Type, ~B: Type, ~C: Type, ~D: Type, ~E: Type, ~F: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  ~S: @-R: Type -> @-down: T.Reducer<D, R> -> T.Reducer<C, R>,
  ~U: @-R: Type -> @-down: T.Reducer<E, R> -> T.Reducer<D, R>,
  ~W: @-R: Type -> @-down: T.Reducer<F, R> -> T.Reducer<E, R>,
  a: Xf<A, B, P>, b: Xf<B, C, Q>,
  c: Xf<C, D, S>, d: Xf<D, E, U>, e: Xf<E, F, W>) ->
  Xf<A, F, (R => down => P(R, Q(R, S(R, U(R, W(R, down))))))>:
  comp2(~A, ~B, ~F, ~P,
    ~(R => down => Q(R, S(R, U(R, W(R, down))))),
    a, comp4(~B, ~C, ~D, ~E, ~F, ~Q, ~S, ~U, ~W, b, c, d, e))

# Prepending is the List destination's insertion semantics. Unlike
# T.into_list it accepts an existing List and does not reverse at completion.
def list_prepend(~A: Type) -> T.Reducer<A, List<A>>:
  T.Reducer{List<A>, List<A>, xs => T.Continue{xs},
    xs => x => T.Continue{x <> xs}, xs => xs}

def list_prepend_rf(~A: Type) -> Rf<A, List<A>, list_prepend(~A), List<A>>:
  Rf{xs => xs}

# A destination selects its insertion reducer while owning an existing value.
type Destination<-B: Type, -D: Type, -Q: T.Reducer<B, D>> is Type:
  Destination{value: D, consumer: Rf<B, D, Q, D>}

def Destination.allow_companion() -> Unit:
  Unit{}

def List.destination(~A: Type, xs: List<A>) ->
  Destination<A, List<A>, list_prepend(~A)>:
  Destination{xs, list_prepend_rf(~A)}

def transduce_from(~A: Type, ~B: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  ~R: Type, ~Q: T.Reducer<B, R>, ~Init: Type,
  ~X: Type,
  ~Drive: @-S: Type -> @-advance: (S -> A -> S) ->
    @-inspect: (S -> T.Checked<S>) -> X -> S -> S,
  xf: Xf<A, B, P>, rf: Rf<B, R, Q, Init>,
  initial: Init, source: T.Source<A, X, Drive>) -> R:
  match xf rf source:
    case Xf{configure} Rf{prepare} T.Source{input}:
      config = configure(R, Q, prepare(initial))
      T.finish_control(~A, ~R, ~P(R, Q),
        Drive((T.Control<T.State(A, R, P(R, Q))>),
          (c => x => T.step_control(~A, ~R, ~P(R, Q), c, x)),
          (c => T.inspect_control(~T.State(A, R, P(R, Q)), c)), input,
          T.start(A, R, P(R, Q), config)))

def into_from(~A: Type, ~B: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  ~D: Type, ~Q: T.Reducer<B, D>, ~X: Type,
  ~Drive: @-S: Type -> @-advance: (S -> A -> S) ->
    @-inspect: (S -> T.Checked<S>) -> X -> S -> S,
  dest: Destination<B, D, Q>, xf: Xf<A, B, P>,
  source: T.Source<A, X, Drive>) -> D:
  match dest:
    case Destination{value, consumer}:
      transduce_from(~A, ~B, ~P, ~D, ~Q, ~D, ~X, ~Drive,
        xf, consumer, value, source)

# One public spelling for every source accepted by the isolated companion
# candidate. The expected witness types trigger checked, owner-scoped
# conversion of a raw owned collection at the call site.
def transduce(~A: Type, ~B: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  ~R: Type, ~Q: T.Reducer<B, R>, ~Init: Type,
  ~X: Type,
  ~Drive: @-S: Type -> @-advance: (S -> A -> S) ->
    @-inspect: (S -> T.Checked<S>) -> X -> S -> S,
  xf: Xf<A, B, P>, rf: Rf<B, R, Q, Init>,
  initial: Init, source: T.Source<A, X, Drive>) -> R:
  transduce_from(~A, ~B, ~P, ~R, ~Q, ~Init, ~X, ~Drive,
    xf, rf, initial, source)

def into(~A: Type, ~B: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  ~D: Type, ~Q: T.Reducer<B, D>, ~X: Type,
  ~Drive: @-S: Type -> @-advance: (S -> A -> S) ->
    @-inspect: (S -> T.Checked<S>) -> X -> S -> S,
  dest: Destination<B, D, Q>, xf: Xf<A, B, P>,
  source: T.Source<A, X, Drive>) -> D:
  into_from(~A, ~B, ~P, ~D, ~Q, ~X, ~Drive,
    dest, xf, source)
